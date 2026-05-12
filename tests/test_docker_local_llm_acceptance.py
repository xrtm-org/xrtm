from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "docker_local_llm_acceptance.py"
    spec = importlib.util.spec_from_file_location("docker_local_llm_acceptance", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_default_artifacts_dir_uses_docker_local_llm_path() -> None:
    module = _load_module()

    path = module.default_artifacts_dir(Path("/workspace"), "20260507T190000Z")

    assert path == Path("/workspace/acceptance-studies/docker-local-llm/20260507T190000Z")


def test_compose_environment_keeps_acceptance_runner_and_llama_service_separate(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module.os, "getuid", lambda: 1000)
    monkeypatch.setattr(module.os, "getgid", lambda: 1001)
    config = module.HostConfig(
        workspace_root=Path("/workspace"),
        xrtm_repo_root=Path("/workspace/xrtm"),
        artifact_source="wheelhouse",
        artifacts_dir=Path("/artifacts-host"),
        wheelhouse_dir=Path("/wheelhouse-host"),
        image_tag="xrtm-local-llm-acceptance:py311",
        python_image="python:3.11-slim",
        xrtm_spec="xrtm==0.3.0",
        project_name="xrtm-local-llm-test",
        llama_image="ghcr.io/ggml-org/llama.cpp:server",
        llama_model_dir=Path("/models-host"),
        llama_model_file="Qwen.gguf",
        local_llm_base_url="http://llama-cpp:8080/v1",
        local_llm_model="Qwen.gguf",
        local_llm_api_key="test",
        local_llm_max_tokens=768,
        local_llm_timeout_seconds=180,
        llama_port=8080,
        llama_ctx_size=4096,
        llama_parallel=1,
        ready_timeout_seconds=600,
        ready_interval_seconds=5,
        perf_iterations=1,
        validation_profile="smoke",
        benchmark_limit=3,
        benchmark_repeats=1,
        gpu_sample_interval_seconds=1.0,
        min_gpu_benchmark_seconds=0,
        min_gpu_active_samples=0,
        min_gpu_memory_mib=0,
    )

    env = module.compose_environment(config)

    assert env["XRTM_ACCEPTANCE_IMAGE"] == "xrtm-local-llm-acceptance:py311"
    assert env["XRTM_LLAMA_CPP_IMAGE"] == "ghcr.io/ggml-org/llama.cpp:server"
    assert env["XRTM_LOCAL_LLM_BASE_URL"] == "http://llama-cpp:8080/v1"
    assert env["XRTM_LOCAL_LLM_BENCHMARK_LIMIT"] == "3"
    assert env["XRTM_LLAMA_CPP_MODEL_DIR"] == "/models-host"
    assert env["XRTM_REPO_ROOT_IN_WORKSPACE"] == "/workspace/xrtm"
    assert env["XRTM_LOCAL_LLM_STRESS_REPEATS"] == "1"
    assert env["XRTM_LOCAL_LLM_VALIDATION_PROFILE"] == "smoke"
    assert env["XRTM_WHEELHOUSE_DIR"] == "/wheelhouse-host"


def test_compose_environment_supports_repo_root_equal_to_workspace_root(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module.os, "getuid", lambda: 1000)
    monkeypatch.setattr(module.os, "getgid", lambda: 1001)
    config = module.HostConfig(
        workspace_root=Path("/workspace"),
        xrtm_repo_root=Path("/workspace"),
        artifact_source="wheelhouse",
        artifacts_dir=Path("/artifacts-host"),
        wheelhouse_dir=Path("/wheelhouse-host"),
        image_tag="xrtm-local-llm-acceptance:py311",
        python_image="python:3.11-slim",
        xrtm_spec="xrtm==0.3.0",
        project_name="xrtm-local-llm-test",
        llama_image="ghcr.io/ggml-org/llama.cpp:server",
        llama_model_dir=Path("/models-host"),
        llama_model_file="Qwen.gguf",
        local_llm_base_url="http://llama-cpp:8080/v1",
        local_llm_model="Qwen.gguf",
        local_llm_api_key="test",
        local_llm_max_tokens=768,
        local_llm_timeout_seconds=180,
        llama_port=8080,
        llama_ctx_size=4096,
        llama_parallel=1,
        ready_timeout_seconds=600,
        ready_interval_seconds=5,
        perf_iterations=1,
        validation_profile="smoke",
        benchmark_limit=3,
        benchmark_repeats=1,
        gpu_sample_interval_seconds=1.0,
        min_gpu_benchmark_seconds=0,
        min_gpu_active_samples=0,
        min_gpu_memory_mib=0,
    )

    env = module.compose_environment(config)

    assert env["XRTM_REPO_ROOT_IN_WORKSPACE"] == "/workspace"


def test_docker_compose_command_uses_compose_lane() -> None:
    module = _load_module()

    command = module.docker_compose_command(
        Path("/workspace/xrtm"),
        "xrtm-local-llm-test",
        Path("/workspace/compose.env"),
        "up",
        "--abort-on-container-exit",
        "--exit-code-from",
        "acceptance",
    )

    assert command[:8] == [
        "docker",
        "compose",
        "--project-name",
        "xrtm-local-llm-test",
        "-f",
        "/workspace/xrtm/docker/local-llm-acceptance.compose.yml",
        "--env-file",
        "/workspace/compose.env",
    ]
    assert command[-4:] == ["up", "--abort-on-container-exit", "--exit-code-from", "acceptance"]


def test_compose_file_passes_local_llm_timeout_to_acceptance_container() -> None:
    compose_path = Path(__file__).resolve().parents[1] / "docker" / "local-llm-acceptance.compose.yml"
    compose_text = compose_path.read_text(encoding="utf-8")

    assert "--local-llm-timeout-seconds" in compose_text
    assert '"${XRTM_LOCAL_LLM_TIMEOUT_SECONDS}"' in compose_text


def test_release_profile_uses_four_stress_repeats_for_gpu_window() -> None:
    module = _load_module()

    assert module.VALIDATION_PROFILES["release"].benchmark_repeats == 4


def test_wait_for_local_llm_accepts_matching_model(tmp_path, monkeypatch) -> None:
    module = _load_module()
    responses = iter(
        [
            {},
            {"data": [{"id": "Qwen.gguf"}]},
        ]
    )

    class FakeResponse:
        def __init__(self, payload: dict[str, object]) -> None:
            self._payload = payload

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def read(self) -> bytes:
            return json.dumps(self._payload).encode("utf-8")

    monkeypatch.setattr(module, "urlopen", lambda request, timeout: FakeResponse(next(responses)))

    status = module.wait_for_local_llm(
        base_url="http://llama-cpp:8080/v1",
        expected_model="Qwen.gguf",
        timeout_seconds=10,
        interval_seconds=1,
        log_path=tmp_path / "ready.json",
    )

    assert status["healthy"] is True
    assert status["models"] == ["Qwen.gguf"]


def test_gpu_telemetry_command_uses_sample_gpu_mode(tmp_path) -> None:
    module = _load_module()

    command = module.gpu_telemetry_command(output_path=tmp_path / "gpu.jsonl", interval_seconds=2.5)

    assert command[1].endswith("docker_local_llm_acceptance.py")
    assert command[2:] == ["sample-gpu", "--output", str(tmp_path / "gpu.jsonl"), "--interval-seconds", "2.5"]


def test_validate_gpu_summary_reports_threshold_failures() -> None:
    module = _load_module()

    failures = module.validate_gpu_summary(
        {
            "available": True,
            "duration_seconds": 120,
            "active_sample_count": 4,
            "peak_memory_used_mib": 1024,
        },
        min_benchmark_seconds=1800,
        min_active_samples=60,
        min_memory_mib=4096,
    )

    assert failures == [
        "gpu benchmark window 120.0s is below required 1800s",
        "gpu active samples 4 are below required 60",
        "gpu peak memory 1024 MiB is below required 4096 MiB",
    ]


def test_run_host_requires_nvidia_smi_for_release_profile(tmp_path, monkeypatch) -> None:
    module = _load_module()
    repo_root = tmp_path / "workspace" / "xrtm"
    model_dir = tmp_path / "models"
    model_dir.mkdir(parents=True)
    (model_dir / "Qwen3.5-9B-UD-Q4_K_XL.gguf").write_text("model", encoding="utf-8")
    repo_root.mkdir(parents=True)

    monkeypatch.setattr(module, "workspace_root", lambda: tmp_path / "workspace")
    monkeypatch.setattr(module, "xrtm_repo_root", lambda: repo_root)
    monkeypatch.setattr(module, "default_specs", lambda root, repo_root: ("xrtm==0.3.0", "xrtm-forecast==0.6.6"))
    monkeypatch.setattr(module, "nvidia_smi_available", lambda: False)
    monkeypatch.setattr(module, "build_wheelhouse", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "run_logged", lambda *args, **kwargs: None)

    args = module.build_parser().parse_args(
        [
            "host",
            "--workspace-root",
            str(tmp_path / "workspace"),
            "--xrtm-repo-root",
            str(repo_root),
            "--llama-model-dir",
            str(model_dir),
            "--validation-profile",
            "release",
        ]
    )

    try:
        module.run_host(args)
    except RuntimeError as exc:
        assert "nvidia-smi is required" in str(exc)
    else:
        raise AssertionError("expected release profile to require nvidia-smi")
