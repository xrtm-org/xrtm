#!/usr/bin/env python3
"""Disposable Docker clean-room runner for provider-free acceptance."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.error import URLError
from urllib.request import Request, urlopen

WORKSPACE_REPOS = ("data", "eval", "forecast", "train", "xrtm")
DEFAULT_IMAGE_TAG = "xrtm-provider-free-acceptance:py311"
DEFAULT_PYTHON_IMAGE = "python:3.11-slim"
CONTAINER_WORKSPACE_ROOT = Path("/workspace")
DEFAULT_MANAGED_SANDBOX_TTL_HOURS = 24.0
DEFAULT_MANAGED_SANDBOX_CLEANUP_POLICY = "delete"
MANAGED_SANDBOX_ENV = "XRTM_ACCEPTANCE_USE_MANAGED_SANDBOX"
TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class HostConfig:
    workspace_root: Path
    xrtm_repo_root: Path
    artifact_source: str
    artifacts_dir: Path
    wheelhouse_dir: Path | None
    image_tag: str
    python_image: str
    xrtm_spec: str
    forecast_spec: str


@dataclass(frozen=True)
class ManagedSandboxContext:
    manager_path: Path
    registry_root: Path | None
    manifest: dict[str, Any]


def script_path() -> Path:
    return Path(__file__).resolve()


def workspace_root() -> Path:
    return script_path().parents[2]


def xrtm_repo_root() -> Path:
    return script_path().parents[1]


def resolve_host_path(value: str | None, default: Path) -> Path:
    return Path(value).resolve() if value else default


def container_workspace_path(path: Path, workspace_root_path: Path) -> Path:
    try:
        relative = path.resolve().relative_to(workspace_root_path.resolve())
    except ValueError as exc:
        raise ValueError(f"{path} must live under workspace root {workspace_root_path}") from exc
    return CONTAINER_WORKSPACE_ROOT / relative


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def default_artifacts_dir(root: Path, timestamp: str | None = None) -> Path:
    return root / "acceptance-studies" / "docker-provider-free" / (timestamp or utc_timestamp())


def env_flag_enabled(value: str | None) -> bool:
    return value is not None and value.strip().lower() in TRUTHY_ENV_VALUES


def managed_sandbox_requested(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "managed_sandbox", False) or env_flag_enabled(os.environ.get(MANAGED_SANDBOX_ENV)))


def default_sandbox_manager_path(workspace_root_path: Path) -> Path:
    return workspace_root_path.parent / "system-scripts" / "sandbox_manager.py"


def resolve_sandbox_manager_path(workspace_root_path: Path, override: str | None) -> Path:
    candidate = Path(override).expanduser().resolve() if override else default_sandbox_manager_path(workspace_root_path).resolve()
    if not candidate.is_file():
        raise FileNotFoundError(f"Sandbox manager not found: {candidate}")
    return candidate


def run_sandbox_manager_json(
    manager_path: Path,
    command: list[str],
    *,
    registry_root: Path | None = None,
) -> dict[str, Any]:
    env = dict(os.environ)
    if registry_root is not None:
        env["SANDBOX_REGISTRY_ROOT"] = str(registry_root)
    result = subprocess.run(
        [sys.executable, str(manager_path), *command, "--json"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip() or f"sandbox manager exited with {result.returncode}"
        raise RuntimeError(f"Sandbox manager command failed: {details}")
    return json.loads(result.stdout)


def managed_sandbox_summary(context: ManagedSandboxContext) -> dict[str, Any]:
    manifest = context.manifest
    integrity = manifest.get("integrity", {})
    return {
        "id": manifest["id"],
        "path": manifest["path"],
        "state": manifest["state"],
        "purpose": manifest["purpose"],
        "type": manifest["type"],
        "expires_at": manifest["expires_at"],
        "cleanup_policy": manifest["cleanup_policy"],
        "manifest_path": integrity.get("manifest_path"),
        "registry_root": integrity.get("registry_root"),
        "manager_path": str(context.manager_path),
    }


def add_managed_sandbox_metadata(payload: dict[str, Any], managed_sandbox: ManagedSandboxContext | None) -> dict[str, Any]:
    if managed_sandbox is not None:
        payload["managed_sandbox"] = managed_sandbox_summary(managed_sandbox)
    return payload


def prepare_host_artifacts_dir(
    *,
    args: argparse.Namespace,
    workspace_root_path: Path,
    repo_name: str,
    purpose: str,
    default_dir_factory,
) -> tuple[Path, ManagedSandboxContext | None]:
    requested_artifacts_dir = Path(args.artifacts_dir).expanduser().resolve() if args.artifacts_dir else None
    if not managed_sandbox_requested(args):
        artifacts_dir = requested_artifacts_dir or default_dir_factory(workspace_root_path)
        prepare_artifacts_dir(artifacts_dir)
        return artifacts_dir, None

    manager_path = resolve_sandbox_manager_path(workspace_root_path, getattr(args, "sandbox_manager", None))
    registry_root = (
        Path(args.sandbox_registry_root).expanduser().resolve()
        if getattr(args, "sandbox_registry_root", None)
        else None
    )
    create_command = [
        "create",
        "--repo",
        repo_name,
        "--purpose",
        purpose,
        "--type",
        "validation",
        "--cleanup-policy",
        args.sandbox_cleanup_policy,
        "--ttl-hours",
        str(args.sandbox_ttl_hours),
    ]
    if requested_artifacts_dir is not None:
        create_command.extend(["--path", str(requested_artifacts_dir)])
    manifest = run_sandbox_manager_json(manager_path, create_command, registry_root=registry_root)
    artifacts_dir = Path(manifest["path"]).resolve()
    prepare_artifacts_dir(artifacts_dir)
    return artifacts_dir, ManagedSandboxContext(manager_path=manager_path, registry_root=registry_root, manifest=manifest)


def load_project_version(repo_dir: Path) -> str:
    payload = tomllib.loads((repo_dir / "pyproject.toml").read_text(encoding="utf-8"))
    return payload["project"]["version"]


def repo_source_dir(repo: str, root: Path, xrtm_repo_root_path: Path | None = None) -> Path:
    candidate = root / repo
    if repo == "xrtm" and xrtm_repo_root_path is not None and not candidate.is_dir():
        return xrtm_repo_root_path
    return candidate


def default_specs(root: Path, xrtm_repo_root_path: Path | None = None) -> tuple[str, str]:
    xrtm_project_root = repo_source_dir("xrtm", root, xrtm_repo_root_path)
    return (
        f"xrtm=={load_project_version(xrtm_project_root)}",
        f"xrtm-forecast=={load_project_version(root / 'forecast')}",
    )


def command_text(command: Iterable[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_logged(
    command: list[str],
    *,
    log_path: Path,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd is not None else None,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    log_text = f"$ {command_text(command)}\n\n{result.stdout}"
    if result.returncode != 0:
        diagnostics = [f"return code: {result.returncode}"]
        if cwd is not None:
            core_files = sorted(path for path in Path(cwd).glob("core*") if path.is_file())
            if core_files:
                diagnostics.append("core files:")
                diagnostics.extend(f"- {path.name} ({path.stat().st_size} bytes)" for path in core_files)
        log_text += "\n\n[diagnostics]\n" + "\n".join(diagnostics)
        log_path.write_text(log_text, encoding="utf-8")
        raise subprocess.CalledProcessError(result.returncode, command, output=result.stdout)
    log_path.write_text(log_text, encoding="utf-8")
    return result


def prepare_artifacts_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def prepare_empty_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def wheelhouse_install_command(venv_python: Path, wheelhouse_dir: Path, specs: list[str]) -> list[str]:
    return [
        str(venv_python),
        "-m",
        "pip",
        "install",
        "--no-cache-dir",
        "--no-index",
        "--find-links",
        str(wheelhouse_dir),
        *specs,
    ]


def pypi_install_command(venv_python: Path, specs: list[str]) -> list[str]:
    return [str(venv_python), "-m", "pip", "install", "--no-cache-dir", *specs]


def docker_run_command(config: HostConfig) -> list[str]:
    container_xrtm_repo_root = container_workspace_path(config.xrtm_repo_root, config.workspace_root)
    command = [
        "docker",
        "run",
        "--rm",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "-v",
        f"{config.workspace_root}:{CONTAINER_WORKSPACE_ROOT}:ro",
        "-v",
        f"{config.artifacts_dir}:/artifacts",
    ]
    if config.wheelhouse_dir is not None:
        command.extend(["-v", f"{config.wheelhouse_dir}:/wheelhouse:ro"])
    command.extend(
        [
            config.image_tag,
            "inside",
            "--workspace-root",
            str(CONTAINER_WORKSPACE_ROOT),
            "--xrtm-repo-root",
            str(container_xrtm_repo_root),
            "--artifacts-dir",
            "/artifacts",
            "--artifact-source",
            config.artifact_source,
            "--xrtm-spec",
            config.xrtm_spec,
            "--forecast-spec",
            config.forecast_spec,
        ]
    )
    if config.wheelhouse_dir is not None:
        command.extend(["--wheelhouse-dir", "/wheelhouse"])
    return command


def docker_build_command(repo_root: Path, image_tag: str, python_image: str) -> list[str]:
    return [
        "docker",
        "build",
        "-f",
        str(repo_root / "docker" / "provider-free-acceptance.Dockerfile"),
        "-t",
        image_tag,
        "--build-arg",
        f"PYTHON_IMAGE={python_image}",
        str(repo_root),
    ]


def discover_run_ids(runs_dir: Path) -> list[str]:
    if not runs_dir.exists():
        return []
    return sorted(path.name for path in runs_dir.iterdir() if path.is_dir())


def latest_run_id(runs_dir: Path) -> str:
    run_ids = discover_run_ids(runs_dir)
    if not run_ids:
        raise RuntimeError(f"No run directories found in {runs_dir}")
    return run_ids[-1]


def new_run_id(previous_run_ids: Iterable[str], runs_dir: Path) -> str:
    previous = set(previous_run_ids)
    current = discover_run_ids(runs_dir)
    created = [run_id for run_id in current if run_id not in previous]
    if len(created) != 1:
        raise RuntimeError(f"Expected exactly one new run in {runs_dir}, found {created}")
    return created[0]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def reserve_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def fetch_json(
    url: str,
    *,
    output_path: Path,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> Any:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    with urlopen(Request(url, data=data, headers=headers, method=method), timeout=10) as response:
        body = response.read().decode("utf-8")
    write_text(output_path, body)
    return json.loads(body) if body else {}


def fetch_text(url: str, *, output_path: Path) -> str:
    with urlopen(url, timeout=10) as response:
        body = response.read().decode("utf-8")
    write_text(output_path, body)
    return body


def wait_for_web_server(base_url: str, *, timeout_seconds: float = 15.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urlopen(f"{base_url}/api/health", timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if payload.get("ready"):
                return payload
            last_error = RuntimeError(f"web server reported not ready: {payload}")
        except (URLError, OSError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            last_error = exc
        time.sleep(0.2)
    raise RuntimeError(f"Web server did not become ready at {base_url}") from last_error


def total_forecast_count(runs_dir: Path) -> int:
    total = 0
    for run_id in discover_run_ids(runs_dir):
        summary_path = runs_dir / run_id / "run_summary.json"
        total += int(load_json(summary_path)["forecast_count"])
    return total


def build_wheelhouse(root: Path, wheelhouse_dir: Path, logs_dir: Path, xrtm_repo_root_path: Path | None = None) -> None:
    prepare_empty_dir(wheelhouse_dir)
    for repo in WORKSPACE_REPOS:
        run_logged(
            ["uv", "build", "--wheel", "--python", "3.11", "--out-dir", str(wheelhouse_dir)],
            cwd=repo_source_dir(repo, root, xrtm_repo_root_path),
            log_path=logs_dir / f"build-{repo}.log",
        )
    local_wheels = [
        next(wheelhouse_dir.glob("xrtm_data-*.whl")),
        next(wheelhouse_dir.glob("xrtm_eval-*.whl")),
        next(wheelhouse_dir.glob("xrtm_forecast-*.whl")),
        next(wheelhouse_dir.glob("xrtm_train-*.whl")),
        next(wheelhouse_dir.glob("xrtm-*.whl")),
    ]
    run_logged(
        [
            sys.executable,
            "-m",
            "pip",
            "download",
            "--dest",
            str(wheelhouse_dir),
            "--find-links",
            str(wheelhouse_dir),
            "--python-version",
            "3.11",
            "--only-binary=:all:",
            *(str(wheel) for wheel in local_wheels),
        ],
        cwd=root,
        log_path=logs_dir / "download-wheelhouse-dependencies.log",
    )


def create_venv(venv_dir: Path, log_dir: Path, install_env: dict[str, str]) -> Path:
    prepare_empty_dir(venv_dir.parent)
    if venv_dir.exists():
        shutil.rmtree(venv_dir)
    run_logged([sys.executable, "-m", "venv", str(venv_dir)], log_path=log_dir / "create-venv.log", env=install_env)
    venv_python = venv_dir / "bin" / "python"
    run_logged([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], log_path=log_dir / "upgrade-pip.log", env=install_env)
    return venv_python


def install_specs(
    venv_python: Path,
    *,
    install_source: str,
    wheelhouse_dir: Path | None,
    specs: list[str],
    log_path: Path,
    env: dict[str, str],
) -> None:
    if install_source == "wheelhouse":
        if wheelhouse_dir is None:
            raise ValueError("wheelhouse_dir is required for wheelhouse installs")
        command = wheelhouse_install_command(venv_python, wheelhouse_dir, specs)
    else:
        command = pypi_install_command(venv_python, specs)
    run_logged(command, log_path=log_path, env=env)


def venv_env(venv_python: Path, base_env: dict[str, str]) -> dict[str, str]:
    env = dict(base_env)
    env["PATH"] = f"{venv_python.parent}:{base_env.get('PATH', '')}"
    return env


def write_versions(venv_python: Path, path: Path, env: dict[str, str]) -> None:
    commands = [
        ["xrtm", "--version"],
        ["xrtm-data", "--version"],
        ["forecast", "--version"],
        ["xrtm-forecast", "--version"],
        ["xrtm-train", "--version"],
    ]
    lines: list[str] = []
    for command in commands:
        result = subprocess.run(command, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        if result.returncode == 0:
            lines.append(result.stdout.strip())
    path.write_text("\n".join(line for line in lines if line) + "\n", encoding="utf-8")


def run_release_claims(repo_root: Path, env: dict[str, str], output_dir: Path) -> None:
    run_logged(
        [
            str(venv_python_from_env(env)),
            str(repo_root / "scripts" / "check_release_claims.py"),
            "--repo-root",
            str(repo_root),
            "--contract",
            str(repo_root / "docs" / "release-command-contract.json"),
            "--scope",
            "xrtm",
        ],
        log_path=output_dir / "release-claims.log",
        env=env,
    )


def run_cli_surface_check(repo_root: Path, env: dict[str, str], output_dir: Path) -> None:
    venv_python = venv_python_from_env(env)
    run_logged(
        [
            str(venv_python),
            str(repo_root / "scripts" / "check_installed_cli_surface.py"),
            "--xrtm-bin",
            str(venv_python.parent / "xrtm"),
        ],
        log_path=output_dir / "cli-surface.log",
        env=env,
    )


def venv_python_from_env(env: dict[str, str]) -> Path:
    first = env["PATH"].split(":", 1)[0]
    return Path(first) / "python"


def run_first_success(env: dict[str, str], artifacts_dir: Path) -> dict[str, Any]:
    journey_dir = artifacts_dir / "xrtm-release" / "first-success"
    prepare_artifacts_dir(journey_dir)
    runs_dir = journey_dir / "runs"
    run_logged(["xrtm", "doctor"], log_path=journey_dir / "doctor.log", cwd=journey_dir, env=env)
    run_logged(
        ["xrtm", "start", "--runs-dir", str(runs_dir)],
        log_path=journey_dir / "start.log",
        cwd=journey_dir,
        env=env,
    )
    run_logged(
        ["xrtm", "workflow", "list"],
        log_path=journey_dir / "workflow-list.log",
        cwd=journey_dir,
        env=env,
    )
    run_logged(
        ["xrtm", "workflow", "show", "demo-provider-free"],
        log_path=journey_dir / "workflow-show.log",
        cwd=journey_dir,
        env=env,
    )
    before_workflow = discover_run_ids(runs_dir)
    run_logged(
        ["xrtm", "workflow", "run", "demo-provider-free", "--runs-dir", str(runs_dir)],
        log_path=journey_dir / "workflow-run.log",
        cwd=journey_dir,
        env=env,
    )
    workflow_run_id = new_run_id(before_workflow, runs_dir)
    run_id = latest_run_id(runs_dir)
    run_dir = runs_dir / run_id
    run_logged(
        ["xrtm", "runs", "show", "latest", "--runs-dir", str(runs_dir)],
        log_path=journey_dir / "runs-show.log",
        cwd=journey_dir,
        env=env,
    )
    run_logged(
        ["xrtm", "artifacts", "inspect", "--latest", "--runs-dir", str(runs_dir)],
        log_path=journey_dir / "artifacts-inspect.log",
        cwd=journey_dir,
        env=env,
    )
    run_logged(
        ["xrtm", "report", "html", "--latest", "--runs-dir", str(runs_dir)],
        log_path=journey_dir / "report-html.log",
        cwd=journey_dir,
        env=env,
    )
    run_logged(["xrtm", "web", "--runs-dir", str(runs_dir), "--smoke"], log_path=journey_dir / "web-smoke.log", cwd=journey_dir, env=env)
    summary = {
        "run_id": run_id,
        "workflow_run_id": workflow_run_id,
        "status": load_json(run_dir / "run.json")["status"],
        "forecast_count": load_json(run_dir / "run_summary.json")["forecast_count"],
        "report_exists": (run_dir / "report.html").exists(),
        "blueprint_exists": (run_dir / "blueprint.json").exists(),
    }
    write_json(journey_dir / "summary.json", summary)
    return summary


def run_operator(env: dict[str, str], artifacts_dir: Path) -> dict[str, Any]:
    journey_dir = artifacts_dir / "xrtm-release" / "operator"
    prepare_artifacts_dir(journey_dir)
    runs_dir = journey_dir / "runs"
    profile_name = "docker-local-mock"
    before_profile = discover_run_ids(runs_dir)
    run_logged(
        [
            "xrtm",
            "profile",
            "create",
            profile_name,
            "--provider",
            "mock",
            "--limit",
            "2",
            "--runs-dir",
            "runs",
            "--profiles-dir",
            "profiles",
        ],
        log_path=journey_dir / "profile-create.log",
        cwd=journey_dir,
        env=env,
    )
    run_logged(
        ["xrtm", "profile", "show", profile_name, "--profiles-dir", "profiles"],
        log_path=journey_dir / "profile-show.log",
        cwd=journey_dir,
        env=env,
    )
    run_logged(
        ["xrtm", "run", "profile", profile_name, "--profiles-dir", "profiles"],
        log_path=journey_dir / "run-profile.log",
        cwd=journey_dir,
        env=env,
    )
    profile_run_id = new_run_id(before_profile, runs_dir)
    before_monitor = discover_run_ids(runs_dir)
    run_logged(
        ["xrtm", "monitor", "start", "--provider", "mock", "--limit", "2", "--runs-dir", "runs"],
        log_path=journey_dir / "monitor-start.log",
        cwd=journey_dir,
        env=env,
    )
    monitor_run_id = new_run_id(before_monitor, runs_dir)
    run_logged(["xrtm", "monitor", "list", "--runs-dir", "runs"], log_path=journey_dir / "monitor-list.log", cwd=journey_dir, env=env)
    run_ids = discover_run_ids(runs_dir)
    if len(run_ids) < 2:
        raise RuntimeError("Operator journey expected at least two runs")
    run_logged(["xrtm", "runs", "list", "--runs-dir", "runs"], log_path=journey_dir / "runs-list.log", cwd=journey_dir, env=env)
    run_logged(
        ["xrtm", "runs", "compare", profile_run_id, monitor_run_id, "--runs-dir", "runs"],
        log_path=journey_dir / "runs-compare.log",
        cwd=journey_dir,
        env=env,
    )
    export_path = journey_dir / "export.json"
    run_logged(
        ["xrtm", "runs", "export", monitor_run_id, "--runs-dir", "runs", "--output", "export.json"],
        log_path=journey_dir / "runs-export.log",
        cwd=journey_dir,
        env=env,
    )
    summary = {
        "run_ids": [profile_run_id, monitor_run_id],
        "export_keys": sorted(load_json(export_path).keys()),
        "monitor_runs": run_ids,
    }
    write_json(journey_dir / "summary.json", summary)
    return summary


def run_research_eval(env: dict[str, str], artifacts_dir: Path) -> dict[str, Any]:
    journey_dir = artifacts_dir / "xrtm-release" / "research-eval"
    prepare_artifacts_dir(journey_dir)
    runs_dir = journey_dir / "runs"
    before_first = discover_run_ids(runs_dir)
    run_logged(
        ["xrtm", "demo", "--provider", "mock", "--limit", "5", "--runs-dir", str(runs_dir)],
        log_path=journey_dir / "demo-1.log",
        cwd=journey_dir,
        env=env,
    )
    first_run_id = new_run_id(before_first, runs_dir)
    before_second = discover_run_ids(runs_dir)
    run_logged(
        ["xrtm", "demo", "--provider", "mock", "--limit", "5", "--runs-dir", str(runs_dir)],
        log_path=journey_dir / "demo-2.log",
        cwd=journey_dir,
        env=env,
    )
    second_run_id = new_run_id(before_second, runs_dir)
    run_logged(["xrtm", "runs", "list", "--runs-dir", str(runs_dir)], log_path=journey_dir / "runs-list.log", cwd=journey_dir, env=env)
    run_logged(
        ["xrtm", "runs", "show", second_run_id, "--runs-dir", str(runs_dir)],
        log_path=journey_dir / "runs-show.log",
        cwd=journey_dir,
        env=env,
    )
    run_logged(
        ["xrtm", "runs", "compare", first_run_id, second_run_id, "--runs-dir", str(runs_dir)],
        log_path=journey_dir / "runs-compare.log",
        cwd=journey_dir,
        env=env,
    )
    export_path = journey_dir / "export.json"
    run_logged(
        ["xrtm", "runs", "export", second_run_id, "--runs-dir", str(runs_dir), "--output", str(export_path)],
        log_path=journey_dir / "runs-export.log",
        cwd=journey_dir,
        env=env,
    )
    run_dir = runs_dir / second_run_id
    run_logged(["xrtm", "artifacts", "inspect", str(run_dir)], log_path=journey_dir / "artifacts-inspect.log", cwd=journey_dir, env=env)
    run_logged(["xrtm", "report", "html", str(run_dir)], log_path=journey_dir / "report-html.log", cwd=journey_dir, env=env)
    performance_path = journey_dir / "performance.json"
    run_logged(
        [
            "xrtm",
            "perf",
            "run",
            "--scenario",
            "provider-free-smoke",
            "--iterations",
            "3",
            "--limit",
            "1",
            "--runs-dir",
            "runs-perf",
            "--output",
            "performance.json",
        ],
        log_path=journey_dir / "perf-run.log",
        cwd=journey_dir,
        env=env,
    )
    perf_payload = load_json(performance_path)
    summary = {
        "run_ids": [first_run_id, second_run_id],
        "forecast_count": total_forecast_count(runs_dir),
        "brier": load_json(run_dir / "run_summary.json")["eval"]["brier_score"],
        "perf_iterations": perf_payload["iterations"],
        "perf_mean_seconds": perf_payload["summary"]["mean_seconds"],
        "perf_budget_passed": perf_payload["budget"]["status"] == "passed",
    }
    write_json(journey_dir / "summary.json", summary)
    return summary


def run_benchmark_matrix(env: dict[str, str], artifacts_dir: Path) -> dict[str, Any]:
    journey_dir = artifacts_dir / "xrtm-release" / "benchmark-matrix"
    prepare_artifacts_dir(journey_dir)
    benchmark_runs_dir = journey_dir / "runs-benchmark"
    benchmark_output_dir = journey_dir / "benchmark-output"
    competition_runs_dir = journey_dir / "runs-competition"
    run_logged(
        [
            "xrtm",
            "benchmark",
            "run",
            "--corpus-id",
            "xrtm-real-binary-v1",
            "--split",
            "eval",
            "--provider",
            "mock",
            "--limit",
            "5",
            "--iterations",
            "2",
            "--runs-dir",
            str(benchmark_runs_dir),
            "--output-dir",
            str(benchmark_output_dir),
            "--release-gate-mode",
        ],
        log_path=journey_dir / "benchmark-run.log",
        cwd=journey_dir,
        env=env,
    )
    run_logged(
        [
            "xrtm",
            "benchmark",
            "compare",
            "--corpus-id",
            "xrtm-real-binary-v1",
            "--split",
            "eval",
            "--limit",
            "5",
            "--runs-dir",
            str(benchmark_runs_dir),
            "--output-dir",
            str(benchmark_output_dir),
            "--release-gate-mode",
            "--baseline-label",
            "mock-control",
            "--baseline-provider",
            "mock",
            "--candidate-label",
            "mock-candidate",
            "--candidate-provider",
            "mock",
        ],
        log_path=journey_dir / "benchmark-compare.log",
        cwd=journey_dir,
        env=env,
    )
    run_logged(
        [
            "xrtm",
            "benchmark",
            "stress",
            "--corpus-id",
            "xrtm-real-binary-v1",
            "--split",
            "eval",
            "--limit",
            "3",
            "--repeats",
            "2",
            "--runs-dir",
            str(benchmark_runs_dir),
            "--output-dir",
            str(benchmark_output_dir),
            "--release-gate-mode",
            "--baseline-label",
            "mock-control",
            "--baseline-provider",
            "mock",
            "--candidate-label",
            "mock-candidate",
            "--candidate-provider",
            "mock",
        ],
        log_path=journey_dir / "benchmark-stress.log",
        cwd=journey_dir,
        env=env,
    )
    run_logged(
        [
            "xrtm",
            "competition",
            "dry-run",
            "metaculus-cup",
            "--runs-dir",
            str(competition_runs_dir),
            "--provider",
            "mock",
            "--limit",
            "2",
        ],
        log_path=journey_dir / "competition-dry-run.log",
        cwd=journey_dir,
        env=env,
    )
    competition_run_id = latest_run_id(competition_runs_dir)
    competition_run_dir = competition_runs_dir / competition_run_id
    summary = {
        "benchmark_artifacts": sorted(path.name for path in benchmark_output_dir.glob("*.json")),
        "benchmark_run_ids": discover_run_ids(benchmark_runs_dir),
        "competition_bundle_exists": (competition_run_dir / "competition_submission.json").exists(),
        "competition_run_id": competition_run_id,
    }
    write_json(journey_dir / "summary.json", summary)
    return summary


def run_workflow_authoring(env: dict[str, str], artifacts_dir: Path) -> dict[str, Any]:
    journey_dir = artifacts_dir / "xrtm-release" / "workflow-authoring"
    cli_dir = journey_dir / "cli"
    webui_dir = journey_dir / "webui"
    workflows_dir = journey_dir / ".xrtm" / "workflows"
    runs_dir = journey_dir / "runs"
    prepare_artifacts_dir(cli_dir)
    prepare_artifacts_dir(webui_dir)
    prepare_artifacts_dir(workflows_dir)

    scratch_name = "gate2-scratch-authoring"
    clone_name = "gate2-clone-authoring"
    template_name = "gate2-template-authoring"

    before_baseline = discover_run_ids(runs_dir)
    run_logged(["xrtm", "start", "--runs-dir", str(runs_dir)], log_path=cli_dir / "start.log", cwd=journey_dir, env=env)
    baseline_run_id = new_run_id(before_baseline, runs_dir)

    scratch_path = workflows_dir / f"{scratch_name}.json"
    run_logged(
        [
            "xrtm",
            "workflow",
            "create",
            "scratch",
            scratch_name,
            "--title",
            "Gate 2 scratch workflow",
            "--description",
            "Provider-free scratch workflow created in clean-room validation.",
            "--question-limit",
            "1",
            "--max-tokens",
            "512",
            "--workflows-dir",
            str(workflows_dir),
        ],
        log_path=cli_dir / "workflow-create-scratch.log",
        cwd=journey_dir,
        env=env,
    )
    run_logged(
        ["xrtm", "workflow", "validate", scratch_name, "--workflows-dir", str(workflows_dir)],
        log_path=cli_dir / "workflow-validate-scratch.log",
        cwd=journey_dir,
        env=env,
    )
    before_scratch = discover_run_ids(runs_dir)
    run_logged(
        ["xrtm", "workflow", "run", scratch_name, "--workflows-dir", str(workflows_dir), "--runs-dir", str(runs_dir)],
        log_path=cli_dir / "workflow-run-scratch.log",
        cwd=journey_dir,
        env=env,
    )
    scratch_run_id = new_run_id(before_scratch, runs_dir)
    scratch_run_dir = runs_dir / scratch_run_id
    run_logged(
        ["xrtm", "runs", "show", scratch_run_id, "--runs-dir", str(runs_dir)],
        log_path=cli_dir / "runs-show-scratch.log",
        cwd=journey_dir,
        env=env,
    )
    run_logged(
        ["xrtm", "runs", "compare", baseline_run_id, scratch_run_id, "--runs-dir", str(runs_dir)],
        log_path=cli_dir / "runs-compare-scratch.log",
        cwd=journey_dir,
        env=env,
    )
    run_logged(
        ["xrtm", "report", "html", str(scratch_run_dir)],
        log_path=cli_dir / "report-html-scratch.log",
        cwd=journey_dir,
        env=env,
    )
    if not scratch_path.exists():
        raise RuntimeError(f"Scratch workflow did not persist: {scratch_path}")
    if not (scratch_run_dir / "report.html").exists():
        raise RuntimeError(f"Scratch workflow report missing: {scratch_run_dir / 'report.html'}")

    clone_path = workflows_dir / f"{clone_name}.json"
    run_logged(
        [
            "xrtm",
            "workflow",
            "create",
            "clone",
            "demo-provider-free",
            clone_name,
            "--workflows-dir",
            str(workflows_dir),
        ],
        log_path=cli_dir / "workflow-create-clone.log",
        cwd=journey_dir,
        env=env,
    )
    run_logged(
        [
            "xrtm",
            "workflow",
            "edit",
            "metadata",
            clone_name,
            "--title",
            "Gate 2 cloned workflow",
            "--description",
            "Cloned workflow proved during clean-room validation.",
            "--tag",
            "gate2",
            "--tag",
            "clone",
            "--workflows-dir",
            str(workflows_dir),
        ],
        log_path=cli_dir / "workflow-edit-clone.log",
        cwd=journey_dir,
        env=env,
    )
    run_logged(
        ["xrtm", "workflow", "validate", clone_name, "--workflows-dir", str(workflows_dir)],
        log_path=cli_dir / "workflow-validate-clone.log",
        cwd=journey_dir,
        env=env,
    )
    before_clone = discover_run_ids(runs_dir)
    run_logged(
        ["xrtm", "workflow", "run", clone_name, "--workflows-dir", str(workflows_dir), "--runs-dir", str(runs_dir), "--limit", "1"],
        log_path=cli_dir / "workflow-run-clone.log",
        cwd=journey_dir,
        env=env,
    )
    clone_run_id = new_run_id(before_clone, runs_dir)
    clone_run_dir = runs_dir / clone_run_id
    if not clone_path.exists():
        raise RuntimeError(f"Cloned workflow did not persist: {clone_path}")

    port = reserve_local_port()
    base_url = f"http://127.0.0.1:{port}"
    server_log_path = webui_dir / "web-server.log"
    with server_log_path.open("w", encoding="utf-8") as server_log:
        server = subprocess.Popen(
            [
                "xrtm",
                "web",
                "--runs-dir",
                str(runs_dir),
                "--workflows-dir",
                str(workflows_dir),
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=str(journey_dir),
            env=env,
            text=True,
            stdout=server_log,
            stderr=subprocess.STDOUT,
        )
        try:
            wait_for_web_server(base_url)
            health = fetch_json(f"{base_url}/api/health", output_path=webui_dir / "health.json")
            workbench_html = fetch_text(f"{base_url}/workbench", output_path=webui_dir / "workbench.html")
            catalog = fetch_json(f"{base_url}/api/authoring/catalog", output_path=webui_dir / "authoring-catalog.json")
            created = fetch_json(
                f"{base_url}/api/drafts",
                output_path=webui_dir / "draft-create.json",
                method="POST",
                payload={
                    "creation_mode": "template",
                    "template_id": "provider-free-demo",
                    "draft_workflow_name": template_name,
                    "baseline_run_id": baseline_run_id,
                    "title": "Gate 2 template workflow",
                    "description": "Template workflow created in provider-free clean-room validation.",
                },
            )
            updated = fetch_json(
                f"{base_url}/api/drafts/{created['id']}",
                output_path=webui_dir / "draft-update.json",
                method="PATCH",
                payload={
                    "action": {
                        "type": "update-core",
                        "metadata": {
                            "title": "Gate 2 template workflow",
                            "description": "Template-authored workflow updated through the WebUI authoring surface.",
                            "workflow_kind": "workflow",
                            "tags": ["gate2", "webui"],
                        },
                        "questions": {"limit": 1},
                        "runtime": {"provider": "mock", "base_url": None, "model": None, "max_tokens": 512},
                        "artifacts": {
                            "write_report": True,
                            "write_blueprint_copy": True,
                            "write_graph_trace": True,
                        },
                        "scoring": {"write_eval": True, "write_train_backtest": True},
                    }
                },
            )
            draft_snapshot = fetch_json(
                f"{base_url}/api/drafts/{created['id']}",
                output_path=webui_dir / "draft-get.json",
            )
            validated = fetch_json(
                f"{base_url}/api/drafts/{created['id']}/validate",
                output_path=webui_dir / "draft-validate.json",
                method="POST",
                payload={},
            )
            launched = fetch_json(
                f"{base_url}/api/drafts/{created['id']}/run",
                output_path=webui_dir / "draft-run.json",
                method="POST",
                payload={},
            )
            candidate_run_id = str(launched["run_id"])
            candidate_run_dir = runs_dir / candidate_run_id
            workflow_detail_html = fetch_text(
                f"{base_url}/workflows/{template_name}",
                output_path=webui_dir / "workflow-detail.html",
            )
            run_detail = fetch_json(
                f"{base_url}/api/runs/{candidate_run_id}",
                output_path=webui_dir / "run-detail.json",
            )
            run_detail_html = fetch_text(
                f"{base_url}/runs/{candidate_run_id}",
                output_path=webui_dir / "run-detail.html",
            )
            compare = fetch_json(
                f"{base_url}/api/runs/{candidate_run_id}/compare/{baseline_run_id}",
                output_path=webui_dir / "compare.json",
            )
            compare_html = fetch_text(
                f"{base_url}/runs/{candidate_run_id}/compare/{baseline_run_id}",
                output_path=webui_dir / "compare.html",
            )
            fetch_json(
                f"{base_url}/api/runs/{candidate_run_id}/report",
                output_path=webui_dir / "report.json",
                method="POST",
                payload={},
            )
            report_html = fetch_text(
                f"{base_url}/runs/{candidate_run_id}/report",
                output_path=webui_dir / "report.html",
            )
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)

    if "Loading the local-first app shell" not in workbench_html:
        raise RuntimeError("Workbench route did not return the app shell")
    if "Loading the local-first app shell" not in workflow_detail_html:
        raise RuntimeError("Workflow detail route did not return the app shell")
    if "Loading the local-first app shell" not in run_detail_html:
        raise RuntimeError("Run detail route did not return the app shell")
    if "Loading the local-first app shell" not in compare_html:
        raise RuntimeError("Compare route did not return the app shell")
    if "<html" not in report_html.lower():
        raise RuntimeError("Report route did not return HTML")
    if not validated["validation"]["ok"]:
        raise RuntimeError(f"WebUI draft validation failed: {validated}")
    if launched["compare"]["baseline_run_id"] != baseline_run_id:
        raise RuntimeError(f"WebUI compare baseline mismatch: expected {baseline_run_id}, got {launched['compare']}")
    if compare["baseline_run_id"] != baseline_run_id:
        raise RuntimeError(f"Compare snapshot baseline mismatch: expected {baseline_run_id}, got {compare}")
    if not candidate_run_dir.exists():
        raise RuntimeError(f"WebUI candidate run missing: {candidate_run_dir}")
    if not (candidate_run_dir / "report.html").exists():
        raise RuntimeError(f"WebUI report missing: {candidate_run_dir / 'report.html'}")
    if not (workflows_dir / f"{template_name}.json").exists():
        raise RuntimeError(f"WebUI template workflow did not persist: {workflows_dir / f'{template_name}.json'}")

    summary = {
        "baseline_run_id": baseline_run_id,
        "cli": {
            "scratch_workflow_path": str(scratch_path),
            "scratch_run_id": scratch_run_id,
            "scratch_status": load_json(scratch_run_dir / "run.json")["status"],
            "scratch_report_exists": (scratch_run_dir / "report.html").exists(),
            "clone_workflow_path": str(clone_path),
            "clone_run_id": clone_run_id,
            "clone_status": load_json(clone_run_dir / "run.json")["status"],
        },
        "webui": {
            "catalog_modes": [item["key"] for item in catalog["creation_modes"]],
            "draft_id": created["id"],
            "workflow_name": template_name,
            "workflow_path": str(workflows_dir / f"{template_name}.json"),
            "updated_title": updated["authoring"]["core_form"]["title"],
            "validate_ok": validated["validation"]["ok"],
            "candidate_run_id": candidate_run_id,
            "candidate_status": run_detail["summary"]["status"],
            "compare_baseline_run_id": compare["baseline_run_id"],
            "compare_row_count": len(compare["rows"]),
            "report_exists": (candidate_run_dir / "report.html").exists(),
            "workbench_route_ok": "Loading the local-first app shell" in workbench_html,
            "workflow_detail_route_ok": "Loading the local-first app shell" in workflow_detail_html,
            "run_detail_route_ok": "Loading the local-first app shell" in run_detail_html,
            "compare_route_ok": "Loading the local-first app shell" in compare_html,
            "report_route_ok": "<html" in report_html.lower(),
            "draft_source": draft_snapshot["workflow"]["source"],
            "health_ready": health["ready"],
        },
    }
    write_json(journey_dir / "summary.json", summary)
    return summary


def run_playground(env: dict[str, str], artifacts_dir: Path) -> dict[str, Any]:
    journey_dir = artifacts_dir / "xrtm-release" / "playground"
    cli_dir = journey_dir / "cli"
    webui_dir = journey_dir / "webui"
    workflows_dir = journey_dir / ".xrtm" / "workflows"
    profiles_dir = journey_dir / ".xrtm" / "profiles"
    runs_dir = journey_dir / "runs"
    prepare_artifacts_dir(cli_dir)
    prepare_artifacts_dir(webui_dir)
    prepare_artifacts_dir(workflows_dir)
    prepare_artifacts_dir(profiles_dir)

    before_baseline = discover_run_ids(runs_dir)
    run_logged(["xrtm", "start", "--runs-dir", str(runs_dir)], log_path=cli_dir / "start.log", cwd=journey_dir, env=env)
    baseline_run_id = new_run_id(before_baseline, runs_dir)

    cli_question = "Will the provider-free CLI playground custom-question flow pass Gate 2?"
    before_cli = discover_run_ids(runs_dir)
    run_logged(
        [
            "xrtm",
            "playground",
            "--workflow",
            "demo-provider-free",
            "--question",
            cli_question,
            "--workflows-dir",
            str(workflows_dir),
            "--runs-dir",
            str(runs_dir),
        ],
        log_path=cli_dir / "playground.log",
        cwd=journey_dir,
        env=env,
    )
    cli_run_id = new_run_id(before_cli, runs_dir)
    cli_run_dir = runs_dir / cli_run_id
    cli_session = load_json(cli_run_dir / "sandbox_session.json")
    cli_step_orders = [int(step["order"]) for step in cli_session["inspection_steps"]]
    if cli_session["labeling"]["classification"] != "exploratory":
        raise RuntimeError(f"CLI playground run should stay exploratory: {cli_session['labeling']}")
    if cli_session["context"]["workflow_name"] != "demo-provider-free":
        raise RuntimeError(f"CLI playground used unexpected workflow context: {cli_session['context']}")
    if cli_session["run"]["provider"] != "mock":
        raise RuntimeError(f"CLI playground should stay provider-free: {cli_session['run']}")
    if cli_session["save_back"]["mode"] != "explicit":
        raise RuntimeError(f"CLI playground save-back should stay explicit: {cli_session['save_back']}")
    if cli_step_orders != sorted(cli_step_orders):
        raise RuntimeError(f"CLI inspection steps are not ordered: {cli_session['inspection_steps']}")
    if not cli_session["inspection_steps"] or cli_session["inspection_steps"][0]["node_id"] != "load_questions":
        raise RuntimeError(f"CLI inspection steps missing load_questions entry: {cli_session['inspection_steps']}")
    if not cli_session["inspection_steps"][0]["artifact_payloads"].get("questions"):
        raise RuntimeError(f"CLI inspection steps missing normalized question payloads: {cli_session['inspection_steps'][0]}")
    cli_log = (cli_dir / "playground.log").read_text(encoding="utf-8")
    if "Exploratory playground session" not in cli_log or "Step inspection" not in cli_log:
        raise RuntimeError("CLI playground output did not include the expected exploratory inspection summary")
    run_logged(
        ["xrtm", "runs", "show", cli_run_id, "--runs-dir", str(runs_dir)],
        log_path=cli_dir / "runs-show.log",
        cwd=journey_dir,
        env=env,
    )
    run_logged(
        ["xrtm", "runs", "compare", baseline_run_id, cli_run_id, "--runs-dir", str(runs_dir)],
        log_path=cli_dir / "runs-compare.log",
        cwd=journey_dir,
        env=env,
    )
    run_logged(
        ["xrtm", "report", "html", str(cli_run_dir)],
        log_path=cli_dir / "report-html.log",
        cwd=journey_dir,
        env=env,
    )
    if not (cli_run_dir / "report.html").exists():
        raise RuntimeError(f"CLI playground report missing: {cli_run_dir / 'report.html'}")

    web_question = "Will the provider-free WebUI playground custom-question flow pass Gate 2?"
    saved_workflow_name = "gate2-playground-web-workflow"
    saved_profile_name = "gate2-playground-web-profile"
    port = reserve_local_port()
    base_url = f"http://127.0.0.1:{port}"
    server_log_path = webui_dir / "web-server.log"
    with server_log_path.open("w", encoding="utf-8") as server_log:
        server = subprocess.Popen(
            [
                "xrtm",
                "web",
                "--runs-dir",
                str(runs_dir),
                "--workflows-dir",
                str(workflows_dir),
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=str(journey_dir),
            env=env,
            text=True,
            stdout=server_log,
            stderr=subprocess.STDOUT,
        )
        try:
            wait_for_web_server(base_url)
            health = fetch_json(f"{base_url}/api/health", output_path=webui_dir / "health.json")
            playground_html = fetch_text(f"{base_url}/playground", output_path=webui_dir / "playground.html")
            snapshot = fetch_json(f"{base_url}/api/playground", output_path=webui_dir / "playground-snapshot.json")
            updated = fetch_json(
                f"{base_url}/api/playground",
                output_path=webui_dir / "playground-update.json",
                method="PATCH",
                payload={
                    "context_type": "template",
                    "template_id": "provider-free-demo",
                    "question_prompt": web_question,
                    "question_title": "Gate 2 playground WebUI question",
                    "resolution_criteria": "Resolves YES if the provider-free playground run completes through the shared WebUI sandbox path.",
                },
            )
            launched = fetch_json(
                f"{base_url}/api/playground/run",
                output_path=webui_dir / "playground-run.json",
                method="POST",
                payload={},
            )
            last_result = launched["last_result"]
            web_run_id = str(last_result["run_id"])
            web_run_dir = runs_dir / web_run_id
            run_detail = fetch_json(
                f"{base_url}/api/runs/{web_run_id}",
                output_path=webui_dir / "run-detail.json",
            )
            run_detail_html = fetch_text(
                f"{base_url}/runs/{web_run_id}",
                output_path=webui_dir / "run-detail.html",
            )
            compare = fetch_json(
                f"{base_url}/api/runs/{web_run_id}/compare/{baseline_run_id}",
                output_path=webui_dir / "compare.json",
            )
            compare_html = fetch_text(
                f"{base_url}/runs/{web_run_id}/compare/{baseline_run_id}",
                output_path=webui_dir / "compare.html",
            )
            fetch_json(
                f"{base_url}/api/runs/{web_run_id}/report",
                output_path=webui_dir / "report.json",
                method="POST",
                payload={},
            )
            report_html = fetch_text(
                f"{base_url}/runs/{web_run_id}/report",
                output_path=webui_dir / "report.html",
            )
            saved_workflow = fetch_json(
                f"{base_url}/api/playground/runs/{web_run_id}/save-workflow",
                output_path=webui_dir / "save-workflow.json",
                method="POST",
                payload={"workflow_name": saved_workflow_name},
            )
            saved_profile = fetch_json(
                f"{base_url}/api/playground/runs/{web_run_id}/save-profile",
                output_path=webui_dir / "save-profile.json",
                method="POST",
                payload={"profile_name": saved_profile_name},
            )
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)

    web_session = load_json(web_run_dir / "sandbox_session.json")
    web_step_orders = [int(step["order"]) for step in web_session["inspection_steps"]]
    if "Loading the local-first app shell" not in playground_html:
        raise RuntimeError("Playground route did not return the app shell")
    if "Loading the local-first app shell" not in run_detail_html:
        raise RuntimeError("Playground run detail route did not return the app shell")
    if "Loading the local-first app shell" not in compare_html:
        raise RuntimeError("Playground compare route did not return the app shell")
    if "<html" not in report_html.lower():
        raise RuntimeError("Playground report route did not return HTML")
    if not health["ready"]:
        raise RuntimeError(f"WebUI playground server never reported ready: {health}")
    if snapshot["session"]["context_type"] != "workflow":
        raise RuntimeError(f"Unexpected initial playground session state: {snapshot['session']}")
    if not updated["session"]["ready_to_run"]:
        raise RuntimeError(f"Updated playground session should be ready to run: {updated['session']}")
    if last_result["labeling"]["classification"] != "exploratory":
        raise RuntimeError(f"WebUI playground run should stay exploratory: {last_result['labeling']}")
    if last_result["run"]["provider"] != "mock":
        raise RuntimeError(f"WebUI playground should stay provider-free: {last_result['run']}")
    if last_result["context"]["template_id"] != "provider-free-demo":
        raise RuntimeError(f"WebUI playground used unexpected template context: {last_result['context']}")
    if web_step_orders != sorted(web_step_orders):
        raise RuntimeError(f"WebUI inspection steps are not ordered: {web_session['inspection_steps']}")
    if web_session["save_back"]["workflow"]["saved_workflow_name"] != saved_workflow_name:
        raise RuntimeError(f"WebUI workflow save-back did not persist expected workflow: {web_session['save_back']}")
    if web_session["save_back"]["profile"]["saved_profile_name"] != saved_profile_name:
        raise RuntimeError(f"WebUI profile save-back did not persist expected profile: {web_session['save_back']}")
    if "Inspection is read-only" not in " ".join(updated["guidance"]["limitations"]):
        raise RuntimeError(f"WebUI playground guidance lost the read-only inspection contract: {updated['guidance']}")
    if compare["baseline_run_id"] != baseline_run_id:
        raise RuntimeError(f"Playground compare baseline mismatch: expected {baseline_run_id}, got {compare}")
    if run_detail["summary"]["status"] != "completed":
        raise RuntimeError(f"Playground run detail should show a completed run: {run_detail['summary']}")
    if saved_workflow["workflow"]["name"] != saved_workflow_name or not Path(saved_workflow["path"]).exists():
        raise RuntimeError(f"Playground workflow save-back failed: {saved_workflow}")
    if saved_profile["profile"]["name"] != saved_profile_name or not Path(saved_profile["path"]).exists():
        raise RuntimeError(f"Playground profile save-back failed: {saved_profile}")
    if saved_profile["profile"]["workflow_name"] != saved_workflow_name:
        raise RuntimeError(f"Playground profile save-back should reference the saved workflow: {saved_profile}")
    if not (web_run_dir / "report.html").exists():
        raise RuntimeError(f"WebUI playground report missing: {web_run_dir / 'report.html'}")

    run_logged(
        ["xrtm", "workflow", "validate", saved_workflow_name, "--workflows-dir", str(workflows_dir)],
        log_path=webui_dir / "workflow-validate-saved.log",
        cwd=journey_dir,
        env=env,
    )
    run_logged(
        ["xrtm", "profile", "show", saved_profile_name, "--profiles-dir", str(profiles_dir)],
        log_path=webui_dir / "profile-show-saved.log",
        cwd=journey_dir,
        env=env,
    )

    summary = {
        "baseline_run_id": baseline_run_id,
        "cli": {
            "run_id": cli_run_id,
            "provider": cli_session["run"]["provider"],
            "question_count": len(cli_session["questions"]),
            "inspection_step_ids": [step["node_id"] for step in cli_session["inspection_steps"]],
            "inspection_ordered": cli_step_orders == sorted(cli_step_orders),
            "inspection_mode": cli_session["labeling"]["inspection_mode"],
            "save_back_mode": cli_session["save_back"]["mode"],
            "report_exists": (cli_run_dir / "report.html").exists(),
        },
        "webui": {
            "run_id": web_run_id,
            "provider": last_result["run"]["provider"],
            "question_count": len(last_result["questions"]),
            "inspection_step_ids": [step["node_id"] for step in last_result["inspection_steps"]],
            "inspection_ordered": web_step_orders == sorted(web_step_orders),
            "playground_route_ok": "Loading the local-first app shell" in playground_html,
            "run_detail_route_ok": "Loading the local-first app shell" in run_detail_html,
            "compare_route_ok": "Loading the local-first app shell" in compare_html,
            "report_route_ok": "<html" in report_html.lower(),
            "saved_workflow_name": saved_workflow["workflow"]["name"],
            "saved_profile_name": saved_profile["profile"]["name"],
            "saved_profile_workflow_name": saved_profile["profile"]["workflow_name"],
            "health_ready": health["ready"],
        },
    }
    write_json(journey_dir / "summary.json", summary)
    return summary


def run_developer_package(
    *,
    workspace_root_path: Path,
    install_source: str,
    wheelhouse_dir: Path | None,
    artifacts_dir: Path,
    forecast_spec: str,
    xrtm_spec: str,
    base_env: dict[str, str],
    scratch_dir: Path,
) -> dict[str, Any]:
    journey_dir = artifacts_dir / "developer-package"
    prepare_artifacts_dir(journey_dir)
    logs_dir = journey_dir
    venv_dir = scratch_dir / "venvs" / "developer-package"
    venv_python = create_venv(venv_dir, logs_dir, base_env)
    env = venv_env(venv_python, base_env)
    install_specs(
        venv_python,
        install_source=install_source,
        wheelhouse_dir=wheelhouse_dir,
        specs=[forecast_spec, xrtm_spec],
        log_path=logs_dir / "install.log",
        env=base_env,
    )
    write_versions(venv_python, journey_dir / "installed-versions.txt", env)
    run_logged(
        [str(venv_python), str(workspace_root_path / "forecast" / "examples" / "providers" / "provider_free_analyst" / "run_provider_free_analyst.py")],
        log_path=journey_dir / "provider-free-analyst.log",
        cwd=journey_dir,
        env=env,
    )
    analyst_log = (journey_dir / "provider-free-analyst.log").read_text(encoding="utf-8")
    if "Schema validation failed" in analyst_log:
        raise RuntimeError("Provider-free analyst example surfaced schema validation failures")
    summary = {
        "forecast_version": next(
            line for line in (journey_dir / "installed-versions.txt").read_text(encoding="utf-8").splitlines() if line.startswith("forecast, version ")
        ),
        "xrtm_forecast_version": next(
            line for line in (journey_dir / "installed-versions.txt").read_text(encoding="utf-8").splitlines() if line.startswith("xrtm-forecast, version ")
        ),
        "schema_validation_failed": False,
    }
    write_json(journey_dir / "summary.json", summary)
    return summary


def run_product_shell(
    *,
    workspace_root_path: Path,
    xrtm_repo_root_path: Path,
    install_source: str,
    wheelhouse_dir: Path | None,
    artifacts_dir: Path,
    xrtm_spec: str,
    base_env: dict[str, str],
    scratch_dir: Path,
) -> dict[str, Any]:
    output_dir = artifacts_dir / "xrtm-release"
    prepare_artifacts_dir(output_dir)
    venv_dir = scratch_dir / "venvs" / "xrtm-release"
    venv_python = create_venv(venv_dir, output_dir, base_env)
    env = venv_env(venv_python, base_env)
    install_specs(
        venv_python,
        install_source=install_source,
        wheelhouse_dir=wheelhouse_dir,
        specs=[xrtm_spec],
        log_path=output_dir / "install.log",
        env=base_env,
    )
    write_versions(venv_python, output_dir / "installed-versions.txt", env)
    run_cli_surface_check(xrtm_repo_root_path, env, output_dir)
    run_release_claims(xrtm_repo_root_path, env, output_dir)
    summary = {
        "first_success": run_first_success(env, artifacts_dir),
        "workflow_authoring": run_workflow_authoring(env, artifacts_dir),
        "playground": run_playground(env, artifacts_dir),
        "operator": run_operator(env, artifacts_dir),
        "research_eval": run_research_eval(env, artifacts_dir),
        "benchmark_matrix": run_benchmark_matrix(env, artifacts_dir),
    }
    write_json(output_dir / "summary.json", summary)
    return summary


def run_host(args: argparse.Namespace) -> int:
    workspace_root_path = resolve_host_path(args.workspace_root, workspace_root())
    xrtm_repo_root_path = resolve_host_path(args.xrtm_repo_root, xrtm_repo_root())
    xrtm_spec, forecast_spec = default_specs(workspace_root_path, xrtm_repo_root_path)
    if args.xrtm_spec:
        xrtm_spec = args.xrtm_spec
    if args.forecast_spec:
        forecast_spec = args.forecast_spec
    artifacts_dir, managed_sandbox = prepare_host_artifacts_dir(
        args=args,
        workspace_root_path=workspace_root_path,
        repo_name="xrtm",
        purpose=f"docker-provider-free acceptance ({args.artifact_source})",
        default_dir_factory=default_artifacts_dir,
    )
    metadata_dir = artifacts_dir / "metadata"
    if managed_sandbox is not None:
        write_json(metadata_dir / "managed-sandbox.json", managed_sandbox.manifest)
    wheelhouse_dir = None
    if args.artifact_source == "wheelhouse":
        wheelhouse_dir = Path(args.wheelhouse_dir).resolve() if args.wheelhouse_dir else artifacts_dir / "wheelhouse"
        build_wheelhouse(workspace_root_path, wheelhouse_dir, metadata_dir / "wheelhouse", xrtm_repo_root_path)
    config = HostConfig(
        workspace_root=workspace_root_path,
        xrtm_repo_root=xrtm_repo_root_path,
        artifact_source=args.artifact_source,
        artifacts_dir=artifacts_dir,
        wheelhouse_dir=wheelhouse_dir,
        image_tag=args.image_tag,
        python_image=args.python_image,
        xrtm_spec=xrtm_spec,
        forecast_spec=forecast_spec,
    )
    request_payload = add_managed_sandbox_metadata(
        {
            "artifact_source": config.artifact_source,
            "artifacts_dir": str(config.artifacts_dir),
            "forecast_spec": config.forecast_spec,
            "image_tag": config.image_tag,
            "python_image": config.python_image,
            "wheelhouse_dir": str(config.wheelhouse_dir) if config.wheelhouse_dir is not None else None,
            "workspace_root": str(config.workspace_root),
            "xrtm_repo_root": str(config.xrtm_repo_root),
            "xrtm_spec": config.xrtm_spec,
        },
        managed_sandbox,
    )
    write_json(metadata_dir / "request.json", request_payload)
    run_logged(
        docker_build_command(xrtm_repo_root_path, config.image_tag, config.python_image),
        log_path=metadata_dir / "docker-build.log",
        cwd=workspace_root_path,
    )
    docker_command = docker_run_command(config)
    (metadata_dir / "docker-run-command.txt").write_text(command_text(docker_command) + "\n", encoding="utf-8")
    run_logged(docker_command, log_path=metadata_dir / "docker-run.log", cwd=workspace_root_path)
    summary_path = artifacts_dir / "summary.json"
    if summary_path.exists():
        summary = load_json(summary_path)
        add_managed_sandbox_metadata(summary, managed_sandbox)
        print(json.dumps(summary, indent=2, sort_keys=True))
        write_json(summary_path, summary)
    else:
        print(f"Docker acceptance completed; summary not found at {summary_path}")
    return 0


def run_inside(args: argparse.Namespace) -> int:
    workspace_root_path = Path(args.workspace_root)
    xrtm_repo_root_path = Path(args.xrtm_repo_root)
    artifacts_dir = Path(args.artifacts_dir)
    prepare_artifacts_dir(artifacts_dir)
    scratch_dir = artifacts_dir / "_scratch"
    home_dir = scratch_dir / "home"
    cache_dir = scratch_dir / "pip-cache"
    prepare_artifacts_dir(home_dir)
    prepare_artifacts_dir(cache_dir)
    base_env = dict(os.environ)
    base_env["HOME"] = str(home_dir)
    base_env["PIP_CACHE_DIR"] = str(cache_dir)
    base_env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    base_env["PYTHONFAULTHANDLER"] = "1"
    wheelhouse_dir = Path(args.wheelhouse_dir) if args.wheelhouse_dir else None
    write_json(
        artifacts_dir / "metadata" / "container-request.json",
        {
            "artifact_source": args.artifact_source,
            "artifacts_dir": str(artifacts_dir),
            "forecast_spec": args.forecast_spec,
            "wheelhouse_dir": str(wheelhouse_dir) if wheelhouse_dir is not None else None,
            "workspace_root": str(workspace_root_path),
            "xrtm_repo_root": str(xrtm_repo_root_path),
            "xrtm_spec": args.xrtm_spec,
        },
    )
    try:
        product_summary = run_product_shell(
            workspace_root_path=workspace_root_path,
            xrtm_repo_root_path=xrtm_repo_root_path,
            install_source=args.artifact_source,
            wheelhouse_dir=wheelhouse_dir,
            artifacts_dir=artifacts_dir,
            xrtm_spec=args.xrtm_spec,
            base_env=base_env,
            scratch_dir=scratch_dir,
        )
        developer_summary = run_developer_package(
            workspace_root_path=workspace_root_path,
            install_source=args.artifact_source,
            wheelhouse_dir=wheelhouse_dir,
            artifacts_dir=artifacts_dir,
            forecast_spec=args.forecast_spec,
            xrtm_spec=args.xrtm_spec,
            base_env=base_env,
            scratch_dir=scratch_dir,
        )
        summary = {
            "artifact_source": args.artifact_source,
            "developer_package": developer_summary,
            "status": "passed",
            "xrtm_release": product_summary,
        }
        write_json(artifacts_dir / "summary.json", summary)
        return 0
    finally:
        if scratch_dir.exists():
            shutil.rmtree(scratch_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode")

    host_parser = subparsers.add_parser("host")
    host_parser.add_argument("--artifact-source", choices=("wheelhouse", "pypi"), default="wheelhouse")
    host_parser.add_argument(
        "--artifacts-dir",
        help="Artifact output directory. With --managed-sandbox, this becomes the tracked sandbox path.",
    )
    host_parser.add_argument("--wheelhouse-dir")
    host_parser.add_argument("--workspace-root")
    host_parser.add_argument("--xrtm-repo-root")
    host_parser.add_argument("--image-tag", default=DEFAULT_IMAGE_TAG)
    host_parser.add_argument("--python-image", default=DEFAULT_PYTHON_IMAGE)
    host_parser.add_argument("--xrtm-spec")
    host_parser.add_argument("--forecast-spec")
    host_parser.add_argument(
        "--managed-sandbox",
        action="store_true",
        help="Track the host artifact root with the shared sandbox manager.",
    )
    host_parser.add_argument(
        "--sandbox-manager",
        help="Path to system-scripts/sandbox_manager.py. Defaults to ../system-scripts relative to the workspace root.",
    )
    host_parser.add_argument(
        "--sandbox-registry-root",
        help="Override SANDBOX_REGISTRY_ROOT for managed sandbox metadata and storage.",
    )
    host_parser.add_argument(
        "--sandbox-ttl-hours",
        type=float,
        default=DEFAULT_MANAGED_SANDBOX_TTL_HOURS,
        help="TTL for managed acceptance sandboxes before reap-stale can remove them.",
    )
    host_parser.add_argument(
        "--sandbox-cleanup-policy",
        choices=("delete", "archive", "manual"),
        default=DEFAULT_MANAGED_SANDBOX_CLEANUP_POLICY,
        help="Cleanup policy recorded for managed acceptance sandboxes.",
    )

    inside_parser = subparsers.add_parser("inside")
    inside_parser.add_argument("--workspace-root", required=True)
    inside_parser.add_argument("--xrtm-repo-root", required=True)
    inside_parser.add_argument("--artifacts-dir", required=True)
    inside_parser.add_argument("--artifact-source", choices=("wheelhouse", "pypi"), required=True)
    inside_parser.add_argument("--wheelhouse-dir")
    inside_parser.add_argument("--xrtm-spec", required=True)
    inside_parser.add_argument("--forecast-spec", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.mode == "inside":
        return run_inside(args)
    if args.mode not in {None, "host"}:
        parser.error(f"Unknown mode: {args.mode}")
    if args.mode is None:
        args.mode = "host"
        args.artifact_source = "wheelhouse"
        args.artifacts_dir = None
        args.wheelhouse_dir = None
        args.workspace_root = None
        args.xrtm_repo_root = None
        args.image_tag = DEFAULT_IMAGE_TAG
        args.python_image = DEFAULT_PYTHON_IMAGE
        args.xrtm_spec = None
        args.forecast_spec = None
    return run_host(args)


if __name__ == "__main__":
    raise SystemExit(main())
