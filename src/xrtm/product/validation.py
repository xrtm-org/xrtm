"""Large-scale validation harness for XRTM with corpus registry integration.

This module provides a comprehensive validation interface that supports:
- Corpus selection from the registry with tier/license awareness
- Split-aware validation (train/eval/held-out)
- Large offline corpus sweeps
- Local-LLM/GPU stress testing (explicit opt-in)
- Structured artifact generation for release gating

See data/docs/benchmark-corpus-policy.md for source classification.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from xrtm.data.corpora import (
    CorpusSplitter,
    CorpusTier,
    SplitConfig,
    describe_corpus,
    get_corpus,
    get_corpus_metadata,
    list_available_corpora,
    prepare_corpus,
)
from xrtm.product.pipeline import PipelineOptions, run_pipeline

VALIDATION_SCHEMA_VERSION = "xrtm.validation.v1"
DEFAULT_VALIDATION_DIR = Path(".cache/validation")
LOCAL_LLM_DEFAULT_MAX_LIMIT = 10


class ValidationTierError(RuntimeError):
    """Raised when attempting release-gate validation with non-approved corpus."""


class ValidationSafetyError(RuntimeError):
    """Raised when attempting unsafe operations without explicit override."""


@dataclass(frozen=True)
class ValidationOptions:
    """Configuration for a validation run."""

    corpus_id: str = "xrtm-real-binary-v1"
    split: Optional[str] = None
    tier_filter: Optional[str] = None
    provider: str = "mock"
    limit: int = 10
    iterations: int = 1
    runs_dir: Path = Path("runs-validation")
    output_dir: Path = DEFAULT_VALIDATION_DIR
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    max_tokens: int = 768
    write_artifacts: bool = True
    release_gate_mode: bool = False
    allow_unsafe_local_llm: bool = False
    split_config: Optional[SplitConfig] = None

    def __post_init__(self):
        if self.limit < 1:
            raise ValueError(
                f"Invalid limit: {self.limit}\n\n"
                f"What happened: Validation limit must be positive\n"
                f"Why: Need at least 1 question to validate\n\n"
                f"Fix: Set --limit to 1 or higher (e.g., --limit 10)"
            )
        if self.iterations < 1:
            raise ValueError(
                f"Invalid iterations: {self.iterations}\n\n"
                f"What happened: Iteration count must be positive\n"
                f"Why: Need at least 1 iteration to run validation\n\n"
                f"Fix: Set --iterations to 1 or higher (e.g., --iterations 3)"
            )
        if self.provider == "local-llm" and not self.allow_unsafe_local_llm:
            if self.limit > LOCAL_LLM_DEFAULT_MAX_LIMIT:
                raise ValidationSafetyError(
                    f"Safety limit exceeded for local-llm validation\n\n"
                    f"What happened: Requested {self.limit} questions, but limit is {LOCAL_LLM_DEFAULT_MAX_LIMIT}\n"
                    f"Why: Large local-llm runs can be slow and resource-intensive\n\n"
                    f"Next steps:\n"
                    f"1. Reduce --limit to {LOCAL_LLM_DEFAULT_MAX_LIMIT} or less, OR\n"
                    f"2. Add --allow-unsafe-local-llm flag to override (use with caution), OR\n"
                    f"3. Use --provider mock for faster testing without API calls\n\n"
                    f"Example: xrtm validate run --provider local-llm --limit {LOCAL_LLM_DEFAULT_MAX_LIMIT}"
                )


def run_validation(options: ValidationOptions) -> dict[str, Any]:
    """Run a corpus-based validation sweep and return structured metrics.

    This is the main entry point for large-scale validation runs. It:
    1. Validates corpus tier and release-gate compatibility
    2. Loads the corpus and applies splits if configured
    3. Runs multiple iterations of forecast/eval/train pipeline
    4. Aggregates metrics and produces structured artifacts

    Args:
        options: ValidationOptions configuration

    Returns:
        Structured validation report with metrics and artifacts

    Raises:
        ValidationTierError: If release-gate mode requires Tier 1 corpus
        ValidationSafetyError: If unsafe operations lack explicit opt-in
    """
    start_time = time.perf_counter()

    # Validate corpus selection and tier
    metadata = get_corpus_metadata(options.corpus_id)
    _validate_tier_compatibility(metadata, options)

    corpus_source = get_corpus(options.corpus_id)
    fetch_limit = options.limit
    if options.split or options.split_config:
        fetch_limit = metadata.size_estimate or max(options.limit, 1000)

    question_pool = asyncio.run(corpus_source.fetch_questions(limit=fetch_limit))
    availability = describe_corpus(options.corpus_id)
    split_signature = None
    selected_questions = question_pool[: options.limit]
    if options.split or options.split_config:
        splitter = CorpusSplitter(options.split_config or SplitConfig())
        splits = splitter.split_corpus(question_pool)
        split_signature = splitter.get_split_signature(question_pool)
        selected_questions = splits[options.split or "train"][: options.limit]
    if not selected_questions:
        raise ValueError(
            f"No questions available from corpus\n\n"
            f"What happened: Corpus '{options.corpus_id}' yielded 0 questions\n"
            f"Why: The corpus may be empty, or the split filter excluded all questions\n\n"
            f"Next steps:\n"
            f"1. Check corpus exists: xrtm validate list-corpora\n"
            f"2. Try without split filter: remove --split option\n"
            f"3. Verify corpus ID spelling: '{options.corpus_id}'\n\n"
            f"Configuration: split={options.split}, limit={options.limit}"
        )

    # Run iterations
    iteration_results = []

    for iteration in range(options.iterations):
        iter_start = time.perf_counter()

        result = run_pipeline(
            PipelineOptions(
                provider=options.provider,
                limit=len(selected_questions),
                questions=tuple(selected_questions),
                corpus_id=options.corpus_id,
                runs_dir=options.runs_dir,
                base_url=options.base_url,
                model=options.model,
                api_key=options.api_key,
                max_tokens=options.max_tokens,
                write_report=False,
                command=f"xrtm validate {options.corpus_id}",
            )
        )

        iter_duration = time.perf_counter() - iter_start

        iteration_results.append({
            "iteration": iteration + 1,
            "run_id": result.run.run_id,
            "duration_seconds": iter_duration,
            "forecast_records": result.forecast_records,
            "training_samples": result.training_samples,
            "eval_brier_score": result.eval_brier_score,
            "train_brier_score": result.train_brier_score,
        })

    total_duration = time.perf_counter() - start_time

    # Aggregate metrics
    report = _build_validation_report(
        options=options,
        metadata=metadata,
        availability=availability,
        iteration_results=iteration_results,
        total_duration=total_duration,
        split_signature=split_signature,
        question_pool_size=len(question_pool),
        selected_questions=len(selected_questions),
    )

    # Write artifacts if requested
    if options.write_artifacts:
        artifact_path = _write_validation_artifact(report, options.output_dir)
        report["artifact_path"] = str(artifact_path)

    return report


def _validate_tier_compatibility(metadata: Any, options: ValidationOptions) -> None:
    """Validate that corpus tier is compatible with validation mode."""
    if options.release_gate_mode:
        if not metadata.is_release_gate_approved():
            raise ValidationTierError(
                f"Corpus not approved for release-gate validation\n\n"
                f"What happened: Corpus '{metadata.corpus_id}' has tier {metadata.tier.value}\n"
                f"Why: Release gates require Tier 1 corpora with verified licensing\n\n"
                f"Next steps:\n"
                f"1. Remove --release-gate-mode flag for regular validation, OR\n"
                f"2. Use a Tier 1 corpus (run 'xrtm validate list-corpora --release-gate-only' to see approved corpora)\n\n"
                f"Current corpus: {metadata.corpus_id} ({metadata.tier.value}, {metadata.license_type.value})"
            )

    # Emit warning for non-Tier-1 usage
    if metadata.tier != CorpusTier.TIER_1:
        import warnings
        warnings.warn(
            f"Using {metadata.tier.value} corpus '{metadata.corpus_id}' with "
            f"{metadata.license_type.value} license. Not approved for release gates.",
            UserWarning,
            stacklevel=3,
        )


def _build_validation_report(
    *,
    options: ValidationOptions,
    metadata: Any,
    availability: Any,
    iteration_results: list[dict[str, Any]],
    total_duration: float,
    split_signature: Optional[str],
    question_pool_size: int,
    selected_questions: int,
) -> dict[str, Any]:
    """Build a structured validation report."""

    durations = [r["duration_seconds"] for r in iteration_results]
    total_forecasts = sum(r["forecast_records"] for r in iteration_results)

    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "validation_type": "corpus-sweep",
        "corpus": {
            "corpus_id": metadata.corpus_id,
            "name": metadata.name,
            "tier": metadata.tier.value,
            "license": metadata.license_type.value,
            "version": metadata.version,
            "release_gate_approved": metadata.release_gate_approved,
            "source_mode": availability.source_mode,
            "cached": availability.already_cached,
            "record_count": availability.record_count,
        },
        "configuration": {
            "split": options.split,
            "split_signature": split_signature,
            "provider": options.provider,
            "limit": options.limit,
            "selected_questions": selected_questions,
            "question_pool_size": question_pool_size,
            "iterations": options.iterations,
            "release_gate_mode": options.release_gate_mode,
        },
        "iterations": iteration_results,
        "summary": {
            "total_duration_seconds": total_duration,
            "mean_iteration_seconds": statistics.fmean(durations) if durations else 0.0,
            "max_iteration_seconds": max(durations) if durations else 0.0,
            "p95_iteration_seconds": _percentile(durations, 0.95) if durations else 0.0,
            "total_forecasts": total_forecasts,
            "forecasts_per_second": total_forecasts / total_duration if total_duration > 0 else 0.0,
        },
        "evaluation": {
            "mean_eval_brier": statistics.fmean([r["eval_brier_score"] for r in iteration_results if r["eval_brier_score"] is not None]) if iteration_results else None,
            "mean_train_brier": statistics.fmean([r["train_brier_score"] for r in iteration_results if r["train_brier_score"] is not None]) if iteration_results else None,
        },
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


def _percentile(values: list[float], percentile: float) -> float:
    """Calculate percentile from a list of values."""
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * percentile
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _write_validation_artifact(report: dict[str, Any], output_dir: Path) -> Path:
    """Write validation report to artifact directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    corpus_id = report["corpus"]["corpus_id"]
    artifact_path = output_dir / f"validation-{corpus_id}-{timestamp}.json"
    artifact_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact_path


