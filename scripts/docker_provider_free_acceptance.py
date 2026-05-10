#!/usr/bin/env python3
"""Disposable Docker clean-room runner for provider-free acceptance."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

WORKSPACE_REPOS = ("data", "eval", "forecast", "train", "xrtm")
DEFAULT_IMAGE_TAG = "xrtm-provider-free-acceptance:py311"
DEFAULT_PYTHON_IMAGE = "python:3.11-slim"
CONTAINER_WORKSPACE_ROOT = Path("/workspace")


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


def load_project_version(repo_dir: Path) -> str:
    payload = tomllib.loads((repo_dir / "pyproject.toml").read_text(encoding="utf-8"))
    return payload["project"]["version"]


def default_specs(root: Path, xrtm_repo_root_path: Path | None = None) -> tuple[str, str]:
    xrtm_project_root = root / "xrtm"
    if xrtm_repo_root_path is not None and not xrtm_project_root.is_dir():
        xrtm_project_root = xrtm_repo_root_path
    return (
        f"xrtm=={load_project_version(xrtm_project_root)}",
        f"xrtm-forecast=={load_project_version(root / 'forecast')}",
    )


def command_text(command: Iterable[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
    log_path.write_text(f"$ {command_text(command)}\n\n{result.stdout}", encoding="utf-8")
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, command, output=result.stdout)
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


def total_forecast_count(runs_dir: Path) -> int:
    total = 0
    for run_id in discover_run_ids(runs_dir):
        summary_path = runs_dir / run_id / "run_summary.json"
        total += int(load_json(summary_path)["forecast_count"])
    return total


def build_wheelhouse(root: Path, wheelhouse_dir: Path, logs_dir: Path) -> None:
    prepare_empty_dir(wheelhouse_dir)
    for repo in WORKSPACE_REPOS:
        run_logged(
            ["uv", "build", "--wheel", "--python", "3.11", "--out-dir", str(wheelhouse_dir)],
            cwd=root / repo,
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


def venv_python_from_env(env: dict[str, str]) -> Path:
    first = env["PATH"].split(":", 1)[0]
    return Path(first) / "python"


def run_first_success(env: dict[str, str], artifacts_dir: Path) -> dict[str, Any]:
    journey_dir = artifacts_dir / "xrtm-release" / "first-success"
    prepare_artifacts_dir(journey_dir)
    runs_dir = journey_dir / "runs"
    run_logged(["xrtm", "doctor"], log_path=journey_dir / "doctor.log", cwd=journey_dir, env=env)
    run_logged(
        ["xrtm", "demo", "--provider", "mock", "--limit", "1", "--runs-dir", str(runs_dir)],
        log_path=journey_dir / "demo.log",
        cwd=journey_dir,
        env=env,
    )
    run_id = latest_run_id(runs_dir)
    run_dir = runs_dir / run_id
    run_logged(["xrtm", "runs", "list", "--runs-dir", str(runs_dir)], log_path=journey_dir / "runs-list.log", cwd=journey_dir, env=env)
    run_logged(
        ["xrtm", "runs", "show", run_id, "--runs-dir", str(runs_dir)],
        log_path=journey_dir / "runs-show.log",
        cwd=journey_dir,
        env=env,
    )
    run_logged(
        ["xrtm", "artifacts", "inspect", str(run_dir)],
        log_path=journey_dir / "artifacts-inspect.log",
        cwd=journey_dir,
        env=env,
    )
    run_logged(["xrtm", "report", "html", str(run_dir)], log_path=journey_dir / "report-html.log", cwd=journey_dir, env=env)
    run_logged(["xrtm", "web", "--runs-dir", str(runs_dir), "--smoke"], log_path=journey_dir / "web-smoke.log", cwd=journey_dir, env=env)
    summary = {
        "run_id": run_id,
        "status": load_json(run_dir / "run.json")["status"],
        "forecast_count": load_json(run_dir / "run_summary.json")["forecast_count"],
        "report_exists": (run_dir / "report.html").exists(),
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
    run_release_claims(xrtm_repo_root_path, env, output_dir)
    summary = {
        "first_success": run_first_success(env, artifacts_dir),
        "operator": run_operator(env, artifacts_dir),
        "research_eval": run_research_eval(env, artifacts_dir),
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
    artifacts_dir = Path(args.artifacts_dir).resolve() if args.artifacts_dir else default_artifacts_dir(workspace_root_path)
    prepare_artifacts_dir(artifacts_dir)
    metadata_dir = artifacts_dir / "metadata"
    wheelhouse_dir = None
    if args.artifact_source == "wheelhouse":
        wheelhouse_dir = Path(args.wheelhouse_dir).resolve() if args.wheelhouse_dir else artifacts_dir / "wheelhouse"
        build_wheelhouse(workspace_root_path, wheelhouse_dir, metadata_dir / "wheelhouse")
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
    write_json(
        metadata_dir / "request.json",
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
    )
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
        print(json.dumps(summary, indent=2, sort_keys=True))
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
    host_parser.add_argument("--artifacts-dir")
    host_parser.add_argument("--wheelhouse-dir")
    host_parser.add_argument("--workspace-root")
    host_parser.add_argument("--xrtm-repo-root")
    host_parser.add_argument("--image-tag", default=DEFAULT_IMAGE_TAG)
    host_parser.add_argument("--python-image", default=DEFAULT_PYTHON_IMAGE)
    host_parser.add_argument("--xrtm-spec")
    host_parser.add_argument("--forecast-spec")

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
