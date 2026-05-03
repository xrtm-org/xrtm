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
    questions: tuple[Any, ...] | None = None
    corpus_id: str = "xrtm-real-binary-v1"
    runs_dir: Path = Path("runs")
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    max_tokens: int = 768
    write_report: bool = True
    command: str = "xrtm run pipeline"
    user: str | None = None


@dataclass(frozen=True)
class PipelineResult:
    """Summary returned by product pipeline execution."""

    run: RunArtifact
    forecast_records: int
    eval_brier_score: float | None
    train_brier_score: float | None
    eval_summary: dict[str, Any]
    train_summary: dict[str, Any]
    training_samples: int
    total_seconds: float


@dataclass(frozen=True)
class _PipelineExecution:
    records: tuple[Any, ...]
    eval_payload: dict[str, Any]
    train_payload: dict[str, Any]
    training_samples: int


def run_pipeline(options: PipelineOptions) -> PipelineResult:
    """Run a bounded real-corpus forecast -> eval -> train/backtest product workflow."""

    if options.limit < 1:
        raise ValueError("limit must be at least 1")

    questions = _select_questions(options)
    store, run = _prepare_run(options, question_count=len(questions))
    start = time.perf_counter()
    try:
        execution = _execute_pipeline(options, store=store, run=run, questions=questions)
        total_seconds = time.perf_counter() - start
        _finalize_success(
            options,
            store=store,
            run=run,
            execution=execution,
            total_seconds=total_seconds,
        )
        return PipelineResult(
            run=run,
            forecast_records=len(execution.records),
            eval_brier_score=execution.eval_payload["summary_statistics"].get("brier_score"),
            train_brier_score=execution.train_payload["summary_statistics"].get("brier_score"),
            eval_summary=execution.eval_payload["summary_statistics"],
            train_summary=execution.train_payload["summary_statistics"],
            training_samples=execution.training_samples,
            total_seconds=total_seconds,
        )
    except Exception as exc:
        _finalize_failure(store=store, run=run, provider=options.provider, started_at=start, error=exc)
        raise


def _select_questions(options: PipelineOptions) -> list[Any]:
    questions = (
        list(options.questions)[: options.limit]
        if options.questions is not None
        else load_real_binary_questions(limit=options.limit)
    )
    if not questions:
        raise ValueError("selected corpus did not yield any questions")
    return questions


def _prepare_run(options: PipelineOptions, *, question_count: int) -> tuple[ArtifactStore, RunArtifact]:
    store = ArtifactStore(options.runs_dir)
    run = store.create_run(
        command=options.command,
        provider=options.provider,
        package_versions=package_versions(),
        user=options.user,
    )
    store.append_event(
        run,
        "run_started",
        provider=options.provider,
        limit=question_count,
        requested_limit=options.limit,
        corpus_id=options.corpus_id,
    )
    return store, run


def _execute_pipeline(
    options: PipelineOptions,
    *,
    store: ArtifactStore,
    run: RunArtifact,
    questions: list[Any],
) -> _PipelineExecution:
    provider = build_provider(
        options.provider,
        base_url=options.base_url,
        model=options.model,
        api_key=options.api_key,
    )
    store.write_json(run, "provider.json", provider_snapshot(provider, options.provider, base_url=options.base_url))
    store.write_jsonl(run, "questions.jsonl", [question.model_dump(mode="json") for question in questions])
    records = tuple(_run_forecast_stage(options, store=store, run=run, questions=questions, provider=provider))
    eval_payload = _write_eval_payload(store, run=run, records=records)
    train_payload, training_samples = _write_train_payload(store, run=run, records=records)
    return _PipelineExecution(
        records=records,
        eval_payload=eval_payload,
        train_payload=train_payload,
        training_samples=training_samples,
    )


