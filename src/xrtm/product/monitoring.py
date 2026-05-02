"""Artifact-backed monitoring UX for XRTM product runs."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from xrtm.data.corpora import load_real_binary_questions
from xrtm.forecast.e2e import run_real_question_e2e
from xrtm.product.artifacts import ArtifactStore, RunArtifact, utc_now
from xrtm.product.observability import (
    MONITOR_SCHEMA_VERSION,
    MonitorThresholds,
    evaluate_probability_threshold,
    monitor_summary,
    validate_monitor_state,
)
from xrtm.product.pipeline import package_versions
from xrtm.product.providers import build_provider, provider_snapshot
from xrtm.product.read_models import list_monitor_records


@dataclass(frozen=True)
class _MonitorRuntime:
    store: ArtifactStore
    run: RunArtifact
    monitor: dict[str, Any]
    provider_name: str
    base_url: str | None
    model: str | None
    thresholds: MonitorThresholds


def start_monitor(
    *,
    runs_dir: Path,
    limit: int,
    provider: str,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    thresholds: MonitorThresholds | None = None,
) -> RunArtifact:
    """Create a local-first monitor run with deterministic corpus watches."""

    if limit < 1:
        raise ValueError("limit must be at least 1")
    store = ArtifactStore(runs_dir)
    run = store.create_run(command="xrtm monitor start", provider=provider, package_versions=package_versions())
    monitor_thresholds = thresholds or MonitorThresholds()
    questions = load_real_binary_questions(limit=limit)
    watches = [
        {
            "watch_id": uuid4().hex[:12],
            "question_id": question.id,
            "title": question.title,
            "status": "created",
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "trajectory": [],
            "warnings": [],
            "errors": [],
        }
        for question in questions
    ]
    store.write_jsonl(run, "questions.jsonl", [question.model_dump(mode="json") for question in questions])
    store.write_json(
        run,
        "monitor.json",
        {
            "schema_version": MONITOR_SCHEMA_VERSION,
            "status": "created",
            "provider": provider,
            "base_url": base_url,
            "model": model,
            "thresholds": monitor_thresholds.to_json_dict(),
            "cycles": 0,
            "watches": watches,
            "updated_at": utc_now(),
        },
    )
    store.append_event(run, "monitor_started", watches=len(watches), provider=provider)
    store.finish(run, status="monitoring")
    return run


def run_monitor_once(
    *,
    run_dir: Path,
    provider: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    max_tokens: int = 768,
) -> dict[str, Any]:
    """Execute one monitor update cycle and persist updated trajectories."""

    runtime = _load_monitor_runtime(
        run_dir,
        provider=provider,
        base_url=base_url,
        model=model,
    )
    runtime.store.append_event(
        runtime.run,
        "monitor_cycle_started",
        provider=runtime.provider_name,
        watches=len(runtime.monitor.get("watches", [])),
    )
    try:
        records = _forecast_monitor_records(runtime, api_key=api_key, max_tokens=max_tokens)
    except Exception as exc:
        _persist_failed_monitor_cycle(runtime, exc)
        raise

    warnings = _apply_watch_outputs(runtime.monitor, records=records, thresholds=runtime.thresholds)
    _persist_monitor_cycle(runtime, records=records, warnings=warnings)
    return runtime.monitor


def run_monitor_daemon(
    *,
    run_dir: Path,
    interval_seconds: float,
    cycles: int,
    provider: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    max_tokens: int = 768,
) -> dict[str, Any]:
    """Run a bounded local monitor loop with deterministic cycle count."""

    if interval_seconds < 0:
        raise ValueError("interval_seconds must be non-negative")
    if cycles < 1:
        raise ValueError("cycles must be at least 1")
    monitor: dict[str, Any] = {}
    for cycle in range(cycles):
        monitor = run_monitor_once(
            run_dir=run_dir,
            provider=provider,
            base_url=base_url,
            model=model,
            api_key=api_key,
            max_tokens=max_tokens,
        )
        if monitor.get("status") in {"halted", "failed"}:
            break
        if cycle < cycles - 1 and interval_seconds:
            time.sleep(interval_seconds)
    return monitor


def set_monitor_status(run_dir: Path, status: str) -> dict[str, Any]:
    """Set monitor status to a supported lifecycle state."""

    validate_monitor_state(status)
    store = ArtifactStore(run_dir.parent)
    run_payload = store.read_run(run_dir)
    run = _run_from_payload(run_dir, run_payload)
    monitor = _read_monitor(run_dir)
    monitor["status"] = status
    monitor["updated_at"] = utc_now()
    store.write_json(run, "monitor.json", monitor)
    store.write_summary(run, monitor_summary(monitor))
    store.append_event(run, "monitor_status_changed", status=status)
    store.finish(run, status="monitoring" if status != "halted" else "halted")
    return monitor


def load_monitor(run_dir: Path) -> dict[str, Any]:
    return _read_monitor(run_dir)


def list_monitors(runs_dir: Path) -> list[dict[str, Any]]:
    return list_monitor_records(runs_dir)


def _load_monitor_runtime(
    run_dir: Path,
    *,
    provider: str | None,
    base_url: str | None,
    model: str | None,
) -> _MonitorRuntime:
    store = ArtifactStore(run_dir.parent)
    run_payload = store.read_run(run_dir)
    monitor = _read_monitor(run_dir)
    _ensure_monitor_can_run(monitor)
    provider_name = provider or monitor.get("provider") or run_payload.get("provider") or "mock"
    return _MonitorRuntime(
        store=store,
        run=_run_from_payload(run_dir, run_payload),
        monitor=monitor,
        provider_name=provider_name,
        base_url=base_url or monitor.get("base_url"),
        model=model or monitor.get("model"),
        thresholds=MonitorThresholds.from_payload(monitor.get("thresholds")),
    )


def _ensure_monitor_can_run(monitor: dict[str, Any]) -> None:
    if monitor.get("status") == "halted":
        raise ValueError("monitor is halted")
    if monitor.get("status") == "paused":
        raise ValueError("monitor is paused")
    if monitor.get("status") == "failed":
        raise ValueError("monitor is failed")


def _forecast_monitor_records(
    runtime: _MonitorRuntime,
    *,
    api_key: str | None,
    max_tokens: int,
) -> list[Any]:
    active_provider = build_provider(
        runtime.provider_name,
        base_url=runtime.base_url,
        model=runtime.model,
        api_key=api_key,
    )
    runtime.store.write_json(
        runtime.run,
        "provider.json",
        provider_snapshot(active_provider, runtime.provider_name, base_url=runtime.base_url),
    )
    return run_real_question_e2e(
        limit=len(runtime.monitor.get("watches", [])),
        provider=active_provider,
        base_url=runtime.base_url,
        model=runtime.model,
        api_key=api_key,
        max_tokens=max_tokens,
        artifact_dir=runtime.run.run_dir / "logs",
        write_artifacts=False,
    )


def _apply_watch_outputs(
    monitor: dict[str, Any],
    *,
    records: list[Any],
    thresholds: MonitorThresholds,
) -> list[str]:
    output_by_id = {record.question_id: record.output for record in records}
    warnings: list[str] = []
    for watch in monitor.get("watches", []):
        output = output_by_id.get(watch["question_id"])
        if output is None:
            message = f"no forecast output returned for watch {watch['question_id']}"
            watch.setdefault("warnings", []).append(message)
            warnings.append(f"{watch['question_id']}: {message}")
            watch["status"] = "degraded"
            watch["updated_at"] = utc_now()
            continue
        watch_warnings = evaluate_probability_threshold(watch=watch, probability=output.probability, thresholds=thresholds)
        watch.setdefault("trajectory", []).append(
            {
                "timestamp": utc_now(),
                "probability": output.probability,
                "reasoning": output.reasoning,
            }
        )
        if watch_warnings:
            watch.setdefault("warnings", []).extend(watch_warnings)
            warnings.extend(f"{watch['question_id']}: {message}" for message in watch_warnings)
            watch["status"] = "degraded"
        else:
            watch["status"] = "running"
        watch["updated_at"] = utc_now()
    return warnings


def _persist_monitor_cycle(runtime: _MonitorRuntime, *, records: list[Any], warnings: list[str]) -> None:
    runtime.monitor["provider"] = runtime.provider_name
    runtime.monitor["base_url"] = runtime.base_url
    runtime.monitor["model"] = runtime.model
    runtime.monitor["status"] = "degraded" if warnings else "running"
    runtime.monitor["cycles"] = int(runtime.monitor.get("cycles", 0) or 0) + 1
    runtime.monitor["updated_at"] = utc_now()
    runtime.store.write_json(runtime.run, "monitor.json", runtime.monitor)
    runtime.store.write_jsonl(runtime.run, "forecasts.jsonl", [record.model_dump(mode="json") for record in records])
    runtime.store.write_summary(runtime.run, monitor_summary(runtime.monitor))
    for message in warnings:
        runtime.store.append_event(runtime.run, "warning", message=message)
    runtime.store.append_event(runtime.run, "monitor_cycle_completed", records=len(records))
    runtime.store.finish(runtime.run, status="monitoring")


def _persist_failed_monitor_cycle(runtime: _MonitorRuntime, error: Exception) -> None:
    message = str(error)
    runtime.monitor["status"] = "failed"
    runtime.monitor["updated_at"] = utc_now()
    runtime.monitor.setdefault("errors", []).append(message)
    runtime.store.write_json(runtime.run, "monitor.json", runtime.monitor)
    runtime.store.write_summary(runtime.run, monitor_summary(runtime.monitor))
    runtime.store.append_event(runtime.run, "error", message=message)
    runtime.store.finish(runtime.run, status="failed", errors=[message])


def _read_monitor(run_dir: Path) -> dict[str, Any]:
    monitor_path = run_dir / "monitor.json"
    if not monitor_path.exists():
        raise FileNotFoundError(f"{monitor_path} does not exist")
    import json

    return json.loads(monitor_path.read_text(encoding="utf-8"))


def _run_from_payload(run_dir: Path, payload: dict[str, Any]) -> RunArtifact:
    return RunArtifact(
        run_id=str(payload.get("run_id", run_dir.name)),
        run_dir=run_dir,
        status=str(payload.get("status", "monitoring")),
        command=str(payload.get("command", "xrtm monitor")),
        provider=str(payload.get("provider", "mock")),
        created_at=str(payload.get("created_at", utc_now())),
        updated_at=str(payload.get("updated_at", utc_now())),
        package_versions=dict(payload.get("package_versions", {})),
        artifacts=dict(payload.get("artifacts", {})),
        summary=dict(payload.get("summary", {})),
        warnings=list(payload.get("warnings", [])),
        errors=list(payload.get("errors", [])),
    )


__all__ = [
    "list_monitors",
    "load_monitor",
    "run_monitor_daemon",
    "run_monitor_once",
    "set_monitor_status",
    "start_monitor",
]
