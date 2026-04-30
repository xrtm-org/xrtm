"""Deterministic performance harnesses for product workflows."""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from xrtm.product.pipeline import PipelineOptions, run_pipeline

PERFORMANCE_SCHEMA_VERSION = "xrtm.performance.v1"
MAX_ITERATIONS = 100
MAX_LIMIT = 1000


class PerformanceBudgetError(RuntimeError):
    """Raised when a performance report violates a fail-on-budget gate."""


@dataclass(frozen=True)
class PerformanceOptions:
    """Inputs for one bounded performance benchmark."""

    scenario: str = "provider-free-smoke"
    iterations: int = 3
    limit: int = 1
    runs_dir: Path = Path("runs-perf")
    output: Path = Path("performance.json")
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    max_tokens: int = 768
    max_mean_seconds: float | None = None
    max_p95_seconds: float | None = None
    fail_on_budget: bool = False


def run_performance_benchmark(options: PerformanceOptions) -> dict[str, Any]:
    """Run a deterministic product benchmark and write a structured report."""

    _validate_options(options)
    provider = _provider_for_scenario(options.scenario)
    samples = []
    for index in range(options.iterations):
        result = run_pipeline(
            PipelineOptions(
                provider=provider,
                limit=options.limit,
                runs_dir=options.runs_dir,
                base_url=options.base_url,
                model=options.model,
                api_key=options.api_key,
                max_tokens=options.max_tokens,
                write_report=False,
                command=f"xrtm perf run {options.scenario}",
            )
        )
        samples.append(
            {
                "iteration": index + 1,
                "run_id": result.run.run_id,
                "run_dir": str(result.run.run_dir),
                "duration_seconds": result.total_seconds,
                "forecast_records": result.forecast_records,
                "training_samples": result.training_samples,
                "eval_brier_score": result.eval_brier_score,
                "train_brier_score": result.train_brier_score,
            }
        )
    report = _build_report(options=options, provider=provider, samples=samples)
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if options.fail_on_budget and report["budget"]["status"] == "failed":
        raise PerformanceBudgetError("; ".join(report["budget"]["violations"]))
    return report


def _validate_options(options: PerformanceOptions) -> None:
    if options.scenario not in {"provider-free-smoke", "provider-free-scale", "local-llm-smoke"}:
        raise ValueError(f"unsupported performance scenario: {options.scenario}")
    if options.iterations < 1:
        raise ValueError("iterations must be at least 1")
    if options.iterations > MAX_ITERATIONS:
        raise ValueError(f"iterations must be at most {MAX_ITERATIONS}")
    if options.limit < 1:
        raise ValueError("limit must be at least 1")
    if options.limit > MAX_LIMIT:
        raise ValueError(f"limit must be at most {MAX_LIMIT}")
    if options.max_tokens < 1:
        raise ValueError("max_tokens must be at least 1")
    if options.max_mean_seconds is not None and options.max_mean_seconds <= 0:
        raise ValueError("max_mean_seconds must be positive")
    if options.max_p95_seconds is not None and options.max_p95_seconds <= 0:
        raise ValueError("max_p95_seconds must be positive")
    _validate_local_relative_path(options.runs_dir, field="runs_dir")
    _validate_local_relative_path(options.output, field="output")


def _validate_local_relative_path(path: Path, *, field: str) -> None:
    if path.is_absolute():
        raise ValueError(f"{field} must be a relative path")
    if any(part == ".." for part in path.parts):
        raise ValueError(f"{field} may not contain '..'")


def _provider_for_scenario(scenario: str) -> str:
    if scenario == "local-llm-smoke":
        return "local-llm"
    return "mock"


def _build_report(*, options: PerformanceOptions, provider: str, samples: list[dict[str, Any]]) -> dict[str, Any]:
    durations = [float(sample["duration_seconds"]) for sample in samples]
    forecast_count = sum(int(sample["forecast_records"]) for sample in samples)
    total_seconds = sum(durations)
    mean_seconds = statistics.fmean(durations)
    max_seconds = max(durations)
    p95_seconds = _percentile(durations, 0.95)
    violations = []
    if options.max_mean_seconds is not None and mean_seconds > options.max_mean_seconds:
        violations.append(f"mean_seconds {mean_seconds:.3f} exceeded budget {options.max_mean_seconds:.3f}")
    if options.max_p95_seconds is not None and p95_seconds > options.max_p95_seconds:
        violations.append(f"p95_seconds {p95_seconds:.3f} exceeded budget {options.max_p95_seconds:.3f}")
    return {
        "schema_version": PERFORMANCE_SCHEMA_VERSION,
        "scenario": options.scenario,
        "provider": provider,
        "iterations": options.iterations,
        "limit": options.limit,
        "runs_dir": str(options.runs_dir),
        "samples": samples,
        "summary": {
            "total_seconds": total_seconds,
            "mean_seconds": mean_seconds,
            "max_seconds": max_seconds,
            "p95_seconds": p95_seconds,
            "forecast_records": forecast_count,
            "forecasts_per_second": forecast_count / total_seconds if total_seconds else None,
        },
        "budget": {
            "status": "failed" if violations else "passed",
            "max_mean_seconds": options.max_mean_seconds,
            "max_p95_seconds": options.max_p95_seconds,
            "violations": violations,
        },
    }


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * percentile
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


__all__ = [
    "PERFORMANCE_SCHEMA_VERSION",
    "PerformanceBudgetError",
    "PerformanceOptions",
    "run_performance_benchmark",
]
