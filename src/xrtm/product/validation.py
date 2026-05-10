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

import ast
import asyncio
import hashlib
import json
import re
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.request import Request, urlopen

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
from xrtm.eval.core.eval.benchmark_artifacts import (
    BenchmarkComparisonRow,
    BenchmarkComparisonSnapshot,
    BenchmarkScoreSummary,
    ExternalComparisonRecord,
    ExternalLeaderboardEntry,
    ExternalLeaderboardSnapshot,
    ScoreInterval,
)
from xrtm.product.pipeline import PipelineOptions, run_pipeline
from xrtm.train.simulation.benchmark_artifacts import (
    BenchmarkRunResultBundle,
    BenchmarkRunSpec,
    BenchmarkSuiteArmResult,
    BenchmarkSuiteArmSpec,
    BenchmarkSuiteResult,
    BenchmarkSuiteSpec,
    ExternalBenchmarkLaneResult,
    ExternalBenchmarkLaneSpec,
    ExternalBenchmarkSourceSpec,
)

VALIDATION_SCHEMA_VERSION = "xrtm.validation.v1"
DEFAULT_VALIDATION_DIR = Path(".cache/validation")
BENCHMARK_COMPARE_SCHEMA_VERSION = "xrtm.benchmark-compare.v1"
DEFAULT_BENCHMARK_COMPARE_DIR = Path(".cache/benchmark")
LOCAL_LLM_DEFAULT_MAX_LIMIT = 10
FORECASTBENCH_BASELINE_BENCHMARK_ID = "forecastbench-baseline"
FORECASTBENCH_BASELINE_BENCHMARK_NAME = "ForecastBench Baseline Leaderboard"
FORECASTBENCH_BASELINE_LEADERBOARD_URL = "https://forecastbench.org/leaderboards"
FORECASTBENCH_BASELINE_JS_URL = "https://forecastbench.org/assets/js/leaderboard_baseline_full.js"
FORECASTBENCH_DOCS_URL = "https://forecastbench.org/docs/"

_FORECASTBENCH_HUMAN_BASELINE_MODELS = frozenset(
    {
        "Superforecaster median forecast",
        "Public median forecast",
    }
)
_FORECASTBENCH_DATA_PATTERN = re.compile(r"const data = (\[.*?\]);", re.DOTALL)


class ValidationTierError(RuntimeError):
    """Raised when attempting release-gate validation with non-approved corpus."""


class ValidationSafetyError(RuntimeError):
    """Raised when attempting unsafe operations without explicit override."""


@dataclass(frozen=True)
class ValidationOptions:
    """Configuration for a validation run."""

    corpus_id: str = "xrtm-real-binary-v1"
    command: str = "xrtm validate"
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


@dataclass(frozen=True)
class _ValidationSelection:
    metadata: Any
    availability: Any
    question_pool_size: int
    selected_questions: tuple[Any, ...]
    split_signature: str | None


@dataclass(frozen=True)
class BenchmarkArmOptions:
    """Configuration for one arm in a baseline-vs-candidate benchmark compare."""

    label: str
    provider: str = "mock"
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    max_tokens: int = 768


@dataclass(frozen=True)
class BenchmarkCompareOptions:
    """Configuration for a reproducible baseline-vs-candidate compare loop."""

    corpus_id: str = "xrtm-real-binary-v1"
    split: Optional[str] = None
    limit: int = 10
    runs_dir: Path = Path("runs-benchmark")
    output_dir: Path = DEFAULT_BENCHMARK_COMPARE_DIR
    release_gate_mode: bool = False
    allow_unsafe_local_llm: bool = False
    write_artifact: bool = True
    split_config: Optional[SplitConfig] = None
    baseline: BenchmarkArmOptions = field(default_factory=lambda: BenchmarkArmOptions(label="baseline"))
    candidate: BenchmarkArmOptions = field(default_factory=lambda: BenchmarkArmOptions(label="candidate"))

    def __post_init__(self):
        if self.limit < 1:
            raise ValueError("benchmark compare limit must be at least 1")


@dataclass(frozen=True)
class BenchmarkStressOptions:
    """Configuration for a repeated benchmark stress suite."""

    corpus_id: str = "xrtm-real-binary-v1"
    split: Optional[str] = None
    limit: int = 10
    repeat_count: int = 3
    runs_dir: Path = Path("runs-benchmark")
    output_dir: Path = DEFAULT_BENCHMARK_COMPARE_DIR
    release_gate_mode: bool = False
    allow_unsafe_local_llm: bool = False
    write_artifact: bool = True
    split_config: Optional[SplitConfig] = None
    arms: tuple[BenchmarkArmOptions, ...] = field(
        default_factory=lambda: (
            BenchmarkArmOptions(label="baseline"),
            BenchmarkArmOptions(label="candidate"),
        )
    )

    def __post_init__(self):
        if self.limit < 1:
            raise ValueError("benchmark stress limit must be at least 1")
        if self.repeat_count < 1:
            raise ValueError("benchmark stress repeat count must be at least 1")
        if len(self.arms) < 2:
            raise ValueError("benchmark stress requires at least 2 arms")
        labels = [arm.label for arm in self.arms]
        if len(set(labels)) != len(labels):
            raise ValueError("benchmark stress arm labels must be unique")


def run_validation(options: ValidationOptions) -> dict[str, Any]:
    """Run a corpus-based validation sweep and return structured metrics."""

    selection = _load_validation_selection(options)
    return _run_validation_with_selection(options, selection)


def _run_validation_with_selection(options: ValidationOptions, selection: _ValidationSelection) -> dict[str, Any]:
    start_time = time.perf_counter()
    iteration_results = _run_validation_iterations(options, selection.selected_questions)
    total_duration = time.perf_counter() - start_time

    report = _build_validation_report(
        options=options,
        metadata=selection.metadata,
        availability=selection.availability,
        iteration_results=iteration_results,
        total_duration=total_duration,
        split_signature=selection.split_signature,
        question_pool_size=selection.question_pool_size,
        selected_questions=len(selection.selected_questions),
    )
    return _attach_validation_artifact(report, options)


def _load_validation_selection(options: ValidationOptions) -> _ValidationSelection:
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

    return _ValidationSelection(
        metadata=metadata,
        availability=availability,
        question_pool_size=len(question_pool),
        selected_questions=tuple(selected_questions),
        split_signature=split_signature,
    )


