"""Product launch services — linear pipeline (no workflow system)."""

from __future__ import annotations

from pathlib import Path

from xrtm.product.doctor import doctor_snapshot
from xrtm.product.pipeline import PipelineOptions, PipelineResult, run_pipeline
from xrtm.product.providers import DETERMINISTIC_PROVIDER_NAME, normalize_provider_name

DEFAULT_DEMO_LIMIT = 2
DEFAULT_MAX_TOKENS = 768


def run_start_quickstart(
    *,
    limit: int = DEFAULT_DEMO_LIMIT,
    runs_dir: Path = Path("runs"),
    user: str | None = None,
) -> PipelineResult:
    """Run the deterministic quickstart after readiness checks."""
    readiness = doctor_snapshot(runs_dir=runs_dir)
    if not readiness["ready"]:
        blocking = [check["detail"] for check in readiness["checks"] if not check["ok"]]
        detail = "; ".join(blocking) if blocking else "doctor readiness checks failed"
        raise ValueError(f"xrtm start prerequisites not satisfied: {detail}")
    return run_demo_workflow(provider=DETERMINISTIC_PROVIDER_NAME, limit=limit, runs_dir=runs_dir, user=user, command="xrtm start")


def run_demo_workflow(
    *,
    provider: str = DETERMINISTIC_PROVIDER_NAME,
    limit: int = DEFAULT_DEMO_LIMIT,
    runs_dir: Path = Path("runs"),
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    write_report: bool = True,
    user: str | None = None,
    command: str = "xrtm demo",
) -> PipelineResult:
    """Run a linear forecast→eval→train pipeline."""
    provider = normalize_provider_name(provider)
    options = PipelineOptions(
        provider=provider,
        limit=limit,
        runs_dir=runs_dir,
        base_url=base_url,
        model=model,
        api_key=api_key,
        max_tokens=max_tokens,
        write_report=write_report,
        command=command,
        user=user,
    )
    return run_pipeline(options)


__all__ = [
    "run_start_quickstart",
    "run_demo_workflow",
]
