#!/usr/bin/env python3
"""Disposable Docker clean-room runner for local-LLM acceptance."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from docker_provider_free_acceptance import (  # noqa: E402
    build_wheelhouse,
    container_workspace_path,
    command_text,
    create_venv,
    default_specs,
    install_specs,
    latest_run_id,
    load_json,
    prepare_artifacts_dir,
    resolve_host_path,
    run_logged,
    run_release_claims,
    venv_env,
    write_json,
    write_versions,
)

DEFAULT_IMAGE_TAG = "xrtm-local-llm-acceptance:py311"
DEFAULT_PYTHON_IMAGE = "python:3.11-slim"
DEFAULT_LLAMA_CPP_IMAGE = "ghcr.io/ggml-org/llama.cpp:server-cuda"
DEFAULT_LLAMA_CPP_MODEL = "Qwen3.5-27B-Q4_K_M.gguf"
DEFAULT_LOCAL_LLM_API_KEY = "test"
DEFAULT_LOCAL_LLM_MAX_TOKENS = 768
DEFAULT_LLAMA_CPP_PORT = 8080
DEFAULT_LLAMA_CPP_CTX_SIZE = 65536
DEFAULT_READY_TIMEOUT_SECONDS = 600
DEFAULT_READY_INTERVAL_SECONDS = 5
DEFAULT_PERF_ITERATIONS = 1


@dataclass(frozen=True)
class HostConfig:
    workspace_root: Path
    xrtm_repo_root: Path
    artifact_source: str
    artifacts_dir: Path
    wheelhouse_dir: Path
    image_tag: str
    python_image: str
    xrtm_spec: str
    project_name: str
    llama_image: str
    llama_model_dir: Path
    llama_model_file: str
    local_llm_base_url: str
    local_llm_model: str
    local_llm_api_key: str
    local_llm_max_tokens: int
    llama_port: int
    llama_ctx_size: int
    ready_timeout_seconds: int
    ready_interval_seconds: int
    perf_iterations: int


def script_path() -> Path:
    return Path(__file__).resolve()


def workspace_root() -> Path:
    return script_path().parents[2]


def xrtm_repo_root() -> Path:
    return script_path().parents[1]


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def default_artifacts_dir(root: Path, timestamp: str | None = None) -> Path:
    return root / "acceptance-studies" / "docker-local-llm" / (timestamp or utc_timestamp())


def default_llama_model_dir(root: Path) -> Path:
    return root.parent / "models"


def compose_project_name(timestamp: str | None = None) -> str:
    return f"xrtm-local-llm-{(timestamp or utc_timestamp()).lower()}-{os.getpid()}"


def local_llm_base_url(*, port: int) -> str:
    return f"http://llama-cpp:{port}/v1"


def docker_build_command(repo_root: Path, image_tag: str, python_image: str) -> list[str]:
    return [
        "docker",
        "build",
        "-f",
        str(repo_root / "docker" / "local-llm-acceptance.Dockerfile"),
        "-t",
        image_tag,
        "--build-arg",
        f"PYTHON_IMAGE={python_image}",
        str(repo_root),
    ]


def compose_file(repo_root: Path) -> Path:
    return repo_root / "docker" / "local-llm-acceptance.compose.yml"


def docker_compose_command(repo_root: Path, project_name: str, env_file: Path, *compose_args: str) -> list[str]:
    return [
        "docker",
        "compose",
        "--project-name",
        project_name,
        "-f",
        str(compose_file(repo_root)),
        "--env-file",
        str(env_file),
        *compose_args,
    ]


def compose_environment(config: HostConfig) -> dict[str, str]:
    container_xrtm_repo_root = container_workspace_path(config.xrtm_repo_root, config.workspace_root)
    return {
        "XRTM_ACCEPTANCE_UID": str(os.getuid()),
        "XRTM_ACCEPTANCE_GID": str(os.getgid()),
        "XRTM_ACCEPTANCE_IMAGE": config.image_tag,
        "XRTM_ARTIFACT_SOURCE": config.artifact_source,
        "XRTM_ARTIFACTS_DIR": str(config.artifacts_dir),
        "XRTM_LLAMA_CPP_CTX_SIZE": str(config.llama_ctx_size),
        "XRTM_LLAMA_CPP_IMAGE": config.llama_image,
        "XRTM_LLAMA_CPP_MODEL_DIR": str(config.llama_model_dir),
        "XRTM_LLAMA_CPP_MODEL_FILE": config.llama_model_file,
        "XRTM_LLAMA_CPP_PORT": str(config.llama_port),
        "XRTM_LOCAL_LLM_API_KEY": config.local_llm_api_key,
        "XRTM_LOCAL_LLM_BASE_URL": config.local_llm_base_url,
        "XRTM_LOCAL_LLM_MAX_TOKENS": str(config.local_llm_max_tokens),
        "XRTM_LOCAL_LLM_MODEL": config.local_llm_model,
        "XRTM_LOCAL_LLM_PERF_ITERATIONS": str(config.perf_iterations),
        "XRTM_LOCAL_LLM_READY_INTERVAL_SECONDS": str(config.ready_interval_seconds),
        "XRTM_LOCAL_LLM_READY_TIMEOUT_SECONDS": str(config.ready_timeout_seconds),
        "XRTM_REPO_ROOT_IN_WORKSPACE": str(container_xrtm_repo_root),
        "XRTM_SPEC": config.xrtm_spec,
        "XRTM_WHEELHOUSE_DIR": str(config.wheelhouse_dir),
        "XRTM_WORKSPACE_ROOT": str(config.workspace_root),
    }


def write_compose_env(path: Path, payload: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key}={value}" for key, value in sorted(payload.items())]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def best_effort_logged(
    command: list[str],
    *,
    log_path: Path,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> None:
    try:
        run_logged(command, log_path=log_path, cwd=cwd, env=env)
    except subprocess.CalledProcessError:
        pass


def _read_json_url(url: str, *, timeout: int) -> Any:
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body else {}


def wait_for_local_llm(
    *,
    base_url: str,
    expected_model: str,
    timeout_seconds: int,
    interval_seconds: int,
    log_path: Path,
) -> dict[str, Any]:
    health_url = f"{base_url.removesuffix('/v1')}/health"
    models_url = f"{base_url}/models"
    started = time.monotonic()
    attempts: list[dict[str, Any]] = []
    while True:
        elapsed_seconds = round(time.monotonic() - started, 3)
        try:
            _read_json_url(health_url, timeout=5)
            models_payload = _read_json_url(models_url, timeout=5)
            models = [
                item.get("id", str(item))
                for item in (models_payload.get("data", []) if isinstance(models_payload, dict) else [])
                if isinstance(item, dict)
            ]
            if not models:
                raise RuntimeError("endpoint is healthy but /models is still empty")
            if expected_model not in models:
                raise RuntimeError(f"endpoint models {models} do not include expected model {expected_model}")
            status = {
                "base_url": base_url,
                "elapsed_seconds": elapsed_seconds,
                "expected_model": expected_model,
                "healthy": True,
                "models": models,
            }
            write_json(log_path, {"attempts": attempts, "status": status})
            return status
        except (OSError, URLError, TimeoutError, ValueError, RuntimeError) as exc:
            attempts.append({"elapsed_seconds": elapsed_seconds, "error": str(exc)})
            if elapsed_seconds >= timeout_seconds:
                write_json(
                    log_path,
                    {
                        "attempts": attempts,
                        "status": {
                            "base_url": base_url,
                            "expected_model": expected_model,
                            "healthy": False,
                        },
                    },
                )
                raise RuntimeError(
                    f"Local llama.cpp endpoint at {base_url} was not ready within {timeout_seconds} seconds"
                ) from exc
            time.sleep(interval_seconds)


def run_local_llm_release_smoke(
    *,
    env: dict[str, str],
    artifacts_dir: Path,
    base_url: str,
    model: str,
    api_key: str,
    max_tokens: int,
    perf_iterations: int,
    ready_status: dict[str, Any],
) -> dict[str, Any]:
    journey_dir = artifacts_dir / "xrtm-release-local-llm"
    prepare_artifacts_dir(journey_dir)
    runs_dir = journey_dir / "runs"
    run_logged(["xrtm", "local-llm", "status", "--base-url", base_url], log_path=journey_dir / "local-llm-status.log", cwd=journey_dir, env=env)
    run_logged(
        [
            "xrtm",
            "demo",
            "--provider",
            "local-llm",
            "--base-url",
            base_url,
            "--model",
            model,
            "--api-key",
            api_key,
            "--limit",
            "1",
            "--max-tokens",
            str(max_tokens),
            "--runs-dir",
            str(runs_dir),
        ],
        log_path=journey_dir / "demo.log",
        cwd=journey_dir,
        env=env,
    )
    run_id = latest_run_id(runs_dir)
    run_dir = runs_dir / run_id
    report_path = run_dir / "report.html"
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
    if report_path.exists():
        best_effort_logged(["xrtm", "report", "html", str(run_dir)], log_path=journey_dir / "report-html.log", cwd=journey_dir, env=env)
    else:
        run_logged(["xrtm", "report", "html", str(run_dir)], log_path=journey_dir / "report-html.log", cwd=journey_dir, env=env)
    run_logged(["xrtm", "web", "--runs-dir", str(runs_dir), "--smoke"], log_path=journey_dir / "web-smoke.log", cwd=journey_dir, env=env)
    run_logged(
        [
            "xrtm",
            "perf",
            "run",
            "--scenario",
            "local-llm-smoke",
            "--iterations",
            str(perf_iterations),
            "--limit",
            "1",
            "--runs-dir",
            "runs-perf",
            "--output",
            "performance.json",
            "--base-url",
            base_url,
            "--model",
            model,
            "--api-key",
            api_key,
            "--max-tokens",
            str(max_tokens),
        ],
        log_path=journey_dir / "perf-run.log",
        cwd=journey_dir,
        env=env,
    )
    performance = load_json(journey_dir / "performance.json")
    summary = {
        "base_url": base_url,
        "forecast_count": load_json(run_dir / "run_summary.json")["forecast_count"],
        "models": ready_status["models"],
        "perf_iterations": performance["iterations"],
        "perf_mean_seconds": performance["summary"]["mean_seconds"],
        "report_exists": report_path.exists(),
        "run_id": run_id,
        "status": load_json(run_dir / "run.json")["status"],
    }
    write_json(journey_dir / "summary.json", summary)
    return summary


def run_host(args: argparse.Namespace) -> int:
    workspace_root_path = resolve_host_path(args.workspace_root, workspace_root())
    xrtm_repo_root_path = resolve_host_path(args.xrtm_repo_root, xrtm_repo_root())
    xrtm_spec, _ = default_specs(workspace_root_path, xrtm_repo_root_path)
    if args.xrtm_spec:
        xrtm_spec = args.xrtm_spec
    artifacts_dir = Path(args.artifacts_dir).resolve() if args.artifacts_dir else default_artifacts_dir(workspace_root_path)
    prepare_artifacts_dir(artifacts_dir)
    metadata_dir = artifacts_dir / "metadata"
    wheelhouse_dir = Path(args.wheelhouse_dir).resolve() if args.wheelhouse_dir else artifacts_dir / "wheelhouse"
    prepare_artifacts_dir(wheelhouse_dir)
    if args.artifact_source == "wheelhouse":
        build_wheelhouse(workspace_root_path, wheelhouse_dir, metadata_dir / "wheelhouse")
    llama_model_dir = Path(args.llama_model_dir).resolve() if args.llama_model_dir else default_llama_model_dir(workspace_root_path)
    llama_model_file = args.llama_model_file or DEFAULT_LLAMA_CPP_MODEL
    llama_model_path = llama_model_dir / llama_model_file
    if not llama_model_path.is_file():
        raise FileNotFoundError(f"Local llama.cpp model not found: {llama_model_path}")
    local_model = args.local_llm_model or llama_model_file
    timestamp = utc_timestamp()
    config = HostConfig(
        workspace_root=workspace_root_path,
        xrtm_repo_root=xrtm_repo_root_path,
        artifact_source=args.artifact_source,
        artifacts_dir=artifacts_dir,
        wheelhouse_dir=wheelhouse_dir,
        image_tag=args.image_tag,
        python_image=args.python_image,
        xrtm_spec=xrtm_spec,
        project_name=compose_project_name(timestamp),
        llama_image=args.llama_image,
        llama_model_dir=llama_model_dir,
        llama_model_file=llama_model_file,
        local_llm_base_url=local_llm_base_url(port=args.llama_port),
        local_llm_model=local_model,
        local_llm_api_key=args.local_llm_api_key,
        local_llm_max_tokens=args.max_tokens,
        llama_port=args.llama_port,
        llama_ctx_size=args.llama_ctx_size,
        ready_timeout_seconds=args.ready_timeout_seconds,
        ready_interval_seconds=args.ready_interval_seconds,
        perf_iterations=args.perf_iterations,
    )
    write_json(
        metadata_dir / "request.json",
        {
            "artifact_source": config.artifact_source,
            "artifacts_dir": str(config.artifacts_dir),
            "image_tag": config.image_tag,
            "llama_ctx_size": config.llama_ctx_size,
            "llama_image": config.llama_image,
            "llama_model_dir": str(config.llama_model_dir),
            "llama_model_file": config.llama_model_file,
            "local_llm_base_url": config.local_llm_base_url,
            "local_llm_max_tokens": config.local_llm_max_tokens,
            "local_llm_model": config.local_llm_model,
            "perf_iterations": config.perf_iterations,
            "project_name": config.project_name,
            "python_image": config.python_image,
            "ready_interval_seconds": config.ready_interval_seconds,
            "ready_timeout_seconds": config.ready_timeout_seconds,
            "wheelhouse_dir": str(config.wheelhouse_dir),
            "workspace_root": str(config.workspace_root),
            "xrtm_repo_root": str(config.xrtm_repo_root),
            "xrtm_spec": config.xrtm_spec,
        },
    )
    env_file = metadata_dir / "compose.env"
    write_compose_env(env_file, compose_environment(config))
    run_logged(
        docker_build_command(xrtm_repo_root_path, config.image_tag, config.python_image),
        log_path=metadata_dir / "docker-build.log",
        cwd=workspace_root_path,
    )
    compose_config_command = docker_compose_command(xrtm_repo_root_path, config.project_name, env_file, "config")
    (metadata_dir / "docker-compose-config-command.txt").write_text(command_text(compose_config_command) + "\n", encoding="utf-8")
    run_logged(compose_config_command, log_path=metadata_dir / "docker-compose-config.log", cwd=workspace_root_path)
    compose_up_command = docker_compose_command(
        xrtm_repo_root_path,
        config.project_name,
        env_file,
        "up",
        "--abort-on-container-exit",
        "--exit-code-from",
        "acceptance",
    )
    (metadata_dir / "docker-compose-up-command.txt").write_text(command_text(compose_up_command) + "\n", encoding="utf-8")
    try:
        run_logged(compose_up_command, log_path=metadata_dir / "docker-compose-up.log", cwd=workspace_root_path)
    finally:
        best_effort_logged(
            docker_compose_command(xrtm_repo_root_path, config.project_name, env_file, "logs", "--no-color"),
            log_path=metadata_dir / "docker-compose-logs.log",
            cwd=workspace_root_path,
        )
        best_effort_logged(
            docker_compose_command(xrtm_repo_root_path, config.project_name, env_file, "down", "--remove-orphans"),
            log_path=metadata_dir / "docker-compose-down.log",
            cwd=workspace_root_path,
        )
    summary_path = artifacts_dir / "summary.json"
    if summary_path.exists():
        print(json.dumps(load_json(summary_path), indent=2, sort_keys=True))
    else:
        print(f"Local-LLM Docker acceptance completed; summary not found at {summary_path}")
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
            "local_llm_base_url": args.local_llm_base_url,
            "local_llm_model": args.local_llm_model,
            "max_tokens": args.max_tokens,
            "perf_iterations": args.perf_iterations,
            "ready_interval_seconds": args.ready_interval_seconds,
            "ready_timeout_seconds": args.ready_timeout_seconds,
            "wheelhouse_dir": str(wheelhouse_dir) if wheelhouse_dir is not None else None,
            "workspace_root": str(workspace_root_path),
            "xrtm_repo_root": str(xrtm_repo_root_path),
            "xrtm_spec": args.xrtm_spec,
        },
    )
    try:
        venv_dir = scratch_dir / "venvs" / "xrtm-release-local-llm"
        output_dir = artifacts_dir / "xrtm-release-local-llm"
        prepare_artifacts_dir(output_dir)
        venv_python = create_venv(venv_dir, output_dir, base_env)
        env = venv_env(venv_python, base_env)
        env.update(
            {
                "XRTM_LOCAL_LLM_API_KEY": args.local_llm_api_key,
                "XRTM_LOCAL_LLM_BASE_URL": args.local_llm_base_url,
                "XRTM_LOCAL_LLM_MAX_TOKENS": str(args.max_tokens),
                "XRTM_LOCAL_LLM_MODEL": args.local_llm_model,
            }
        )
        install_specs(
            venv_python,
            install_source=args.artifact_source,
            wheelhouse_dir=wheelhouse_dir,
            specs=[args.xrtm_spec],
            log_path=output_dir / "install.log",
            env=base_env,
        )
        write_versions(venv_python, output_dir / "installed-versions.txt", env)
        ready_status = wait_for_local_llm(
            base_url=args.local_llm_base_url,
            expected_model=args.local_llm_model,
            timeout_seconds=args.ready_timeout_seconds,
            interval_seconds=args.ready_interval_seconds,
            log_path=artifacts_dir / "metadata" / "local-llm-ready.json",
        )
        run_release_claims(xrtm_repo_root_path, env, output_dir)
        release_summary = run_local_llm_release_smoke(
            env=env,
            artifacts_dir=artifacts_dir,
            base_url=args.local_llm_base_url,
            model=args.local_llm_model,
            api_key=args.local_llm_api_key,
            max_tokens=args.max_tokens,
            perf_iterations=args.perf_iterations,
            ready_status=ready_status,
        )
        summary = {
            "artifact_source": args.artifact_source,
            "llama_cpp": ready_status,
            "status": "passed",
            "xrtm_release_local_llm": release_summary,
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
    host_parser.add_argument("--llama-image", default=DEFAULT_LLAMA_CPP_IMAGE)
    host_parser.add_argument("--llama-model-dir")
    host_parser.add_argument("--llama-model-file", default=DEFAULT_LLAMA_CPP_MODEL)
    host_parser.add_argument("--local-llm-model", default=None)
    host_parser.add_argument("--local-llm-api-key", default=DEFAULT_LOCAL_LLM_API_KEY)
    host_parser.add_argument("--max-tokens", type=int, default=DEFAULT_LOCAL_LLM_MAX_TOKENS)
    host_parser.add_argument("--llama-port", type=int, default=DEFAULT_LLAMA_CPP_PORT)
    host_parser.add_argument("--llama-ctx-size", type=int, default=DEFAULT_LLAMA_CPP_CTX_SIZE)
    host_parser.add_argument("--ready-timeout-seconds", type=int, default=DEFAULT_READY_TIMEOUT_SECONDS)
    host_parser.add_argument("--ready-interval-seconds", type=int, default=DEFAULT_READY_INTERVAL_SECONDS)
    host_parser.add_argument("--perf-iterations", type=int, default=DEFAULT_PERF_ITERATIONS)

    inside_parser = subparsers.add_parser("inside")
    inside_parser.add_argument("--workspace-root", required=True)
    inside_parser.add_argument("--xrtm-repo-root", required=True)
    inside_parser.add_argument("--artifacts-dir", required=True)
    inside_parser.add_argument("--artifact-source", choices=("wheelhouse", "pypi"), required=True)
    inside_parser.add_argument("--wheelhouse-dir")
    inside_parser.add_argument("--xrtm-spec", required=True)
    inside_parser.add_argument("--local-llm-base-url", required=True)
    inside_parser.add_argument("--local-llm-model", required=True)
    inside_parser.add_argument("--local-llm-api-key", required=True)
    inside_parser.add_argument("--max-tokens", type=int, required=True)
    inside_parser.add_argument("--ready-timeout-seconds", type=int, required=True)
    inside_parser.add_argument("--ready-interval-seconds", type=int, required=True)
    inside_parser.add_argument("--perf-iterations", type=int, required=True)

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
        args.llama_image = DEFAULT_LLAMA_CPP_IMAGE
        args.llama_model_dir = None
        args.llama_model_file = DEFAULT_LLAMA_CPP_MODEL
        args.local_llm_model = None
        args.local_llm_api_key = DEFAULT_LOCAL_LLM_API_KEY
        args.max_tokens = DEFAULT_LOCAL_LLM_MAX_TOKENS
        args.llama_port = DEFAULT_LLAMA_CPP_PORT
        args.llama_ctx_size = DEFAULT_LLAMA_CPP_CTX_SIZE
        args.ready_timeout_seconds = DEFAULT_READY_TIMEOUT_SECONDS
        args.ready_interval_seconds = DEFAULT_READY_INTERVAL_SECONDS
        args.perf_iterations = DEFAULT_PERF_ITERATIONS
    return run_host(args)


if __name__ == "__main__":
    raise SystemExit(main())
