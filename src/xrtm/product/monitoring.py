"""Artifact-backed monitoring UX for XRTM product runs."""

from __future__ import annotations

import time
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

    store = ArtifactStore(run_dir.parent)
    run_payload = store.read_run(run_dir)
    monitor = _read_monitor(run_dir)
    if monitor.get("status") == "halted":
        raise ValueError("monitor is halted")
    if monitor.get("status") == "paused":
        raise ValueError("monitor is paused")
    if monitor.get("status") == "failed":
        raise ValueError("monitor is failed")

    active_provider_name = provider or monitor.get("provider") or run_payload.get("provider") or "mock"
    active_base_url = base_url or monitor.get("base_url")
    active_model = model or monitor.get("model")
    run = _run_from_payload(run_dir, run_payload)
    thresholds = MonitorThresholds.from_payload(monitor.get("thresholds"))
    store.append_event(run, "monitor_cycle_started", provider=active_provider_name, watches=len(monitor.get("watches", [])))
    try:
        active_provider = build_provider(
            active_provider_name,
            base_url=active_base_url,
            model=active_model,
            api_key=api_key,
        )
        store.write_json(run, "provider.json", provider_snapshot(active_provider, active_provider_name, base_url=active_base_url))
        records = run_real_question_e2e(
            limit=len(monitor.get("watches", [])),
            provider=active_provider,
            base_url=active_base_url,
            model=active_model,
            api_key=api_key,
            max_tokens=max_tokens,
            artifact_dir=run_dir / "logs",
            write_artifacts=False,
        )
    except Exception as exc:
        monitor["status"] = "failed"
        monitor["updated_at"] = utc_now()
        monitor.setdefault("errors", []).append(str(exc))
        store.write_json(run, "monitor.json", monitor)
        store.write_summary(run, monitor_summary(monitor))
        store.append_event(run, "error", message=str(exc))
        store.finish(run, status="failed", errors=[str(exc)])
        raise
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
    monitor["provider"] = active_provider_name
    monitor["base_url"] = active_base_url
    monitor["model"] = active_model
    monitor["status"] = "degraded" if warnings else "running"
    monitor["cycles"] = int(monitor.get("cycles", 0) or 0) + 1
    monitor["updated_at"] = utc_now()
    store.write_json(run, "monitor.json", monitor)
    store.write_jsonl(run, "forecasts.jsonl", [record.model_dump(mode="json") for record in records])
    store.write_summary(run, monitor_summary(monitor))
    for message in warnings:
        store.append_event(run, "warning", message=message)
    store.append_event(run, "monitor_cycle_completed", records=len(records))
    store.finish(run, status="monitoring")
    return monitor


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
    monitors: list[dict[str, Any]] = []
    if not runs_dir.exists():
        return monitors
    for run_dir in sorted(path for path in runs_dir.iterdir() if path.is_dir()):
        monitor_path = run_dir / "monitor.json"
        run_path = run_dir / "run.json"
        if monitor_path.exists() and run_path.exists():
            monitor = _read_monitor(run_dir)
            run = ArtifactStore.read_run(run_dir)
            monitors.append(
                {
                    "run_id": run.get("run_id", run_dir.name),
                    "run_dir": str(run_dir),
                    "status": monitor.get("status", run.get("status")),
                    "watches": len(monitor.get("watches", [])),
                    "updated_at": monitor.get("updated_at"),
                }
            )
    return monitors


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
