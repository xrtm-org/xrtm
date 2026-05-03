"""Shared read-model helpers over canonical XRTM product artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from xrtm.product.artifacts import ArtifactStore
from xrtm.product.observability import MONITOR_SCHEMA_VERSION


def list_run_records(
    runs_dir: Path,
    *,
    status: str | None = None,
    provider: str | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    """List canonical runs, newest first, with optional filters."""

    if not runs_dir.exists():
        return []

    runs: list[dict[str, Any]] = []
    for run_dir in _iter_run_dirs(runs_dir, reverse=True):
        run = _read_run_record(run_dir)
        if run is None:
            continue
        if status and run.get("status") != status:
            continue
        if provider and run.get("provider") != provider:
            continue
        if query and query.lower() not in _search_text(run).lower():
            continue
        runs.append(run)
    return runs


def list_monitor_records(runs_dir: Path) -> list[dict[str, Any]]:
    """List real monitor runs with lightweight monitor state, newest first."""

    if not runs_dir.exists():
        return []

    monitors: list[dict[str, Any]] = []
    for run_dir in _iter_run_dirs(runs_dir, reverse=True):
        monitor_path = run_dir / "monitor.json"
        if not monitor_path.exists():
            continue
        run = _read_run_record(run_dir)
        if run is None:
            continue
        monitor = _read_optional_json(monitor_path)
        if not is_monitor_record(run, monitor):
            continue
        summary = _read_optional_json(run_dir / "run_summary.json")
        monitors.append(
            {
                "run_id": run.get("run_id", run_dir.name),
                "run_dir": str(run_dir),
                "provider": run.get("provider"),
                "command": run.get("command"),
                "status": monitor.get("status", run.get("status")),
                "watches": len(monitor.get("watches", [])),
                "updates": summary.get("updates"),
                "warning_count": summary.get("warning_count"),
                "updated_at": monitor.get("updated_at") or run.get("updated_at"),
            }
        )
    return monitors


def read_run_detail(run_dir: Path) -> dict[str, Any]:
    """Read the shared run-detail payload used across product surfaces."""

    detail: dict[str, Any] = {
        "run": ArtifactStore.read_run(run_dir),
        "summary": _read_optional_json(run_dir / "run_summary.json"),
        "questions": _read_optional_jsonl(run_dir / "questions.jsonl"),
        "events": _read_optional_jsonl(run_dir / "events.jsonl"),
        "forecasts": _read_optional_jsonl(run_dir / "forecasts.jsonl"),
        "eval": _read_optional_json(run_dir / "eval.json"),
        "train": _read_optional_json(run_dir / "train.json"),
        "provider": _read_optional_json(run_dir / "provider.json"),
    }
    monitor_path = run_dir / "monitor.json"
    if monitor_path.exists():
        monitor = _read_optional_json(monitor_path)
        if is_monitor_record(detail["run"], monitor):
            detail["monitor"] = monitor
    return detail


def _iter_run_dirs(runs_dir: Path, *, reverse: bool) -> list[Path]:
    return sorted((path for path in runs_dir.iterdir() if path.is_dir()), key=lambda path: path.name, reverse=reverse)


def _read_run_record(run_dir: Path) -> dict[str, Any] | None:
    try:
        run = ArtifactStore.read_run(run_dir)
    except FileNotFoundError:
        return None
    summary = _read_optional_json(run_dir / "run_summary.json")
    run["summary"] = summary or run.get("summary", {})
    run["run_dir"] = str(run_dir)
    return run


def _read_optional_json(path: Path) -> Any:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_optional_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _search_text(run: dict[str, Any]) -> str:
    values = [
        run.get("run_id"),
        run.get("status"),
        run.get("provider"),
        run.get("command"),
        run.get("run_dir"),
        run.get("user"),
    ]
    return " ".join(str(value) for value in values if value is not None)


def is_monitor_record(run: dict[str, Any], monitor: dict[str, Any]) -> bool:
    if monitor.get("schema_version") == MONITOR_SCHEMA_VERSION:
        return True
    return run.get("command") == "xrtm monitor start"

__all__ = ["is_monitor_record", "list_monitor_records", "list_run_records", "read_run_detail"]