def _run_validation_iterations(options: ValidationOptions, selected_questions: tuple[Any, ...]) -> list[dict[str, Any]]:
    return [
        _run_validation_iteration(options, selected_questions=selected_questions, iteration=iteration)
        for iteration in range(options.iterations)
    ]


def _run_validation_iteration(
    options: ValidationOptions,
    *,
    selected_questions: tuple[Any, ...],
    iteration: int,
) -> dict[str, Any]:
    iter_start = time.perf_counter()
    result = run_pipeline(
        PipelineOptions(
            provider=options.provider,
            limit=len(selected_questions),
            questions=selected_questions,
            corpus_id=options.corpus_id,
            runs_dir=options.runs_dir,
            base_url=options.base_url,
            model=options.model,
            api_key=options.api_key,
            max_tokens=options.max_tokens,
            write_report=False,
            command=f"{options.command} {options.corpus_id}",
        )
    )
    return {
        "iteration": iteration + 1,
        "run_id": result.run.run_id,
        "duration_seconds": time.perf_counter() - iter_start,
        "forecast_records": result.forecast_records,
        "training_samples": result.training_samples,
        "eval_brier_score": result.eval_brier_score,
        "train_brier_score": result.train_brier_score,
        "eval_ece": result.eval_summary.get("ece"),
        "eval_reliability": result.eval_summary.get("reliability"),
        "eval_resolution": result.eval_summary.get("resolution"),
        "eval_uncertainty": result.eval_summary.get("uncertainty"),
        "eval_slices": result.eval_slices,
        "resolved_count": result.eval_summary.get("resolved_count"),
    }


def _attach_validation_artifact(report: dict[str, Any], options: ValidationOptions) -> dict[str, Any]:
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
    eval_briers = [r["eval_brier_score"] for r in iteration_results if r["eval_brier_score"] is not None]
    train_briers = [r["train_brier_score"] for r in iteration_results if r["train_brier_score"] is not None]
    eval_eces = [r["eval_ece"] for r in iteration_results if r["eval_ece"] is not None]
    eval_reliabilities = [r["eval_reliability"] for r in iteration_results if r["eval_reliability"] is not None]
    eval_resolutions = [r["eval_resolution"] for r in iteration_results if r["eval_resolution"] is not None]
    eval_uncertainties = [r["eval_uncertainty"] for r in iteration_results if r["eval_uncertainty"] is not None]
    best_eval_run = _select_iteration(iteration_results, metric="eval_brier_score", prefer="lower")
    worst_eval_run = _select_iteration(iteration_results, metric="eval_brier_score", prefer="higher")

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
            "runs_dir": str(options.runs_dir),
            "output_dir": str(options.output_dir),
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
            "mean_eval_brier": statistics.fmean(eval_briers) if eval_briers else None,
            "best_eval_brier": min(eval_briers) if eval_briers else None,
            "worst_eval_brier": max(eval_briers) if eval_briers else None,
            "eval_brier_spread": (max(eval_briers) - min(eval_briers)) if len(eval_briers) > 1 else 0.0,
            "best_eval_run_id": best_eval_run.get("run_id") if best_eval_run else None,
            "worst_eval_run_id": worst_eval_run.get("run_id") if worst_eval_run else None,
            "mean_eval_ece": statistics.fmean(eval_eces) if eval_eces else None,
            "eval_ece_spread": (max(eval_eces) - min(eval_eces)) if len(eval_eces) > 1 else 0.0,
            "mean_eval_reliability": statistics.fmean(eval_reliabilities) if eval_reliabilities else None,
            "mean_eval_resolution": statistics.fmean(eval_resolutions) if eval_resolutions else None,
            "mean_eval_uncertainty": statistics.fmean(eval_uncertainties) if eval_uncertainties else None,
            "mean_train_brier": statistics.fmean(train_briers) if train_briers else None,
            "cohorts": _aggregate_cohort_metrics(iteration_results),
        },
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


def _select_iteration(
    iteration_results: list[dict[str, Any]],
    *,
    metric: str,
    prefer: str,
) -> dict[str, Any] | None:
    populated = [row for row in iteration_results if row.get(metric) is not None]
    if not populated:
        return None
    reverse = prefer == "higher"
    return sorted(populated, key=lambda row: float(row[metric]), reverse=reverse)[0]


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


