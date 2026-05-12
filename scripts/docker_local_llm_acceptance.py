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
    command_text,
    container_workspace_path,
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
DEFAULT_LLAMA_CPP_MODEL = "Qwen3.5-9B-UD-Q4_K_XL.gguf"
DEFAULT_LOCAL_LLM_API_KEY = "test"
DEFAULT_LOCAL_LLM_MAX_TOKENS = 768
DEFAULT_LOCAL_LLM_TIMEOUT_SECONDS = 180
DEFAULT_LLAMA_CPP_PORT = 8080
DEFAULT_LLAMA_CPP_CTX_SIZE = 8192
DEFAULT_LLAMA_CPP_PARALLEL = 1
DEFAULT_READY_TIMEOUT_SECONDS = 600
DEFAULT_READY_INTERVAL_SECONDS = 5
DEFAULT_PERF_ITERATIONS = 1
DEFAULT_VALIDATION_PROFILE = "smoke"
DEFAULT_BENCHMARK_LIMIT = 5
DEFAULT_BENCHMARK_REPEATS = 2
DEFAULT_GPU_SAMPLE_INTERVAL_SECONDS = 1.0
DEFAULT_RELEASE_MIN_GPU_BENCHMARK_SECONDS = 1800
DEFAULT_RELEASE_MIN_GPU_ACTIVE_SAMPLES = 60
DEFAULT_RELEASE_MIN_GPU_MEMORY_MIB = 4096


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
    local_llm_timeout_seconds: int
    llama_port: int
    llama_ctx_size: int
    llama_parallel: int
    ready_timeout_seconds: int
    ready_interval_seconds: int
    perf_iterations: int
    validation_profile: str
    benchmark_limit: int
    benchmark_repeats: int
    gpu_sample_interval_seconds: float
    min_gpu_benchmark_seconds: int
    min_gpu_active_samples: int
    min_gpu_memory_mib: int


@dataclass(frozen=True)
class ValidationProfileConfig:
    perf_iterations: int
    benchmark_limit: int
    benchmark_repeats: int
    min_gpu_benchmark_seconds: int
    min_gpu_active_samples: int
    min_gpu_memory_mib: int


VALIDATION_PROFILES = {
    "smoke": ValidationProfileConfig(
        perf_iterations=1,
        benchmark_limit=3,
        benchmark_repeats=1,
        min_gpu_benchmark_seconds=0,
        min_gpu_active_samples=0,
        min_gpu_memory_mib=0,
    ),
    "release": ValidationProfileConfig(
        perf_iterations=10,
        benchmark_limit=25,
        benchmark_repeats=4,
        min_gpu_benchmark_seconds=DEFAULT_RELEASE_MIN_GPU_BENCHMARK_SECONDS,
        min_gpu_active_samples=DEFAULT_RELEASE_MIN_GPU_ACTIVE_SAMPLES,
        min_gpu_memory_mib=DEFAULT_RELEASE_MIN_GPU_MEMORY_MIB,
    ),
}


def script_path() -> Path:
    return Path(__file__).resolve()


def workspace_root() -> Path:
    return script_path().parents[2]