def list_validation_corpora(
    tier: Optional[CorpusTier] = None,
    release_gate_only: bool = False,
) -> list[dict[str, Any]]:
    """List available corpora for validation with metadata.

    Args:
        tier: Filter by specific tier
        release_gate_only: Only show release-gate approved corpora

    Returns:
        List of corpus metadata dictionaries
    """
    corpora = list_available_corpora(tier=tier, release_gate_only=release_gate_only)
    return [m.to_dict() for m in corpora]


def prepare_validation_corpus(
    corpus_id: str,
    *,
    cache_root: Path | None = None,
    refresh: bool = False,
    use_hf_datasets: bool = True,
) -> dict[str, Any]:
    """Prepare an external corpus cache for product validation flows."""
    availability = prepare_corpus(
        corpus_id,
        cache_root=cache_root,
        refresh=refresh,
        use_hf_datasets=use_hf_datasets,
    )
    metadata = get_corpus_metadata(corpus_id)
    return {
        "corpus": {
            "corpus_id": metadata.corpus_id,
            "name": metadata.name,
            "tier": metadata.tier.value,
            "license": metadata.license_type.value,
            "release_gate_approved": metadata.release_gate_approved,
        },
        "availability": availability.to_dict(),
    }


__all__ = [
    "VALIDATION_SCHEMA_VERSION",
    "ValidationOptions",
    "ValidationTierError",
    "ValidationSafetyError",
    "run_validation",
    "list_validation_corpora",
    "prepare_validation_corpus",
]
