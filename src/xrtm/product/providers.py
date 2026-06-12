"""Runtime provider — OpenAI-compatible by default, mock for testing."""

from __future__ import annotations

import hashlib
import json
import os
from types import SimpleNamespace
from typing import Any

from pydantic import SecretStr

from xrtm.forecast.core.config.inference import OpenAIConfig
from xrtm.forecast.providers.inference.base import InferenceProvider, ModelResponse
from xrtm.forecast.providers.inference.factory import ModelFactory

MOCK_PROVIDER_NAME = "mock"
_PROVIDER_NAME_ALIASES = {"deterministic": MOCK_PROVIDER_NAME, MOCK_PROVIDER_NAME: MOCK_PROVIDER_NAME}


class MockProvider(InferenceProvider):
    """Hash-derived provider for CI smoke testing — zero cost, no API key."""

    model_id = "xrtm-mock"
    base_url = "mock://"

    def __init__(self) -> None:
        self._cache: dict[str, ModelResponse] = {}

    def generate_content(self, prompt: Any, **kwargs: Any) -> ModelResponse:
        key = hashlib.sha256(json.dumps(prompt, sort_keys=True, default=str).encode()).hexdigest()
        if key in self._cache:
            return self._cache[key]
        bucket = int(key[:8], 16) / 0xFFFFFFFF
        p = round(0.05 + bucket * 0.9, 3)
        text = json.dumps({"probability": p, "reasoning": "mock", "causal_nodes": [], "causal_edges": []})
        resp = ModelResponse(text=text, raw=SimpleNamespace(), usage={"total_tokens": 2}, metadata={"mock": True})
        self._cache[key] = resp
        return resp

    async def generate_content_async(self, prompt: Any, **kwargs: Any) -> ModelResponse:
        return self.generate_content(prompt, **kwargs)

    async def stream(self, messages, **kwargs: Any):
        yield self.generate_content(messages, **kwargs)


def normalize_provider_name(provider: str) -> str:
    return _PROVIDER_NAME_ALIASES.get(provider.strip().lower(), provider.strip())


def build_provider(provider: str, *, base_url: str | None, model: str | None, api_key: str | None) -> InferenceProvider:
    provider = normalize_provider_name(provider)
    if provider == MOCK_PROVIDER_NAME:
        return MockProvider()
    resolved_base = base_url or os.environ.get("OPENAI_BASE_URL", "")
    resolved_model = model or os.environ.get("OPENAI_MODEL", "")
    resolved_key = api_key or os.environ.get("OPENAI_API_KEY", "")
    if not resolved_key:
        raise ValueError(
            "OPENAI_API_KEY not set. Set it in your environment or .env file.\n"
            "Get a key at https://platform.openai.com or use any OpenAI-compatible provider."
        )
    config = OpenAIConfig(model_id=resolved_model, base_url=resolved_base, api_key=SecretStr(resolved_key))
    return ModelFactory.get_provider(config)


__all__ = ["MOCK_PROVIDER_NAME", "MockProvider", "build_provider", "normalize_provider_name"]
