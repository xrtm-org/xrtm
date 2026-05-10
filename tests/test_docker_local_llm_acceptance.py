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
        llama_port=8080,
        llama_ctx_size=4096,
        ready_timeout_seconds=600,
        ready_interval_seconds=5,
        perf_iterations=1,
    )

    env = module.compose_environment(config)

    assert env["XRTM_ACCEPTANCE_IMAGE"] == "xrtm-local-llm-acceptance:py311"
    assert env["XRTM_LLAMA_CPP_IMAGE"] == "ghcr.io/ggml-org/llama.cpp:server"
    assert env["XRTM_LOCAL_LLM_BASE_URL"] == "http://llama-cpp:8080/v1"
    assert env["XRTM_LLAMA_CPP_MODEL_DIR"] == "/models-host"
    assert env["XRTM_REPO_ROOT_IN_WORKSPACE"] == "/workspace/xrtm"
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
        llama_port=8080,
        llama_ctx_size=4096,
        ready_timeout_seconds=600,
        ready_interval_seconds=5,
        perf_iterations=1,
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