def _aggregate_cohort_metrics(iteration_results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    aggregated: dict[str, dict[str, list[float] | int]] = {}
    for iteration in iteration_results:
        for cohort_name, cohort_report in (iteration.get("eval_slices") or {}).items():
            bucket = aggregated.setdefault(
                cohort_name,
                {
                    "mean_scores": [],
                    "eces": [],
                    "sample_size": 0,
                },
            )
            mean_score = cohort_report.get("mean_score")
            if mean_score is not None:
                bucket["mean_scores"].append(float(mean_score))
            ece = cohort_report.get("summary_statistics", {}).get("ece")
            if ece is not None:
                bucket["eces"].append(float(ece))
            bucket["sample_size"] = max(int(bucket["sample_size"]), int(cohort_report.get("total_evaluations") or 0))

    return {
        cohort_name: {
            "mean_eval_brier": statistics.fmean(bucket["mean_scores"]) if bucket["mean_scores"] else None,
            "mean_eval_ece": statistics.fmean(bucket["eces"]) if bucket["eces"] else None,
            "sample_size": int(bucket["sample_size"]),
        }
        for cohort_name, bucket in aggregated.items()
    }


def _write_validation_artifact(report: dict[str, Any], output_dir: Path) -> Path:
    """Write validation report to artifact directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    corpus_id = report["corpus"]["corpus_id"]
    artifact_path = _next_validation_artifact_path(output_dir=output_dir, corpus_id=corpus_id, timestamp=timestamp)
    artifact_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact_path


def _next_validation_artifact_path(*, output_dir: Path, corpus_id: str, timestamp: str) -> Path:
    """Return a validation artifact path that avoids same-second collisions."""
    base_name = f"validation-{corpus_id}-{timestamp}"
    for attempt in range(1000):
        suffix = "" if attempt == 0 else f"-{attempt:02d}"
        candidate = output_dir / f"{base_name}{suffix}.json"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Failed to allocate validation artifact path under {output_dir}")


def list_validation_corpora(
    tier: Optional[CorpusTier] = None,
    release_gate_only: bool = False,
) -> list[dict[str, Any]]:
    """List available corpora for validation with metadata."""

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


def capture_forecastbench_baseline_reference(
    output_dir: Path = Path(".cache/benchmark-review"),
    *,
    fetcher: Callable[[str], str] | None = None,
    captured_at: datetime | None = None,
) -> dict[str, Any]:
    """Capture the public ForecastBench baseline leaderboard into XRTM artifacts."""
    resolved_captured_at = captured_at or datetime.now(timezone.utc)
    resolved_fetcher = fetcher or _fetch_public_text
    raw_js = resolved_fetcher(FORECASTBENCH_BASELINE_JS_URL)
    rows = _parse_forecastbench_leaderboard_rows(raw_js)
    if not rows:
        raise ValueError("ForecastBench baseline leaderboard did not contain any rows")

    source_sha256 = hashlib.sha256(raw_js.encode("utf-8")).hexdigest()
    source_version = source_sha256[:16]
    top_human_row = next(
        (row for row in rows if _is_forecastbench_human_baseline(str(row.get("Model") or ""))),
        None,
    )
    baseline_name = str(top_human_row.get("Model")) if top_human_row is not None else None
    baseline_score = _float_or_none(top_human_row.get("Overall")) if top_human_row is not None else None

    leaderboard_snapshot = ExternalLeaderboardSnapshot(
        benchmark_id=FORECASTBENCH_BASELINE_BENCHMARK_ID,
        benchmark_name=FORECASTBENCH_BASELINE_BENCHMARK_NAME,
        source_name="ForecastBench",
        captured_at=resolved_captured_at,
        source_url=FORECASTBENCH_BASELINE_LEADERBOARD_URL,
        source_version=source_version,
        scoring_rule="higher-is-better",
        entries=[
            ExternalLeaderboardEntry(
                system_id=_forecastbench_system_id(row),
                display_name=str(row.get("Model") or "unknown"),
                rank=int(row["Rank"]) if row.get("Rank") is not None else None,
                score_name="overall_brier_index",
                score=float(row["Overall"]),
                sample_size=int(row["N"]) if row.get("N") is not None else None,
                metadata=_forecastbench_row_metadata(row, source_sha256=source_sha256),
            )
            for row in rows
            if row.get("Overall") is not None
        ],
        metadata={
            "leaderboard_kind": "baseline",
            "docs_url": FORECASTBENCH_DOCS_URL,
            "source_asset_url": FORECASTBENCH_BASELINE_JS_URL,
            "source_sha256": source_sha256,
            "comparison_semantics": "official-difficulty-adjusted-public-reference",
            "identical_question_sets": False,
        },
    )

    comparisons = [
        ExternalComparisonRecord(
            benchmark_id=FORECASTBENCH_BASELINE_BENCHMARK_ID,
            benchmark_name=FORECASTBENCH_BASELINE_BENCHMARK_NAME,
            system_id=_forecastbench_system_id(row),
            display_name=str(row.get("Model") or "unknown"),
            reporting_lane=(
                "public-human-baseline"
                if _is_forecastbench_human_baseline(str(row.get("Model") or ""))
                else "public-leaderboard"
            ),
            primary_score_name="overall_brier_index",
            primary_score=float(row["Overall"]),
            captured_at=resolved_captured_at,
            source_name="ForecastBench",
            source_id=f"{FORECASTBENCH_BASELINE_BENCHMARK_ID}:{source_version}:{_forecastbench_system_id(row)}",
            source_url=FORECASTBENCH_BASELINE_LEADERBOARD_URL,
            source_version=source_version,
            rank=int(row["Rank"]) if row.get("Rank") is not None else None,
            sample_size=int(row["N"]) if row.get("N") is not None else None,
            baseline_name=baseline_name if baseline_name and str(row.get("Model")) != baseline_name else None,
            delta_vs_baseline=(
                None
                if baseline_score is None or str(row.get("Model")) == baseline_name
                else float(row["Overall"]) - baseline_score
            ),
            score_summary=BenchmarkScoreSummary(
                metric_name="Brier Index",
                primary_score_name="overall_brier_index",
                primary_score=float(row["Overall"]),
                sample_size=int(row["N"]) if row.get("N") is not None else 0,
                confidence_interval=_parse_forecastbench_interval(row.get("Overall 95% CI")),
                notes=_forecastbench_common_notes(model_name=str(row.get("Model") or "")),
                metadata=_forecastbench_row_metadata(row, source_sha256=source_sha256),
            ),
            notes=_forecastbench_common_notes(model_name=str(row.get("Model") or "")),
            metadata=_forecastbench_row_metadata(row, source_sha256=source_sha256),
        )
        for row in rows
        if row.get("Overall") is not None
    ]

    result = ExternalBenchmarkLaneResult(
        started_at=resolved_captured_at,
        completed_at=resolved_captured_at,
        spec=ExternalBenchmarkLaneSpec(
            lane_id=f"{FORECASTBENCH_BASELINE_BENCHMARK_ID}-{resolved_captured_at.strftime('%Y%m%dT%H%M%SZ')}",
            benchmark_id=FORECASTBENCH_BASELINE_BENCHMARK_ID,
            benchmark_name=FORECASTBENCH_BASELINE_BENCHMARK_NAME,
            output_dir=output_dir,
            sources=[
                ExternalBenchmarkSourceSpec(
                    source_id="forecastbench-human-baselines",
                    display_name="ForecastBench human baselines",
                    reporting_lane="public-human-baseline",
                    source_name="ForecastBench",
                    source_url=FORECASTBENCH_BASELINE_LEADERBOARD_URL,
                    source_version=source_version,
                    scoring_rule="higher-is-better",
                    refresh_notes=(
                        "Official public baseline leaderboard; comparisons are difficulty-adjusted "
                        "and not a locally rerun identical-question XRTM benchmark."
                    ),
                ),
                ExternalBenchmarkSourceSpec(
                    source_id="forecastbench-baseline-leaderboard",
                    display_name="ForecastBench baseline leaderboard",
                    reporting_lane="public-leaderboard",
                    source_name="ForecastBench",
                    source_url=FORECASTBENCH_BASELINE_LEADERBOARD_URL,
                    source_version=source_version,
                    scoring_rule="higher-is-better",
                    refresh_notes=(
                        "Official public baseline leaderboard; comparisons are difficulty-adjusted "
                        "and not a locally rerun identical-question XRTM benchmark."
                    ),
                ),
            ],
            metadata={
                "docs_url": FORECASTBENCH_DOCS_URL,
                "source_asset_url": FORECASTBENCH_BASELINE_JS_URL,
            },
        ),
        comparisons=comparisons,
        leaderboards=[leaderboard_snapshot],
        metadata={
            "source_sha256": source_sha256,
            "comparison_semantics": "official-difficulty-adjusted-public-reference",
            "identical_question_sets": False,
            "baseline_reference": baseline_name,
        },
    )
    scorecard = result.to_public_scorecard_snapshot(
        metadata={
            "source_sha256": source_sha256,
            "leaderboard_url": FORECASTBENCH_BASELINE_LEADERBOARD_URL,
            "docs_url": FORECASTBENCH_DOCS_URL,
        }
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = resolved_captured_at.strftime("%Y%m%dT%H%M%SZ")
    source_path = _next_public_benchmark_artifact_path(
        output_dir=output_dir,
        base_name=f"public-source-{FORECASTBENCH_BASELINE_BENCHMARK_ID}",
        timestamp=timestamp,
        extension="js",
    )
    result_path = _next_public_benchmark_artifact_path(
        output_dir=output_dir,
        base_name=f"public-benchmark-{FORECASTBENCH_BASELINE_BENCHMARK_ID}",
        timestamp=timestamp,
        extension="json",
    )
    scorecard_path = _next_public_benchmark_artifact_path(
        output_dir=output_dir,
        base_name=f"public-scorecard-{FORECASTBENCH_BASELINE_BENCHMARK_ID}",
        timestamp=timestamp,
        extension="json",
    )
    source_path.write_text(raw_js.rstrip() + "\n", encoding="utf-8")
    result.artifact_paths = [source_path, result_path, scorecard_path]
    result_path.write_text(json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    scorecard_path.write_text(
        json.dumps(scorecard.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "schema_version": "xrtm.public-benchmark-reference.v1",
        "artifact_paths": [str(path) for path in result.artifact_paths],
        "lane_result": result.model_dump(mode="json"),
        "public_scorecard": scorecard.model_dump(mode="json"),
    }


def run_benchmark_compare(options: BenchmarkCompareOptions) -> dict[str, Any]:
    """Run a frozen baseline-vs-candidate benchmark compare and emit an artifact."""
    selection = _load_benchmark_selection(options)
    baseline_bundle = _run_compare_arm(options=options, arm=options.baseline, selection=selection)
    candidate_bundle = _run_compare_arm(options=options, arm=options.candidate, selection=selection)

    report = {
        "schema_version": BENCHMARK_COMPARE_SCHEMA_VERSION,
        "benchmark": {
            "corpus_id": selection.metadata.corpus_id,
            "name": selection.metadata.name,
            "version": selection.metadata.version,
            "tier": selection.metadata.tier.value,
            "license": selection.metadata.license_type.value,
            "split": options.split or "full",
            "split_signature": selection.split_signature,
            "source_mode": selection.availability.source_mode,
            "question_pool_size": selection.question_pool_size,
            "selected_questions": len(selection.selected_questions),
            "release_gate_mode": options.release_gate_mode,
        },
        "baseline": baseline_bundle.model_dump(mode="json"),
        "candidate": candidate_bundle.model_dump(mode="json"),
        "comparison": _benchmark_compare_summary(baseline_bundle=baseline_bundle, candidate_bundle=candidate_bundle),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    if options.write_artifact:
        artifact_path = _write_benchmark_compare_artifact(report, options.output_dir)
        report["artifact_path"] = str(artifact_path)
    return report


def run_benchmark_stress_suite(options: BenchmarkStressOptions) -> dict[str, Any]:
    """Run a repeated multi-arm benchmark suite on one frozen corpus selection."""
    selection = _load_benchmark_selection(options)
    started_at = datetime.now(timezone.utc)
    suite_id = f"{selection.metadata.corpus_id}-{started_at.strftime('%Y%m%dT%H%M%SZ')}"
    spec = BenchmarkSuiteSpec(
        suite_id=suite_id,
        benchmark_id=selection.metadata.corpus_id,
        benchmark_name=selection.metadata.name,
        corpus_id=selection.metadata.corpus_id,
        corpus_version=selection.metadata.version,
        source_mode=selection.availability.source_mode,
        split=options.split or "full",
        split_signature=selection.split_signature,
        run_limit=len(selection.selected_questions),
        repeat_count=options.repeat_count,
        release_gate_mode=options.release_gate_mode,
        baseline_arm_id=options.arms[0].label,
        runs_dir=options.runs_dir,
        output_dir=options.output_dir,
        arms=[
            BenchmarkSuiteArmSpec(
                arm_id=arm.label,
                display_name=arm.label,
                provider=arm.provider,
                model=arm.model,
                max_tokens=arm.max_tokens,
                tags=[arm.label, selection.metadata.tier.value],
                metadata={"base_url": arm.base_url},
            )
            for arm in options.arms
        ],
        metadata={
            "question_pool_size": selection.question_pool_size,
            "selected_questions": len(selection.selected_questions),
        },
    )

    arm_results = [
        _run_stress_arm(
            options=options,
            arm=arm,
            selection=selection,
            arm_spec=next(spec_arm for spec_arm in spec.arms if spec_arm.arm_id == arm.label),
        )
        for arm in options.arms
    ]
    comparison = _build_stress_comparison(spec=spec, arm_results=arm_results)
    completed_at = datetime.now(timezone.utc)
    artifact_path: Path | None = None
    warnings = sorted({warning for result in arm_results for warning in result.warnings})
    suite = BenchmarkSuiteResult(
        started_at=started_at,
        completed_at=completed_at,
        spec=spec,
        arm_results=arm_results,
        comparison=comparison,
        warnings=warnings,
        metadata={
            "question_pool_size": selection.question_pool_size,
            "selected_questions": len(selection.selected_questions),
            "source_mode": selection.availability.source_mode,
        },
    )
    if options.write_artifact:
        artifact_path = _write_benchmark_stress_artifact(suite.model_dump(mode="json"), options.output_dir, options.corpus_id)
        suite.artifact_paths.append(artifact_path)
    report = suite.model_dump(mode="json")
    if artifact_path is not None:
        report["artifact_path"] = str(artifact_path)
    return report


def _run_compare_arm(
    *,
    options: BenchmarkCompareOptions,
    arm: BenchmarkArmOptions,
    selection: _ValidationSelection,
) -> BenchmarkRunResultBundle:
    report, started_at, completed_at = _run_benchmark_arm_validation(
        options=options,
        arm=arm,
        selection=selection,
        command=f"xrtm benchmark compare --arm {arm.label}",
    )
    return _build_run_result_bundle(
        report=report,
        arm=arm,
        selection=selection,
        split=options.split,
        release_gate_mode=options.release_gate_mode,
        output_dir=options.output_dir,
        runs_dir=options.runs_dir,
        started_at=started_at,
        completed_at=completed_at,
    )


def _run_stress_arm(
    *,
    options: BenchmarkStressOptions,
    arm: BenchmarkArmOptions,
    selection: _ValidationSelection,
    arm_spec: BenchmarkSuiteArmSpec,
) -> BenchmarkSuiteArmResult:
    runs: list[BenchmarkRunResultBundle] = []
    for repeat_index in range(options.repeat_count):
        report, started_at, completed_at = _run_benchmark_arm_validation(
            options=options,
            arm=arm,
            selection=selection,
            command=f"xrtm benchmark stress --arm {arm.label} --repeat {repeat_index + 1}",
        )
        runs.append(
            _build_run_result_bundle(
                report=report,
                arm=arm,
                selection=selection,
                split=options.split,
                release_gate_mode=options.release_gate_mode,
                output_dir=options.output_dir,
                runs_dir=options.runs_dir,
                started_at=started_at,
                completed_at=completed_at,
            )
        )
    systems_summary = _aggregate_stress_systems(runs)
    warnings = sorted({warning for run in runs for warning in run.warnings})
    score_summary = _aggregate_stress_scores(runs, systems_summary=systems_summary)
    return BenchmarkSuiteArmResult(
        arm=arm_spec,
        score_summary=score_summary,
        runs=runs,
        systems_summary=systems_summary,
        warnings=warnings,
        metadata={"repeat_count": options.repeat_count},
    )


def _load_benchmark_selection(options: BenchmarkCompareOptions | BenchmarkStressOptions) -> _ValidationSelection:
    return _load_validation_selection(_benchmark_selection_options(options))


def _benchmark_selection_options(options: BenchmarkCompareOptions | BenchmarkStressOptions) -> ValidationOptions:
    return ValidationOptions(
        corpus_id=options.corpus_id,
        split=options.split,
        limit=options.limit,
        write_artifacts=False,
        release_gate_mode=options.release_gate_mode,
        allow_unsafe_local_llm=options.allow_unsafe_local_llm,
        split_config=options.split_config,
    )


def _run_benchmark_arm_validation(
    *,
    options: BenchmarkCompareOptions | BenchmarkStressOptions,
    arm: BenchmarkArmOptions,
    selection: _ValidationSelection,
    command: str,
) -> tuple[dict[str, Any], datetime, datetime]:
    started_at = datetime.now(timezone.utc)
    report = _run_validation_with_selection(
        _benchmark_arm_validation_options(options=options, arm=arm, selection=selection, command=command),
        selection,
    )
    return report, started_at, datetime.now(timezone.utc)


def _benchmark_arm_validation_options(
    *,
    options: BenchmarkCompareOptions | BenchmarkStressOptions,
    arm: BenchmarkArmOptions,
    selection: _ValidationSelection,
    command: str,
) -> ValidationOptions:
    return ValidationOptions(
        corpus_id=options.corpus_id,
        command=command,
        split=options.split,
        provider=arm.provider,
        limit=len(selection.selected_questions),
        iterations=1,
        runs_dir=options.runs_dir,
        output_dir=options.output_dir,
        base_url=arm.base_url,
        model=arm.model,
        api_key=arm.api_key,
        max_tokens=arm.max_tokens,
        write_artifacts=False,
        release_gate_mode=options.release_gate_mode,
        allow_unsafe_local_llm=options.allow_unsafe_local_llm,
        split_config=options.split_config,
    )


def _build_run_result_bundle(
    *,
    report: dict[str, Any],
    arm: BenchmarkArmOptions,
    selection: _ValidationSelection,
    split: str | None,
    release_gate_mode: bool,
    output_dir: Path,
    runs_dir: Path,
    started_at: datetime,
    completed_at: datetime,
) -> BenchmarkRunResultBundle:
    evaluation = report["evaluation"]
    notes = [f"source_mode={report['corpus']['source_mode']}"]
    if report["corpus"]["source_mode"] == "preview":
        notes.append("preview_fixture_only")
    run_ids = [str(item["run_id"]) for item in report["iterations"] if item.get("run_id")]
    return BenchmarkRunResultBundle(
        started_at=started_at,
        completed_at=completed_at,
        spec=BenchmarkRunSpec(
            benchmark_id=selection.metadata.corpus_id,
            benchmark_name=selection.metadata.name,
            corpus_id=selection.metadata.corpus_id,
            corpus_version=selection.metadata.version,
            source_mode=selection.availability.source_mode,
            split=split or "full",
            provider=arm.provider,
            model=arm.model,
            strategy_id=arm.label,
            run_limit=len(selection.selected_questions),
            iterations=1,
            release_gate_mode=release_gate_mode,
            output_dir=output_dir,
            tags=[arm.label, selection.metadata.tier.value],
            metadata={
                "split_signature": selection.split_signature,
                "question_pool_size": selection.question_pool_size,
                "runs_dir": str(runs_dir),
            },
        ),
        score_summary=BenchmarkScoreSummary(
            metric_name="Real Binary Forecast Brier Score",
            primary_score_name="eval_brier",
            primary_score=float(evaluation.get("mean_eval_brier") or 0.0),
            sample_size=int(report["summary"]["total_forecasts"]),
            calibration_error=evaluation.get("mean_eval_ece"),
            reliability=evaluation.get("mean_eval_reliability"),
            resolution=evaluation.get("mean_eval_resolution"),
            uncertainty=evaluation.get("mean_eval_uncertainty"),
            notes=notes,
            metadata={
                "cohorts": evaluation.get("cohorts", {}),
                "systems": _read_run_systems(runs_dir, run_ids),
            },
        ),
        run_ids=run_ids,
        warnings=notes[1:] if len(notes) > 1 else [],
        metadata={"report": report},
    )


def _benchmark_compare_summary(
    *,
    baseline_bundle: BenchmarkRunResultBundle,
    candidate_bundle: BenchmarkRunResultBundle,
) -> dict[str, Any]:
    baseline_score = baseline_bundle.score_summary.primary_score
    candidate_score = candidate_bundle.score_summary.primary_score
    baseline_ece = baseline_bundle.score_summary.calibration_error
    candidate_ece = candidate_bundle.score_summary.calibration_error
    baseline_reliability = baseline_bundle.score_summary.reliability
    candidate_reliability = candidate_bundle.score_summary.reliability
    baseline_resolution = baseline_bundle.score_summary.resolution
    candidate_resolution = candidate_bundle.score_summary.resolution
    baseline_cohorts = baseline_bundle.score_summary.metadata.get("cohorts", {})
    candidate_cohorts = candidate_bundle.score_summary.metadata.get("cohorts", {})
    return {
        "primary_metric": "eval_brier",
        "direction": "lower-is-better",
        "baseline_primary_score": baseline_score,
        "candidate_primary_score": candidate_score,
        "delta_primary_score": candidate_score - baseline_score,
        "baseline_eval_ece": baseline_ece,
        "candidate_eval_ece": candidate_ece,
        "delta_eval_ece": _metric_delta(candidate_ece, baseline_ece),
        "baseline_reliability": baseline_reliability,
        "candidate_reliability": candidate_reliability,
        "delta_reliability": _metric_delta(candidate_reliability, baseline_reliability),
        "baseline_resolution": baseline_resolution,
        "candidate_resolution": candidate_resolution,
        "delta_resolution": _metric_delta(candidate_resolution, baseline_resolution),
        "candidate_beats_baseline": candidate_score < baseline_score,
        "cohort_deltas": _cohort_deltas(baseline_cohorts=baseline_cohorts, candidate_cohorts=candidate_cohorts),
    }


def _aggregate_stress_scores(
    runs: list[BenchmarkRunResultBundle],
    *,
    systems_summary: dict[str, Any],
) -> BenchmarkScoreSummary:
    primary_scores = [run.score_summary.primary_score for run in runs]
    calibration_errors = [value for value in (run.score_summary.calibration_error for run in runs) if value is not None]
    reliabilities = [value for value in (run.score_summary.reliability for run in runs) if value is not None]
    resolutions = [value for value in (run.score_summary.resolution for run in runs) if value is not None]
    uncertainties = [value for value in (run.score_summary.uncertainty for run in runs) if value is not None]
    cohorts = _merge_cohort_metrics([run.score_summary.metadata.get("cohorts", {}) for run in runs])
    return BenchmarkScoreSummary(
        metric_name=runs[0].score_summary.metric_name,
        primary_score_name=runs[0].score_summary.primary_score_name,
        primary_score=statistics.fmean(primary_scores),
        sample_size=sum(run.score_summary.sample_size for run in runs),
        calibration_error=statistics.fmean(calibration_errors) if calibration_errors else None,
        reliability=statistics.fmean(reliabilities) if reliabilities else None,
        resolution=statistics.fmean(resolutions) if resolutions else None,
        uncertainty=statistics.fmean(uncertainties) if uncertainties else None,
        notes=sorted({note for run in runs for note in run.score_summary.notes}),
        metadata={
            "repeat_count": len(runs),
            "score_spread": (max(primary_scores) - min(primary_scores)) if len(primary_scores) > 1 else 0.0,
            "cohorts": cohorts,
            "systems": systems_summary,
        },
    )


def _merge_cohort_metrics(cohort_payloads: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, dict[str, list[float] | int]] = {}
    for payload in cohort_payloads:
        for cohort_name, values in payload.items():
            bucket = buckets.setdefault(cohort_name, {"brier": [], "ece": [], "sample_size": 0})
            mean_eval_brier = values.get("mean_eval_brier")
            if mean_eval_brier is not None:
                bucket["brier"].append(float(mean_eval_brier))
            mean_eval_ece = values.get("mean_eval_ece")
            if mean_eval_ece is not None:
                bucket["ece"].append(float(mean_eval_ece))
            bucket["sample_size"] = max(int(bucket["sample_size"]), int(values.get("sample_size") or 0))
    return {
        cohort_name: {
            "mean_eval_brier": statistics.fmean(bucket["brier"]) if bucket["brier"] else None,
            "mean_eval_ece": statistics.fmean(bucket["ece"]) if bucket["ece"] else None,
            "sample_size": int(bucket["sample_size"]),
        }
        for cohort_name, bucket in buckets.items()
    }


def _aggregate_stress_systems(runs: list[BenchmarkRunResultBundle]) -> dict[str, Any]:
    reports = [run.score_summary.metadata.get("systems", {}) for run in runs]
    durations = [value for value in (report.get("duration_seconds") for report in reports) if value is not None]
    throughputs = [value for value in (report.get("forecasts_per_second") for report in reports) if value is not None]
    token_totals = [value for value in (report.get("total_tokens") for report in reports) if value is not None]
    cache_hit_rates = [value for value in (report.get("cache_hit_rate") for report in reports) if value is not None]
    provider_latencies = [value for value in (report.get("provider_latency_mean_ms") for report in reports) if value is not None]
    warning_counts = [int(report.get("warning_count") or 0) for report in reports]
    error_counts = [int(report.get("error_count") or 0) for report in reports]
    return {
        "mean_duration_seconds": statistics.fmean(durations) if durations else None,
        "mean_forecasts_per_second": statistics.fmean(throughputs) if throughputs else None,
        "mean_total_tokens": statistics.fmean(token_totals) if token_totals else None,
        "mean_cache_hit_rate": statistics.fmean(cache_hit_rates) if cache_hit_rates else None,
        "mean_provider_latency_ms": statistics.fmean(provider_latencies) if provider_latencies else None,
        "total_warning_count": sum(warning_counts),
        "total_error_count": sum(error_counts),
    }


def _build_stress_comparison(
    *,
    spec: BenchmarkSuiteSpec,
    arm_results: list[BenchmarkSuiteArmResult],
) -> BenchmarkComparisonSnapshot:
    baseline = next(
        (arm_result for arm_result in arm_results if arm_result.arm.arm_id == spec.baseline_arm_id),
        arm_results[0],
    )
    rows: list[BenchmarkComparisonRow] = []
    metrics = [
        ("eval_brier", "lower-is-better", baseline.score_summary.primary_score, "primary_score"),
        ("eval_ece", "lower-is-better", baseline.score_summary.calibration_error, "calibration_error"),
        ("duration_seconds", "lower-is-better", baseline.systems_summary.get("mean_duration_seconds"), "mean_duration_seconds"),
        (
            "forecasts_per_second",
            "higher-is-better",
            baseline.systems_summary.get("mean_forecasts_per_second"),
            "mean_forecasts_per_second",
        ),
        ("total_tokens", "lower-is-better", baseline.systems_summary.get("mean_total_tokens"), "mean_total_tokens"),
        ("cache_hit_rate", "higher-is-better", baseline.systems_summary.get("mean_cache_hit_rate"), "mean_cache_hit_rate"),
        (
            "provider_latency_ms",
            "lower-is-better",
            baseline.systems_summary.get("mean_provider_latency_ms"),
            "mean_provider_latency_ms",
        ),
    ]
    for candidate in arm_results[1:]:
        for metric_name, direction, baseline_value, candidate_key in metrics:
            candidate_value = (
                getattr(candidate.score_summary, candidate_key)
                if hasattr(candidate.score_summary, candidate_key)
                else candidate.systems_summary.get(candidate_key)
            )
            rows.append(
                BenchmarkComparisonRow(
                    metric_name=metric_name,
                    baseline_system_id=baseline.arm.arm_id,
                    candidate_system_id=candidate.arm.arm_id,
                    direction=direction,
                    baseline_value=_float_or_none(baseline_value),
                    candidate_value=_float_or_none(candidate_value),
                    delta=_directional_delta(_float_or_none(candidate_value), _float_or_none(baseline_value)),
                    interpretation=_comparison_interpretation(
                        metric_name=metric_name,
                        direction=direction,
                        baseline_label=baseline.arm.display_name,
                        candidate_label=candidate.arm.display_name,
                        baseline_value=_float_or_none(baseline_value),
                        candidate_value=_float_or_none(candidate_value),
                    ),
                    metadata={"repeat_count": spec.repeat_count},
                )
            )
    return BenchmarkComparisonSnapshot(
        benchmark_id=spec.benchmark_id,
        benchmark_name=spec.benchmark_name,
        rows=rows,
        metadata={"suite_id": spec.suite_id, "baseline_arm_id": spec.baseline_arm_id},
    )


def _metric_delta(candidate_value: float | None, baseline_value: float | None) -> float | None:
    if candidate_value is None or baseline_value is None:
        return None
    return candidate_value - baseline_value


def _directional_delta(candidate_value: float | None, baseline_value: float | None) -> float | None:
    return _metric_delta(candidate_value, baseline_value)


def _comparison_interpretation(
    *,
    metric_name: str,
    direction: str,
    baseline_label: str,
    candidate_label: str,
    baseline_value: float | None,
    candidate_value: float | None,
) -> str:
    if baseline_value is None or candidate_value is None:
        return f"{metric_name} unavailable"
    if candidate_value == baseline_value:
        return f"{metric_name} tied"
    candidate_better = candidate_value < baseline_value if direction == "lower-is-better" else candidate_value > baseline_value
    better_label = candidate_label if candidate_better else baseline_label
    return f"{direction.replace('-', ' ')}; {better_label} improved"


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _cohort_deltas(
    *,
    baseline_cohorts: dict[str, Any],
    candidate_cohorts: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    shared = sorted(set(baseline_cohorts) & set(candidate_cohorts))
    return {
        cohort_name: {
            "baseline_mean_eval_brier": baseline_cohorts[cohort_name].get("mean_eval_brier"),
            "candidate_mean_eval_brier": candidate_cohorts[cohort_name].get("mean_eval_brier"),
            "delta_mean_eval_brier": _metric_delta(
                candidate_cohorts[cohort_name].get("mean_eval_brier"),
                baseline_cohorts[cohort_name].get("mean_eval_brier"),
            ),
            "baseline_mean_eval_ece": baseline_cohorts[cohort_name].get("mean_eval_ece"),
            "candidate_mean_eval_ece": candidate_cohorts[cohort_name].get("mean_eval_ece"),
            "delta_mean_eval_ece": _metric_delta(
                candidate_cohorts[cohort_name].get("mean_eval_ece"),
                baseline_cohorts[cohort_name].get("mean_eval_ece"),
            ),
            "sample_size": min(
                int(baseline_cohorts[cohort_name].get("sample_size") or 0),
                int(candidate_cohorts[cohort_name].get("sample_size") or 0),
            ),
        }
        for cohort_name in shared
    }


def _write_benchmark_compare_artifact(report: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    corpus_id = report["benchmark"]["corpus_id"]
    artifact_path = _next_benchmark_compare_artifact_path(output_dir=output_dir, corpus_id=corpus_id, timestamp=timestamp)
    artifact_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact_path


def _next_benchmark_compare_artifact_path(*, output_dir: Path, corpus_id: str, timestamp: str) -> Path:
    base_name = f"benchmark-compare-{corpus_id}-{timestamp}"
    for attempt in range(1000):
        suffix = "" if attempt == 0 else f"-{attempt:02d}"
        candidate = output_dir / f"{base_name}{suffix}.json"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Failed to allocate benchmark compare artifact path under {output_dir}")


def _write_benchmark_stress_artifact(report: dict[str, Any], output_dir: Path, corpus_id: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    artifact_path = _next_benchmark_stress_artifact_path(output_dir=output_dir, corpus_id=corpus_id, timestamp=timestamp)
    artifact_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact_path


def _next_benchmark_stress_artifact_path(*, output_dir: Path, corpus_id: str, timestamp: str) -> Path:
    base_name = f"benchmark-stress-{corpus_id}-{timestamp}"
    for attempt in range(1000):
        suffix = "" if attempt == 0 else f"-{attempt:02d}"
        candidate = output_dir / f"{base_name}{suffix}.json"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Failed to allocate benchmark stress artifact path under {output_dir}")


def _next_public_benchmark_artifact_path(
    *,
    output_dir: Path,
    base_name: str,
    timestamp: str,
    extension: str,
) -> Path:
    for attempt in range(1000):
        suffix = "" if attempt == 0 else f"-{attempt:02d}"
        candidate = output_dir / f"{base_name}-{timestamp}{suffix}.{extension}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Failed to allocate public benchmark artifact path under {output_dir}")


def _fetch_public_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "xrtm-public-benchmark-capture/1.0"})
    with urlopen(request, timeout=30) as response:
        payload = response.read().decode("utf-8")
    if not payload:
        raise ValueError(f"Empty response from public benchmark source: {url}")
    return payload


def _parse_forecastbench_leaderboard_rows(payload: str) -> list[dict[str, Any]]:
    match = _FORECASTBENCH_DATA_PATTERN.search(payload)
    if match is None:
        raise ValueError("Unable to locate ForecastBench leaderboard data array")
    literal = match.group(1)
    python_literal = re.sub(r"\bnull\b", "None", literal)
    python_literal = re.sub(r"\btrue\b", "True", python_literal)
    python_literal = re.sub(r"\bfalse\b", "False", python_literal)
    rows = ast.literal_eval(python_literal)
    if not isinstance(rows, list):
        raise ValueError("ForecastBench leaderboard data payload was not a list")
    return [dict(row) for row in rows if isinstance(row, dict)]


def _is_forecastbench_human_baseline(model_name: str) -> bool:
    return model_name.strip() in _FORECASTBENCH_HUMAN_BASELINE_MODELS


def _forecastbench_system_id(row: dict[str, Any]) -> str:
    org = str(row.get("Model Organization") or "forecastbench").lower()
    model = str(row.get("Model") or "unknown").lower()
    return re.sub(r"[^a-z0-9]+", "-", f"{org}-{model}").strip("-")


def _forecastbench_row_metadata(row: dict[str, Any], *, source_sha256: str) -> dict[str, Any]:
    return {
        "model_organization": row.get("Model Organization"),
        "team_name": row.get("Team Name"),
        "dataset_brier_index": _float_or_none(row.get("Dataset")),
        "dataset_sample_size": int(row["N dataset"]) if row.get("N dataset") is not None else None,
        "dataset_95_ci": row.get("Dataset 95% CI"),
        "market_brier_index": _float_or_none(row.get("Market")),
        "market_sample_size": int(row["N market"]) if row.get("N market") is not None else None,
        "market_95_ci": row.get("Market 95% CI"),
        "overall_95_ci": row.get("Overall 95% CI"),
        "supers_gt_forecaster": row.get("Supers > Forecaster?"),
        "supers_gt_forecaster_p_value": row.get("p-val Supers > Forecaster?"),
        "forecaster_gt_public": row.get("Forecaster > Public?"),
        "forecaster_gt_public_p_value": row.get("p-val Forecaster > Public?"),
        "leaderboard_kind": "baseline",
        "comparison_semantics": "official-difficulty-adjusted-public-reference",
        "identical_question_sets": False,
        "source_asset_url": FORECASTBENCH_BASELINE_JS_URL,
        "source_sha256": source_sha256,
    }


def _forecastbench_common_notes(*, model_name: str) -> list[str]:
    notes = [
        "Captured from the public ForecastBench baseline leaderboard.",
        "Primary score is ForecastBench Overall Brier Index (0-100, higher is better), not raw mean Brier loss.",
        "ForecastBench documents that leaderboard comparisons are difficulty-adjusted across non-identical question sets rather than locally rerun identical-question XRTM evaluations.",
    ]
    if _is_forecastbench_human_baseline(model_name):
        notes.append(
            "ForecastBench notes that human comparison groups were last surveyed in July 2024 and are compared using its published fixed-effects adjustment."
        )
    return notes


def _parse_forecastbench_interval(value: Any) -> ScoreInterval | None:
    if not isinstance(value, str):
        return None
    match = re.match(r"^\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]$", value.strip())
    if match is None:
        return None
    return ScoreInterval(low=float(match.group(1)), high=float(match.group(2)), level=0.95)


def _read_run_systems(runs_dir: Path, run_ids: list[str]) -> dict[str, Any]:
    durations: list[float] = []
    throughputs: list[float] = []
    token_totals: list[int] = []
    cache_hit_rates: list[float] = []
    provider_latencies: list[float] = []
    warning_count = 0
    error_count = 0
    for run_id in run_ids:
        run_dir = runs_dir / run_id
        run_summary_path = run_dir / "run_summary.json"
        provider_path = run_dir / "provider.json"
        if run_summary_path.exists():
            payload = json.loads(run_summary_path.read_text(encoding="utf-8"))
            if payload.get("duration_seconds") is not None:
                durations.append(float(payload["duration_seconds"]))
            forecast_count = payload.get("forecast_count")
            duration_seconds = payload.get("duration_seconds")
            if forecast_count and duration_seconds:
                throughputs.append(float(forecast_count) / float(duration_seconds))
            token_counts = payload.get("token_counts", {})
            total_tokens = token_counts.get("total_tokens")
            if total_tokens is not None:
                token_totals.append(int(total_tokens))
            latency_mean = payload.get("provider_latency_ms", {}).get("mean")
            if latency_mean is not None:
                provider_latencies.append(float(latency_mean))
            warning_count += int(payload.get("warning_count") or 0)
            error_count += int(payload.get("error_count") or 0)
        if provider_path.exists():
            provider_payload = json.loads(provider_path.read_text(encoding="utf-8"))
            cache_hit_rate = provider_payload.get("cache", {}).get("hit_rate")
            if cache_hit_rate is not None:
                cache_hit_rates.append(float(cache_hit_rate))
    return {
        "duration_seconds": statistics.fmean(durations) if durations else None,
        "forecasts_per_second": statistics.fmean(throughputs) if throughputs else None,
        "total_tokens": statistics.fmean(token_totals) if token_totals else None,
        "cache_hit_rate": statistics.fmean(cache_hit_rates) if cache_hit_rates else None,
        "provider_latency_mean_ms": statistics.fmean(provider_latencies) if provider_latencies else None,
        "warning_count": warning_count,
        "error_count": error_count,
    }


__all__ = [
    "VALIDATION_SCHEMA_VERSION",
    "BENCHMARK_COMPARE_SCHEMA_VERSION",
    "BenchmarkArmOptions",
    "BenchmarkCompareOptions",
    "BenchmarkStressOptions",
    "ValidationOptions",
    "ValidationTierError",
    "ValidationSafetyError",
    "run_validation",
    "run_benchmark_compare",
    "run_benchmark_stress_suite",
    "capture_forecastbench_baseline_reference",
    "list_validation_corpora",
    "prepare_validation_corpus",
]
