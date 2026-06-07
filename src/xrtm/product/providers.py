"""Runtime provider resolution — deterministic baseline + OpenAI-compatible."""

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

DETERMINISTIC_PROVIDER_NAME = "deterministic"
_PROVIDER_NAME_ALIASES = {
    "mock": DETERMINISTIC_PROVIDER_NAME,
    "provider-free": DETERMINISTIC_PROVIDER_NAME,
}


class DeterministicProvider(InferenceProvider):
    """Deterministic baseline provider — no API keys, stable hash-derived probabilities."""

    model_id = "xrtm-deterministic"
    base_url = "deterministic://hash-derived"

    def __init__(self) -> None:
        self._cache: dict[str, ModelResponse] = {}

    def generate_content(self, prompt: Any, **kwargs: Any) -> ModelResponse:
        prompt_text = json.dumps(prompt, sort_keys=True, default=str)
        cache_key = hashlib.sha256(prompt_text.encode()).hexdigest()
        if cache_key in self._cache:
            return self._cache[cache_key]

        question_id = hashlib.sha256(prompt_text.encode()).hexdigest()[:12]
        bucket = int(hashlib.sha256(question_id.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        probability = round(0.05 + bucket * 0.9, 3)

        payload = json.dumps({
            "probability": probability,
            "reasoning": f"Deterministic hash-derived forecast for {question_id}.",
            "causal_nodes": [],
            "causal_edges": [],
        }, separators=(",", ":"))

        response = ModelResponse(
            text=payload,
            raw=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(reasoning_content=""))]),
            usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            metadata={"deterministic": True},
        )
        self._cache[cache_key] = response
        return response

    async def generate_content_async(self, prompt: Any, **kwargs: Any) -> ModelResponse:
        return self.generate_content(prompt, **kwargs)

    async def stream(self, messages, **kwargs: Any):
        yield self.generate_content(messages, **kwargs)


def normalize_provider_name(provider: str) -> str:
    return _PROVIDER_NAME_ALIASES.get(provider.strip().lower(), provider.strip())


def build_provider(provider: str, *, base_url: str | None, model: str | None, api_key: str | None) -> InferenceProvider:
    provider = normalize_provider_name(provider)
    if provider == DETERMINISTIC_PROVIDER_NAME:
        return DeterministicProvider()
    if provider in {"openai", "openai-compatible"}:
        resolved_base_url = base_url or "https://api.openai.com/v1"
        resolved_model = model or "gpt-4o-mini"
        resolved_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        config = OpenAIConfig(
            model_id=resolved_model,
            base_url=resolved_base_url,
            api_key=SecretStr(resolved_key) if resolved_key else None,
        )
        return ModelFactory.get_provider(config)
    supported = ["deterministic", "openai", "openai-compatible"]
    raise ValueError(f"Unsupported provider: '{provider}'. Supported: {', '.join(supported)}")


__all__ = ["DETERMINISTIC_PROVIDER_NAME", "DeterministicProvider", "build_provider", "normalize_provider_name"]
