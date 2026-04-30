"""Artifact-backed monitoring UX for XRTM product runs."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from xrtm.data.corpora import load_real_binary_questions
from xrtm.forecast.e2e import run_real_question_e2e
from xrtm.product.artifacts import ArtifactStore, RunArtifact, utc_now
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
) -> RunArtifact:
    """Create a local-first monitor run with deterministic corpus watches."""

    if limit < 1:
        raise ValueError("limit must be at least 1")
    store = ArtifactStore(runs_dir)
    run = store.create_run(command="xrtm monitor start", provider=provider, package_versions=package_versions())
    questions = load_real_binary_questions(limit=limit)
    watches = [
        {
            "watch_id": uuid4().hex[:12],
            "question_id": question.id,
            "title": question.title,
            "status": "active",
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "trajectory": [],
            "errors": [],
        }
        for question in questions
    ]
    store.write_jsonl(run, "questions.jsonl", [question.model_dump(mode="json") for question in questions])
    store.write_json(
        run,
        "monitor.json",
        {
            "status": "running",
            "provider": provider,
            "base_url": base_url,
            "model": model,
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

    active_provider_name = provider or monitor.get("provider") or run_payload.get("provider") or "mock"
    active_base_url = base_url or monitor.get("base_url")
    active_model = model or monitor.get("model")
    active_provider = build_provider(
        active_provider_name,
        base_url=active_base_url,
        model=active_model,
        api_key=api_key,
    )
    run = _run_from_payload(run_dir, run_payload)
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
    output_by_id = {record.question_id: record.output for record in records}
    for watch in monitor.get("watches", []):
        output = output_by_id.get(watch["question_id"])
        if output is None:
            continue
        watch.setdefault("trajectory", []).append(
            {
                "timestamp": utc_now(),
                "probability": output.probability,
                "reasoning": output.reasoning,
            }
        )
        watch["updated_at"] = utc_now()
    monitor["provider"] = active_provider_name
    monitor["base_url"] = active_base_url
    monitor["model"] = active_model
    monitor["status"] = "running"
    monitor["updated_at"] = utc_now()
    store.write_json(run, "monitor.json", monitor)
    store.write_jsonl(run, "forecasts.jsonl", [record.model_dump(mode="json") for record in records])
    store.append_event(run, "monitor_cycle_completed", records=len(records))
    store.finish(run, status="monitoring")
    return monitor


def set_monitor_status(run_dir: Path, status: str) -> dict[str, Any]:
    """Set monitor status to running, paused, or halted."""

    if status not in {"running", "paused", "halted"}:
        raise ValueError(f"unsupported monitor status: {status}")
    store = ArtifactStore(run_dir.parent)
    run_payload = store.read_run(run_dir)
    run = _run_from_payload(run_dir, run_payload)
    monitor = _read_monitor(run_dir)
    monitor["status"] = status
    monitor["updated_at"] = utc_now()
    store.write_json(run, "monitor.json", monitor)
    store.append_event(run, f"monitor_{status}")
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
        warnings=list(payload.get("warnings", [])),
        errors=list(payload.get("errors", [])),
    )


__all__ = [
    "list_monitors",
    "load_monitor",
    "run_monitor_once",
    "set_monitor_status",
    "start_monitor",
]
