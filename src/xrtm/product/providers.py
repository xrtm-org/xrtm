"""Provider discovery and deterministic provider-free execution."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from types import SimpleNamespace
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from pydantic import SecretStr

from xrtm.forecast.core.config.inference import OpenAIConfig
from xrtm.forecast.providers.inference.base import InferenceProvider, ModelResponse
from xrtm.forecast.providers.inference.factory import ModelFactory

DEFAULT_LOCAL_LLM_BASE_URL = "http://localhost:8080/v1"
DEFAULT_LOCAL_LLM_MODEL = "Qwen3.5-27B-Q4_K_M.gguf"


class DeterministicProvider(InferenceProvider):
    """Provider-free forecast double with deterministic structured responses."""

    model_id = "xrtm-deterministic-product"
    base_url = "provider-free://deterministic"

    def __init__(self) -> None:
        self.cache_hits = 0
        self.cache_misses = 0
        self._cache: dict[str, ModelResponse] = {}

    def generate_content(self, prompt: Any, output_logprobs: bool = False, **kwargs: Any) -> ModelResponse:
        prompt_text = json.dumps(prompt, sort_keys=True, default=str)
        cache_key = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
        if cache_key in self._cache:
            self.cache_hits += 1
            cached = self._cache[cache_key]
            return ModelResponse(
                text=cached.text,
                raw=cached.raw,
                usage=dict(cached.usage),
                metadata={**cached.metadata, "cache_hit": True},
            )

        self.cache_misses += 1
        question_id = extract_question_id(prompt_text)
        probability = deterministic_probability(question_id)
        payload = {
            "probability": probability,
            "reasoning": f"Deterministic provider-free forecast for {question_id}.",
            "logical_trace": [
                {
                    "event": "deterministic_real_corpus_prior",
                    "probability": probability,
                    "description": "Stable hash-derived probability for product smoke validation.",
                }
            ],
            "structural_trace": ["load_question", "provider_free_forecast", "validate_output"],
        }
        completion_text = json.dumps(payload, separators=(",", ":"))
        response = ModelResponse(
            text=completion_text,
            raw=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(reasoning_content=""))]),
            usage={
                "prompt_tokens": max(1, len(prompt_text.split())),
                "completion_tokens": max(1, len(completion_text.split())),
                "total_tokens": max(2, len(prompt_text.split()) + len(completion_text.split())),
            },
            metadata={"cache_hit": False, "provider_free": True},
        )
        self._cache[cache_key] = response
        return response

    async def generate_content_async(self, prompt: Any, output_logprobs: bool = False, **kwargs: Any) -> ModelResponse:
        return self.generate_content(prompt, output_logprobs, **kwargs)

    async def stream(self, messages: list[dict[str, str]], **kwargs: Any):
        yield self.generate_content(messages, **kwargs)

    @property
    def cache_snapshot(self) -> dict[str, Any]:
        total = self.cache_hits + self.cache_misses
        return {
            "enabled": True,
            "hits": self.cache_hits,
            "misses": self.cache_misses,
            "entries": len(self._cache),
            "hit_rate": self.cache_hits / total if total else 0.0,
        }


def build_provider(provider: str, *, base_url: str | None, model: str | None, api_key: str | None) -> InferenceProvider:
    if provider == "mock":
        return DeterministicProvider()
    if provider == "local-llm":
        base_url_value = local_llm_base_url(base_url)
        status = local_llm_status(base_url=base_url_value)
        if not status["healthy"]:
            raise RuntimeError(status["error"] or f"Local LLM endpoint is not healthy: {base_url_value}")
        config = OpenAIConfig(
            model_id=model or os.getenv("XRTM_LOCAL_LLM_MODEL") or DEFAULT_LOCAL_LLM_MODEL,
            api_key=SecretStr(api_key or os.getenv("XRTM_LOCAL_LLM_API_KEY") or "test"),
            base_url=base_url_value,
        )
        return ModelFactory.get_provider(config)
    raise ValueError(f"unsupported provider: {provider}")


def local_llm_base_url(base_url: str | None = None) -> str:
    return (base_url or os.getenv("XRTM_LOCAL_LLM_BASE_URL") or DEFAULT_LOCAL_LLM_BASE_URL).rstrip("/")


def local_llm_status(*, base_url: str | None = None) -> dict[str, Any]:
    base_url_value = local_llm_base_url(base_url)
    root_url = base_url_value.removesuffix("/v1")
    status: dict[str, Any] = {
        "base_url": base_url_value,
        "health_url": f"{root_url}/health",
        "models_url": f"{base_url_value}/models",
        "healthy": False,
        "models": [],
        "gpu": gpu_snapshot(),
        "error": None,
    }
    try:
        _read_json_url(status["health_url"], timeout=3)
        models_payload = _read_json_url(status["models_url"], timeout=5)
        models = models_payload.get("data", []) if isinstance(models_payload, dict) else []
        status["models"] = [item.get("id", str(item)) for item in models if isinstance(item, dict)]
        status["healthy"] = True
    except (OSError, URLError, TimeoutError, ValueError) as exc:
        status["error"] = str(exc)
    return status


def provider_snapshot(provider: InferenceProvider, provider_name: str, *, base_url: str | None = None) -> dict[str, Any]:
    snapshot = {
        "provider": provider_name,
        "model": getattr(provider, "model_id", None),
        "base_url": str(getattr(provider, "base_url", base_url)),
        "cache": cache_snapshot(provider),
    }
    if provider_name == "local-llm":
        snapshot["local_llm"] = local_llm_status(base_url=base_url)
    return snapshot


def cache_snapshot(provider: InferenceProvider) -> dict[str, Any]:
    snapshot = getattr(provider, "cache_snapshot", None)
    if isinstance(snapshot, dict):
        return snapshot
    return {"enabled": False}


def gpu_snapshot() -> dict[str, Any]:
    command = [
        "nvidia-smi",
        "--query-gpu=name,memory.used,memory.total,utilization.gpu",
        "--format=csv,noheader,nounits",
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=5)
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "error": str(exc)}
    rows = []
    for line in result.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) == 4:
            rows.append(
                {
                    "name": parts[0],
                    "memory_used_mib": _coerce_int(parts[1]),
                    "memory_total_mib": _coerce_int(parts[2]),
                    "utilization_percent": _coerce_int(parts[3]),
                }
            )
    return {"available": bool(rows), "gpus": rows}


def extract_question_id(prompt_text: str) -> str:
    marker = "Question ID: "
    if marker in prompt_text:
        return prompt_text.split(marker, 1)[1].split("\\n", 1)[0].strip().strip('"')
    return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:12]


def deterministic_probability(question_id: str) -> float:
    digest = hashlib.sha256(question_id.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) / 0xFFFFFFFF
    return round(0.05 + bucket * 0.9, 3)


def _read_json_url(url: str, *, timeout: int) -> Any:
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body else {}


def _coerce_int(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


__all__ = [
    "DEFAULT_LOCAL_LLM_BASE_URL",
    "DEFAULT_LOCAL_LLM_MODEL",
    "DeterministicProvider",
    "build_provider",
    "local_llm_status",
    "provider_snapshot",
]
