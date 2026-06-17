"""Runtime provider resolution — imports MockProvider from forecast, adds product logic."""

from __future__ import annotations

import os

from pydantic import SecretStr

from xrtm.forecast.core.config.inference import OpenAIConfig
from xrtm.forecast.providers.inference.base import InferenceProvider
from xrtm.forecast.providers.inference.factory import ModelFactory
from xrtm.forecast.providers.inference.mock_provider import MockProvider

MOCK_PROVIDER_NAME = "mock"
_PROVIDER_NAME_ALIASES = {"deterministic": MOCK_PROVIDER_NAME, MOCK_PROVIDER_NAME: MOCK_PROVIDER_NAME}


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
            "OPENAI_API_KEY not set. Add it to your environment or .env file."
        )
    config = OpenAIConfig(model_id=resolved_model, base_url=resolved_base, api_key=SecretStr(resolved_key))
    return ModelFactory.get_provider(config)


__all__ = ["MOCK_PROVIDER_NAME", "MockProvider", "build_provider", "normalize_provider_name"]