def xrtm_repo_root() -> Path:
    return script_path().parents[1]


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
        "XRTM_LLAMA_CPP_PARALLEL": str(config.llama_parallel),
        "XRTM_LLAMA_CPP_PORT": str(config.llama_port),
        "XRTM_LOCAL_LLM_API_KEY": config.local_llm_api_key,
        "XRTM_LOCAL_LLM_BASE_URL": config.local_llm_base_url,
        "XRTM_LOCAL_LLM_BENCHMARK_LIMIT": str(config.benchmark_limit),
        "XRTM_LOCAL_LLM_MAX_TOKENS": str(config.local_llm_max_tokens),
        "XRTM_LOCAL_LLM_MODEL": config.local_llm_model,
        "XRTM_LOCAL_LLM_TIMEOUT_SECONDS": str(config.local_llm_timeout_seconds),
        "XRTM_LOCAL_LLM_PERF_ITERATIONS": str(config.perf_iterations),
        "XRTM_LOCAL_LLM_READY_INTERVAL_SECONDS": str(config.ready_interval_seconds),
        "XRTM_LOCAL_LLM_READY_TIMEOUT_SECONDS": str(config.ready_timeout_seconds),
        "XRTM_LOCAL_LLM_STRESS_REPEATS": str(config.benchmark_repeats),
        "XRTM_LOCAL_LLM_VALIDATION_PROFILE": config.validation_profile,
        "XRTM_REPO_ROOT_IN_WORKSPACE": str(container_xrtm_repo_root),
        "XRTM_SPEC": config.xrtm_spec,
        "XRTM_WHEELHOUSE_DIR": str(config.wheelhouse_dir),
        "XRTM_WORKSPACE_ROOT": str(config.workspace_root),
    }


