from __future__ import annotations

from unittest.mock import patch

import xrtm.product.providers as providers_module
from xrtm.product.providers import DEFAULT_LOCAL_LLM_BASE_URL, build_provider, local_llm_base_url


def test_build_provider_uses_local_llm_env_defaults(monkeypatch) -> None:
    monkeypatch.setenv("XRTM_LOCAL_LLM_BASE_URL", "http://127.0.0.1:9000/v1/")
    monkeypatch.setenv("XRTM_LOCAL_LLM_MODEL", "demo-model")
    monkeypatch.setenv("XRTM_LOCAL_LLM_API_KEY", "secret-token")

    resolved_config = None

    def fake_get_provider(config):
        nonlocal resolved_config
        resolved_config = config
        return object()

    with patch.object(
        providers_module,
        "local_llm_status",
        return_value={
            "base_url": "http://127.0.0.1:9000/v1",
            "health_url": "http://127.0.0.1:9000/health",
            "models_url": "http://127.0.0.1:9000/v1/models",
            "healthy": True,
            "models": ["demo-model"],
            "gpu": {"available": False},
            "error": None,
        },
    ), patch.object(providers_module.ModelFactory, "get_provider", side_effect=fake_get_provider):
        provider = build_provider("local-llm", base_url=None, model=None, api_key=None)

    assert provider is not None
    assert resolved_config is not None
    assert local_llm_base_url() == "http://127.0.0.1:9000/v1"
    assert resolved_config.base_url == "http://127.0.0.1:9000/v1"
    assert resolved_config.model_id == "demo-model"
    assert resolved_config.api_key.get_secret_value() == "secret-token"


def test_build_provider_surfaces_local_llm_status_failure() -> None:
    with patch.object(
        providers_module,
        "local_llm_status",
        return_value={
            "base_url": DEFAULT_LOCAL_LLM_BASE_URL,
            "health_url": "http://localhost:8080/health",
            "models_url": f"{DEFAULT_LOCAL_LLM_BASE_URL}/models",
            "healthy": False,
            "models": [],
            "gpu": {"available": False},
            "error": "connection refused",
        },
    ):
        try:
            build_provider("local-llm", base_url=None, model=None, api_key=None)
        except RuntimeError as exc:
            message = str(exc)
        else:
            raise AssertionError("expected local-llm provider resolution to fail")

    assert DEFAULT_LOCAL_LLM_BASE_URL in message
    assert "curl http://localhost:8080/health" in message
    assert "connection refused" in message
