"""Product launch services — linear pipeline (no workflow system)."""

from __future__ import annotations

from pathlib import Path

from xrtm.product.pipeline import PipelineOptions, PipelineResult, run_pipeline
from xrtm.product.providers import MOCK_PROVIDER_NAME

DEFAULT_LIMIT = 5
DEFAULT_MAX_TOKENS = 768


def run_forecasts(
    *,
    limit: int = DEFAULT_LIMIT,
    runs_dir: Path = Path("runs"),
    provider: str = "openai",
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    user: str | None = None,
) -> PipelineResult:
    """Run forecast pipeline. Uses OpenAI-compatible by default."""
    options = PipelineOptions(
        provider=provider,
        limit=limit,
        runs_dir=runs_dir,
        model=model,
        base_url=base_url,
        api_key=api_key,
        max_tokens=DEFAULT_MAX_TOKENS,
        write_report=True,
        command="xrtm start",
        user=user,
    )
    return run_pipeline(options)


__all__ = ["run_forecasts"]
