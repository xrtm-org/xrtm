"""Cross-stack product pipeline for forecast, eval, train/backtest, and reports."""

from __future__ import annotations

import time
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from xrtm.data.corpora import load_real_binary_questions
from xrtm.eval.real_e2e import evaluate_resolved_forecasts
from xrtm.forecast.e2e import run_real_question_e2e
from xrtm.product.artifacts import ArtifactStore, RunArtifact, to_json_safe
from xrtm.product.observability import build_run_summary
from xrtm.product.providers import build_provider, provider_snapshot
from xrtm.product.reports import render_html_report
from xrtm.train.real_e2e import (
    build_training_samples_from_resolved_forecasts,
    evaluate_forecast_records_with_backtest_runner,
)


@dataclass(frozen=True)
class PipelineOptions:
    """Inputs for a product pipeline run."""

    provider: str = "mock"
    limit: int = 2
    runs_dir: Path = Path("runs")
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    max_tokens: int = 768
    write_report: bool = True
    command: str = "xrtm run pipeline"


@dataclass(frozen=True)
class PipelineResult:
    """Summary returned by product pipeline execution."""

    run: RunArtifact
    forecast_records: int
    eval_brier_score: float | None
    train_brier_score: float | None
    training_samples: int
    total_seconds: float


def run_pipeline(options: PipelineOptions) -> PipelineResult:
    """Run a bounded real-corpus forecast -> eval -> train/backtest product workflow."""

    if options.limit < 1:
        raise ValueError("limit must be at least 1")
    store = ArtifactStore(options.runs_dir)
    run = store.create_run(command=options.command, provider=options.provider, package_versions=package_versions())
    start = time.perf_counter()
    try:
        store.append_event(run, "run_started", provider=options.provider, limit=options.limit)
        provider = build_provider(
            options.provider,
            base_url=options.base_url,
            model=options.model,
            api_key=options.api_key,
        )
        provider_info = provider_snapshot(provider, options.provider, base_url=options.base_url)
        store.write_json(run, "provider.json", provider_info)

        questions = load_real_binary_questions(limit=options.limit)
        store.write_jsonl(run, "questions.jsonl", [question.model_dump(mode="json") for question in questions])
        store.append_event(run, "provider_request_started", questions=len(questions), provider=options.provider)
        records = run_real_question_e2e(
            limit=options.limit,
            provider=provider,
            base_url=options.base_url,
            model=options.model,
            api_key=options.api_key,
            max_tokens=options.max_tokens,
            artifact_dir=run.run_dir / "logs",
            write_artifacts=False,
        )
        store.write_jsonl(run, "forecasts.jsonl", [record.model_dump(mode="json") for record in records])
        store.append_event(run, "provider_request_completed", records=len(records), provider=options.provider)
        store.append_event(run, "forecast_written", records=len(records), artifact="forecasts.jsonl")

        eval_report = evaluate_resolved_forecasts(records)
        eval_payload = _eval_payload(eval_report)
        store.write_json(run, "eval.json", eval_payload)
        store.append_event(run, "eval_completed", total_evaluations=eval_payload["total_evaluations"])

        train_report = evaluate_forecast_records_with_backtest_runner(records)
        training_samples = build_training_samples_from_resolved_forecasts(records)
        train_payload = _train_payload(train_report, training_samples=len(training_samples))
        store.write_json(run, "train.json", train_payload)
        store.append_event(run, "train_completed", total_evaluations=train_payload["total_evaluations"])

        if options.write_report:
            report_path = render_html_report(run.run_dir)
            run.artifacts["report.html"] = str(report_path)

        total_seconds = time.perf_counter() - start
        summary = build_run_summary(
            status="completed",
            provider=options.provider,
            total_seconds=total_seconds,
            forecast_records=list(records),
            eval_payload=eval_payload,
            train_payload=train_payload,
            warnings=run.warnings,
            errors=run.errors,
        )
        store.write_summary(run, summary)
        store.append_event(run, "run_completed", total_seconds=total_seconds)
        store.finish(run, status="completed")
        return PipelineResult(
            run=run,
            forecast_records=len(records),
            eval_brier_score=eval_payload["summary_statistics"].get("brier_score"),
            train_brier_score=train_payload["summary_statistics"].get("brier_score"),
            training_samples=len(training_samples),
            total_seconds=total_seconds,
        )
    except Exception as exc:
        total_seconds = time.perf_counter() - start
        store.write_summary(
            run,
            build_run_summary(
                status="failed",
                provider=options.provider,
                total_seconds=total_seconds,
                forecast_records=[],
                errors=[str(exc)],
            ),
        )
        store.append_event(run, "error", message=str(exc))
        store.append_event(run, "run_failed", error=str(exc), total_seconds=total_seconds)
        store.finish(run, status="failed", errors=[str(exc)])
        raise


def package_versions() -> dict[str, str]:
    packages = ["xrtm", "xrtm-data", "xrtm-eval", "xrtm-forecast", "xrtm-train"]
    versions = {}
    for package in packages:
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = "unknown"
    return versions


def _eval_payload(report: Any) -> dict[str, Any]:
    return {
        "metric_name": report.metric_name,
        "mean_score": report.mean_score,
        "total_evaluations": report.total_evaluations,
        "summary_statistics": to_json_safe(report.summary_statistics),
        "reliability_bins": to_json_safe(report.reliability_bins),
    }


def _train_payload(report: Any, *, training_samples: int) -> dict[str, Any]:
    return {
        "metric_name": report.metric_name,
        "mean_score": report.mean_score,
        "total_evaluations": report.total_evaluations,
        "summary_statistics": to_json_safe(report.summary_statistics),
        "slices": to_json_safe(report.slices),
        "training_samples": training_samples,
    }


__all__ = ["PipelineOptions", "PipelineResult", "package_versions", "run_pipeline"]