def write_compose_env(path: Path, payload: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key}={value}" for key, value in sorted(payload.items())]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def nvidia_smi_available() -> bool:
    result = subprocess.run(["nvidia-smi", "--help"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    return result.returncode == 0


def gpu_telemetry_command(*, output_path: Path, interval_seconds: float) -> list[str]:
    return [
        sys.executable,
        str(script_path()),
        "sample-gpu",
        "--output",
        str(output_path),
        "--interval-seconds",
        str(interval_seconds),
    ]


def start_gpu_telemetry_sampler(
    *,
    output_path: Path,
    interval_seconds: float,
    log_path: Path,
) -> subprocess.Popen[str]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = gpu_telemetry_command(output_path=output_path, interval_seconds=interval_seconds)
    log_path.write_text(f"$ {command_text(command)}\n\n", encoding="utf-8")
    handle = log_path.open("a", encoding="utf-8")
    process = subprocess.Popen(command, stdout=handle, stderr=subprocess.STDOUT, text=True)
    process._xrtm_log_handle = handle  # type: ignore[attr-defined]
    return process


def stop_gpu_telemetry_sampler(process: subprocess.Popen[str] | None) -> None:
    if process is None:
        return
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    handle = getattr(process, "_xrtm_log_handle", None)
    if handle is not None:
        handle.close()


def sample_gpu_once() -> dict[str, Any]:
    timestamp = utc_now_iso()
    command = [
        "nvidia-smi",
        "--query-gpu=index,name,memory.used,memory.total,utilization.gpu,utilization.memory,temperature.gpu,power.draw",
        "--format=csv,noheader,nounits",
    ]
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if result.returncode != 0:
        return {"timestamp": timestamp, "error": result.stdout.strip() or f"nvidia-smi exited with {result.returncode}"}
    gpus = []
    for line in result.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 8:
            continue
        gpus.append(
            {
                "index": _int_or_none(parts[0]),
                "name": parts[1],
                "memory_used_mib": _int_or_none(parts[2]),
                "memory_total_mib": _int_or_none(parts[3]),
                "utilization_gpu_percent": _int_or_none(parts[4]),
                "utilization_memory_percent": _int_or_none(parts[5]),
                "temperature_celsius": _int_or_none(parts[6]),
                "power_draw_watts": _float_or_none(parts[7]),
            }
        )
    return {"timestamp": timestamp, "gpus": gpus}


def run_gpu_sampler(*, output_path: Path, interval_seconds: float) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    while True:
        with output_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(sample_gpu_once(), sort_keys=True) + "\n")
        time.sleep(interval_seconds)


def summarize_gpu_telemetry(path: Path, *, start_time: str | None = None, end_time: str | None = None) -> dict[str, Any]:
    if not path.exists():
        return {
            "available": False,
            "sample_count": 0,
            "duration_seconds": 0.0,
            "active_sample_count": 0,
            "active_ratio": 0.0,
            "peak_memory_used_mib": 0,
            "peak_utilization_gpu_percent": 0,
            "mean_utilization_gpu_percent": 0.0,
        }
    start_dt = _parse_iso8601(start_time) if start_time else None
    end_dt = _parse_iso8601(end_time) if end_time else None
    samples = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        payload = json.loads(raw_line)
        sample_dt = _parse_iso8601(payload.get("timestamp"))
        if sample_dt is None:
            continue
        if start_dt is not None and sample_dt < start_dt:
            continue
        if end_dt is not None and sample_dt > end_dt:
            continue
        samples.append(payload)
    if not samples:
        return {
            "available": True,
            "sample_count": 0,
            "duration_seconds": 0.0,
            "active_sample_count": 0,
            "active_ratio": 0.0,
            "peak_memory_used_mib": 0,
            "peak_utilization_gpu_percent": 0,
            "mean_utilization_gpu_percent": 0.0,
        }
    first_dt = _parse_iso8601(samples[0].get("timestamp"))
    last_dt = _parse_iso8601(samples[-1].get("timestamp"))
    duration_seconds = (last_dt - first_dt).total_seconds() if first_dt is not None and last_dt is not None else 0.0
    utilization_values: list[int] = []
    memory_values: list[int] = []
    active_sample_count = 0
    for sample in samples:
        gpus = sample.get("gpus", [])
        sample_active = False
        for gpu in gpus:
            util = int(gpu.get("utilization_gpu_percent") or 0)
            memory_used = int(gpu.get("memory_used_mib") or 0)
            utilization_values.append(util)
            memory_values.append(memory_used)
            if util > 0:
                sample_active = True
        if sample_active:
            active_sample_count += 1
    sample_count = len(samples)
    return {
        "available": True,
        "sample_count": sample_count,
        "duration_seconds": round(duration_seconds, 3),
        "active_sample_count": active_sample_count,
        "active_ratio": round(active_sample_count / sample_count, 3) if sample_count else 0.0,
        "peak_memory_used_mib": max(memory_values, default=0),
        "peak_utilization_gpu_percent": max(utilization_values, default=0),
        "mean_utilization_gpu_percent": round(sum(utilization_values) / len(utilization_values), 3)
        if utilization_values
        else 0.0,
    }


def validate_gpu_summary(
    summary: dict[str, Any],
    *,
    min_benchmark_seconds: int,
    min_active_samples: int,
    min_memory_mib: int,
) -> list[str]:
    failures: list[str] = []
    if not summary.get("available"):
        failures.append("gpu telemetry is unavailable")
        return failures
    if min_benchmark_seconds and float(summary.get("duration_seconds", 0.0)) < min_benchmark_seconds:
        failures.append(
            f"gpu benchmark window {summary.get('duration_seconds', 0.0):.1f}s is below required {min_benchmark_seconds}s"
        )
    if min_active_samples and int(summary.get("active_sample_count", 0)) < min_active_samples:
        failures.append(
            f"gpu active samples {summary.get('active_sample_count', 0)} are below required {min_active_samples}"
        )
    if min_memory_mib and int(summary.get("peak_memory_used_mib", 0)) < min_memory_mib:
        failures.append(
            f"gpu peak memory {summary.get('peak_memory_used_mib', 0)} MiB is below required {min_memory_mib} MiB"
        )
    return failures


def _parse_iso8601(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _int_or_none(value: str) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _float_or_none(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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


def _post_json_url(url: str, *, payload: dict[str, Any], timeout: int, api_key: str) -> Any:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
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


def warm_up_local_llm(
    *,
    base_url: str,
    model: str,
    api_key: str,
    timeout_seconds: int,
    log_path: Path,
) -> dict[str, Any]:
    started = time.monotonic()
    response = _post_json_url(
        f"{base_url}/chat/completions",
        payload={
            "model": model,
            "messages": [{"role": "user", "content": "Reply with exactly XRTM_WARMUP_OK and no other text."}],
            "max_tokens": 32,
            "temperature": 0,
        },
        timeout=timeout_seconds,
        api_key=api_key,
    )
    choices = response.get("choices", []) if isinstance(response, dict) else []
    message = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
    content = message.get("content", "") if isinstance(message, dict) else ""
    result = {
        "base_url": base_url,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "model": model,
        "response_preview": content[:200],
        "usage": response.get("usage", {}) if isinstance(response, dict) else {},
    }
    write_json(log_path, result)
    return result


def run_local_llm_release_smoke(
    *,
    env: dict[str, str],
    artifacts_dir: Path,
    base_url: str,
    model: str,
    api_key: str,
    max_tokens: int,
    timeout_seconds: int,
    perf_iterations: int,
    benchmark_limit: int,
    benchmark_repeats: int,
    validation_profile: str,
    ready_status: dict[str, Any],
) -> dict[str, Any]:
    journey_dir = artifacts_dir / "xrtm-release-local-llm"
    prepare_artifacts_dir(journey_dir)
    runs_dir = journey_dir / "runs"
    benchmark_runs_dir = journey_dir / "runs-benchmark"
    competition_runs_dir = journey_dir / "runs-competition"
    benchmark_output_dir = journey_dir / "benchmark-output"
    metadata_dir = artifacts_dir / "metadata"
    run_logged(["xrtm", "local-llm", "status", "--base-url", base_url], log_path=journey_dir / "local-llm-status.log", cwd=journey_dir, env=env)
    warm_up_local_llm(
        base_url=base_url,
        model=model,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        log_path=journey_dir / "warmup.json",
    )
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
    previous_benchmark_runs: set[str] = set()
    compare_run_ids: list[str] = []
    stress_run_ids: list[str] = []
    flagship_run_id: str | None = None
    competition_run_id: str | None = None
    write_json(
        metadata_dir / "benchmark-window-start.json",
        {"timestamp": utc_now_iso(), "validation_profile": validation_profile},
    )
    try:
        if benchmark_runs_dir.exists():
            previous_benchmark_runs = set(path.name for path in benchmark_runs_dir.iterdir() if path.is_dir())
        run_logged(
            [
                "xrtm",
                "workflow",
                "run",
                "flagship-benchmark",
                "--runs-dir",
                str(benchmark_runs_dir),
                "--provider",
                "local-llm",
                "--base-url",
                base_url,
                "--model",
                model,
                "--api-key",
                api_key,
                "--limit",
                str(benchmark_limit),
                "--max-tokens",
                str(max_tokens),
            ],
            log_path=journey_dir / "flagship-workflow.log",
            cwd=journey_dir,
            env=env,
        )
        flagship_run_id = latest_run_id(benchmark_runs_dir)
        previous_benchmark_runs = set(path.name for path in benchmark_runs_dir.iterdir() if path.is_dir())
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
                str(benchmark_limit),
                "--runs-dir",
                str(benchmark_runs_dir),
                "--output-dir",
                str(benchmark_output_dir),
                "--release-gate-mode",
                "--allow-unsafe-local-llm",
                "--baseline-label",
                "mock-control",
                "--baseline-provider",
                "mock",
                "--candidate-label",
                "local-qwen",
                "--candidate-provider",
                "local-llm",
                "--candidate-base-url",
                base_url,
                "--candidate-model",
                model,
                "--candidate-api-key",
                api_key,
                "--candidate-max-tokens",
                str(max_tokens),
            ],
            log_path=journey_dir / "benchmark-compare.log",
            cwd=journey_dir,
            env=env,
        )
        compare_run_ids = sorted(
            path.name for path in benchmark_runs_dir.iterdir() if path.is_dir() and path.name not in previous_benchmark_runs
        )
        previous_benchmark_runs = set(path.name for path in benchmark_runs_dir.iterdir() if path.is_dir())
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
                str(benchmark_limit),
                "--repeats",
                str(benchmark_repeats),
                "--runs-dir",
                str(benchmark_runs_dir),
                "--output-dir",
                str(benchmark_output_dir),
                "--release-gate-mode",
                "--allow-unsafe-local-llm",
                "--baseline-label",
                "mock-control",
                "--baseline-provider",
                "mock",
                "--candidate-label",
                "local-qwen",
                "--candidate-provider",
                "local-llm",
                "--candidate-base-url",
                base_url,
                "--candidate-model",
                model,
                "--candidate-api-key",
                api_key,
                "--candidate-max-tokens",
                str(max_tokens),
            ],
            log_path=journey_dir / "benchmark-stress.log",
            cwd=journey_dir,
            env=env,
        )
        stress_run_ids = sorted(
            path.name for path in benchmark_runs_dir.iterdir() if path.is_dir() and path.name not in previous_benchmark_runs
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
                "local-llm",
                "--base-url",
                base_url,
                "--model",
                model,
                "--api-key",
                api_key,
                "--limit",
                str(benchmark_limit),
                "--max-tokens",
                str(max_tokens),
            ],
            log_path=journey_dir / "competition-dry-run.log",
            cwd=journey_dir,
            env=env,
        )
        competition_run_id = latest_run_id(competition_runs_dir)
    finally:
        write_json(
            metadata_dir / "benchmark-window-end.json",
            {"timestamp": utc_now_iso(), "validation_profile": validation_profile},
        )
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
    if flagship_run_id is None:
        raise RuntimeError("Flagship benchmark run did not produce a run ID")
    if competition_run_id is None:
        raise RuntimeError("Competition dry-run did not produce a run ID")
    competition_run_dir = competition_runs_dir / competition_run_id
    summary = {
        "base_url": base_url,
        "benchmark_artifacts": sorted(path.name for path in benchmark_output_dir.glob("*.json")),
        "benchmark_compare_run_ids": compare_run_ids,
        "benchmark_limit": benchmark_limit,
        "benchmark_repeats": benchmark_repeats,
        "benchmark_stress_run_ids": stress_run_ids,
        "competition_bundle_exists": (competition_run_dir / "competition_submission.json").exists(),
        "competition_run_id": competition_run_id,
        "forecast_count": load_json(run_dir / "run_summary.json")["forecast_count"],
        "flagship_benchmark_run_id": flagship_run_id,
        "models": ready_status["models"],
        "perf_iterations": performance["iterations"],
        "perf_mean_seconds": performance["summary"]["mean_seconds"],
        "report_exists": report_path.exists(),
        "run_id": run_id,
        "status": load_json(run_dir / "run.json")["status"],
        "validation_profile": validation_profile,
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
    profile = VALIDATION_PROFILES[args.validation_profile]
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
        local_llm_timeout_seconds=args.local_llm_timeout_seconds,
        llama_port=args.llama_port,
        llama_ctx_size=args.llama_ctx_size,
        llama_parallel=args.llama_parallel,
        ready_timeout_seconds=args.ready_timeout_seconds,
        ready_interval_seconds=args.ready_interval_seconds,
        perf_iterations=max(args.perf_iterations, profile.perf_iterations),
        validation_profile=args.validation_profile,
        benchmark_limit=max(args.benchmark_limit, profile.benchmark_limit),
        benchmark_repeats=max(args.benchmark_repeats, profile.benchmark_repeats),
        gpu_sample_interval_seconds=args.gpu_sample_interval_seconds,
        min_gpu_benchmark_seconds=max(args.min_gpu_benchmark_seconds, profile.min_gpu_benchmark_seconds),
        min_gpu_active_samples=max(args.min_gpu_active_samples, profile.min_gpu_active_samples),
        min_gpu_memory_mib=max(args.min_gpu_memory_mib, profile.min_gpu_memory_mib),
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
            "local_llm_timeout_seconds": config.local_llm_timeout_seconds,
            "llama_parallel": config.llama_parallel,
            "perf_iterations": config.perf_iterations,
            "benchmark_limit": config.benchmark_limit,
            "benchmark_repeats": config.benchmark_repeats,
            "gpu_sample_interval_seconds": config.gpu_sample_interval_seconds,
            "min_gpu_benchmark_seconds": config.min_gpu_benchmark_seconds,
            "min_gpu_active_samples": config.min_gpu_active_samples,
            "min_gpu_memory_mib": config.min_gpu_memory_mib,
            "project_name": config.project_name,
            "python_image": config.python_image,
            "ready_interval_seconds": config.ready_interval_seconds,
            "ready_timeout_seconds": config.ready_timeout_seconds,
            "validation_profile": config.validation_profile,
            "wheelhouse_dir": str(config.wheelhouse_dir),
            "workspace_root": str(config.workspace_root),
            "xrtm_repo_root": str(config.xrtm_repo_root),
            "xrtm_spec": config.xrtm_spec,
        },
    )
    gpu_sampler: subprocess.Popen[str] | None = None
    gpu_telemetry_path = artifacts_dir / "metadata" / "gpu-telemetry.jsonl"
    if nvidia_smi_available():
        gpu_sampler = start_gpu_telemetry_sampler(
            output_path=gpu_telemetry_path,
            interval_seconds=config.gpu_sample_interval_seconds,
            log_path=metadata_dir / "gpu-telemetry.log",
        )
    elif config.validation_profile == "release":
        raise RuntimeError("nvidia-smi is required for release-profile local-LLM validation")
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
        stop_gpu_telemetry_sampler(gpu_sampler)
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
        summary = load_json(summary_path)
        benchmark_start_path = metadata_dir / "benchmark-window-start.json"
        benchmark_end_path = metadata_dir / "benchmark-window-end.json"
        benchmark_start = load_json(benchmark_start_path).get("timestamp") if benchmark_start_path.exists() else None
        benchmark_end = load_json(benchmark_end_path).get("timestamp") if benchmark_end_path.exists() else None
        gpu_summary = summarize_gpu_telemetry(gpu_telemetry_path, start_time=benchmark_start, end_time=benchmark_end)
        failures = validate_gpu_summary(
            gpu_summary,
            min_benchmark_seconds=config.min_gpu_benchmark_seconds,
            min_active_samples=config.min_gpu_active_samples,
            min_memory_mib=config.min_gpu_memory_mib,
        )
        gpu_summary["validation"] = {"status": "failed" if failures else "passed", "failures": failures}
        summary["gpu_telemetry"] = gpu_summary
        summary["validation_profile"] = config.validation_profile
        write_json(metadata_dir / "gpu-telemetry-summary.json", gpu_summary)
        write_json(summary_path, summary)
        if failures:
            raise RuntimeError("local-LLM GPU validation failed: " + "; ".join(failures))
        print(json.dumps(summary, indent=2, sort_keys=True))
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
            "local_llm_timeout_seconds": args.local_llm_timeout_seconds,
            "perf_iterations": args.perf_iterations,
            "benchmark_limit": args.benchmark_limit,
            "benchmark_repeats": args.benchmark_repeats,
            "ready_interval_seconds": args.ready_interval_seconds,
            "ready_timeout_seconds": args.ready_timeout_seconds,
            "validation_profile": args.validation_profile,
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
                "XRTM_LOCAL_LLM_TIMEOUT_SECONDS": str(args.local_llm_timeout_seconds),
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
            timeout_seconds=args.local_llm_timeout_seconds,
            perf_iterations=args.perf_iterations,
            benchmark_limit=args.benchmark_limit,
            benchmark_repeats=args.benchmark_repeats,
            validation_profile=args.validation_profile,
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
    host_parser.add_argument("--local-llm-timeout-seconds", type=int, default=DEFAULT_LOCAL_LLM_TIMEOUT_SECONDS)
    host_parser.add_argument("--llama-port", type=int, default=DEFAULT_LLAMA_CPP_PORT)
    host_parser.add_argument("--llama-ctx-size", type=int, default=DEFAULT_LLAMA_CPP_CTX_SIZE)
    host_parser.add_argument("--llama-parallel", type=int, default=DEFAULT_LLAMA_CPP_PARALLEL)
    host_parser.add_argument("--ready-timeout-seconds", type=int, default=DEFAULT_READY_TIMEOUT_SECONDS)
    host_parser.add_argument("--ready-interval-seconds", type=int, default=DEFAULT_READY_INTERVAL_SECONDS)
    host_parser.add_argument("--perf-iterations", type=int, default=DEFAULT_PERF_ITERATIONS)
    host_parser.add_argument("--validation-profile", choices=sorted(VALIDATION_PROFILES), default=DEFAULT_VALIDATION_PROFILE)
    host_parser.add_argument("--benchmark-limit", type=int, default=DEFAULT_BENCHMARK_LIMIT)
    host_parser.add_argument("--benchmark-repeats", type=int, default=DEFAULT_BENCHMARK_REPEATS)
    host_parser.add_argument("--gpu-sample-interval-seconds", type=float, default=DEFAULT_GPU_SAMPLE_INTERVAL_SECONDS)
    host_parser.add_argument("--min-gpu-benchmark-seconds", type=int, default=0)
    host_parser.add_argument("--min-gpu-active-samples", type=int, default=0)
    host_parser.add_argument("--min-gpu-memory-mib", type=int, default=0)

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
    inside_parser.add_argument("--local-llm-timeout-seconds", type=int, required=True)
    inside_parser.add_argument("--ready-timeout-seconds", type=int, required=True)
    inside_parser.add_argument("--ready-interval-seconds", type=int, required=True)
    inside_parser.add_argument("--perf-iterations", type=int, required=True)
    inside_parser.add_argument("--validation-profile", choices=sorted(VALIDATION_PROFILES), required=True)
    inside_parser.add_argument("--benchmark-limit", type=int, required=True)
    inside_parser.add_argument("--benchmark-repeats", type=int, required=True)

    sample_gpu_parser = subparsers.add_parser("sample-gpu")
    sample_gpu_parser.add_argument("--output", required=True)
    sample_gpu_parser.add_argument("--interval-seconds", type=float, default=DEFAULT_GPU_SAMPLE_INTERVAL_SECONDS)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.mode == "inside":
        return run_inside(args)
    if args.mode == "sample-gpu":
        return run_gpu_sampler(output_path=Path(args.output), interval_seconds=args.interval_seconds)
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
        args.local_llm_timeout_seconds = DEFAULT_LOCAL_LLM_TIMEOUT_SECONDS
        args.llama_port = DEFAULT_LLAMA_CPP_PORT
        args.llama_ctx_size = DEFAULT_LLAMA_CPP_CTX_SIZE
        args.llama_parallel = DEFAULT_LLAMA_CPP_PARALLEL
        args.ready_timeout_seconds = DEFAULT_READY_TIMEOUT_SECONDS
        args.ready_interval_seconds = DEFAULT_READY_INTERVAL_SECONDS
        args.perf_iterations = DEFAULT_PERF_ITERATIONS
        args.validation_profile = DEFAULT_VALIDATION_PROFILE
        args.benchmark_limit = DEFAULT_BENCHMARK_LIMIT
        args.benchmark_repeats = DEFAULT_BENCHMARK_REPEATS
        args.gpu_sample_interval_seconds = DEFAULT_GPU_SAMPLE_INTERVAL_SECONDS
        args.min_gpu_benchmark_seconds = 0
        args.min_gpu_active_samples = 0
        args.min_gpu_memory_mib = 0
    return run_host(args)


if __name__ == "__main__":
    raise SystemExit(main())