def _run_forecast_stage(
    options: PipelineOptions,
    *,
    store: ArtifactStore,
    run: RunArtifact,
    questions: list[Any],
    provider: Any,
) -> list[Any]:
    store.append_event(
        run,
        "provider_request_started",
        questions=len(questions),
        provider=options.provider,
        corpus_id=options.corpus_id,
    )
    records = run_real_question_e2e(
        limit=len(questions),
        questions=questions,
        corpus_id=options.corpus_id,
        provider=provider,
        base_url=options.base_url,
        model=options.model,
        api_key=options.api_key,
        max_tokens=options.max_tokens,
        artifact_dir=run.run_dir / "logs",
        write_artifacts=False,
    )
    store.write_jsonl(run, "forecasts.jsonl", [record.model_dump(mode="json") for record in records])
    store.append_event(
        run,
        "provider_request_completed",
        records=len(records),
        provider=options.provider,
        corpus_id=options.corpus_id,
    )
    store.append_event(
        run,
        "forecast_written",
        records=len(records),
        artifact="forecasts.jsonl",
        corpus_id=options.corpus_id,
    )
    return records


def _write_eval_payload(store: ArtifactStore, *, run: RunArtifact, records: tuple[Any, ...]) -> dict[str, Any]:
    eval_report = evaluate_resolved_forecasts(records)
    eval_payload = _eval_payload(eval_report)
    store.write_json(run, "eval.json", eval_payload)
    store.append_event(run, "eval_completed", total_evaluations=eval_payload["total_evaluations"])
    return eval_payload


def _write_train_payload(
    store: ArtifactStore,
    *,
    run: RunArtifact,
    records: tuple[Any, ...],
) -> tuple[dict[str, Any], int]:
    train_report = evaluate_forecast_records_with_backtest_runner(records)
    training_samples = build_training_samples_from_resolved_forecasts(records)
    train_payload = _train_payload(train_report, training_samples=len(training_samples))
    store.write_json(run, "train.json", train_payload)
    store.append_event(run, "train_completed", total_evaluations=train_payload["total_evaluations"])
    return train_payload, len(training_samples)


def _finalize_success(
    options: PipelineOptions,
    *,
    store: ArtifactStore,
    run: RunArtifact,
    execution: _PipelineExecution,
    total_seconds: float,
) -> None:
    if options.write_report:
        report_path = render_html_report(run.run_dir)
        run.artifacts["report.html"] = str(report_path)

    summary = build_run_summary(
        status="completed",
        provider=options.provider,
        total_seconds=total_seconds,
        forecast_records=list(execution.records),
        eval_payload=execution.eval_payload,
        train_payload=execution.train_payload,
        warnings=run.warnings,
        errors=run.errors,
    )
    store.write_summary(run, summary)
    store.append_event(run, "run_completed", total_seconds=total_seconds)
    store.finish(run, status="completed")


def _finalize_failure(
    *,
    store: ArtifactStore,
    run: RunArtifact,
    provider: str,
    started_at: float,
    error: Exception,
) -> None:
    total_seconds = time.perf_counter() - started_at
    message = str(error)
    store.write_summary(
        run,
        build_run_summary(
            status="failed",
            provider=provider,
            total_seconds=total_seconds,
            forecast_records=[],
            errors=[message],
        ),
    )
    store.append_event(run, "error", message=message)
    store.append_event(run, "run_failed", error=message, total_seconds=total_seconds)
    store.finish(run, status="failed", errors=[message])


_PACKAGE_VERSION_CACHE: dict[str, str] | None = None


def package_versions() -> dict[str, str]:
    """Get package versions with caching for performance."""
    global _PACKAGE_VERSION_CACHE
    if _PACKAGE_VERSION_CACHE is not None:
        return _PACKAGE_VERSION_CACHE

    packages = ["xrtm", "xrtm-data", "xrtm-eval", "xrtm-forecast", "xrtm-train"]
    versions = {}
    for package in packages:
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = "unknown"

    _PACKAGE_VERSION_CACHE = versions
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
