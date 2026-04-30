"""Run history helpers over canonical product artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from xrtm.product.artifacts import ArtifactStore
from xrtm.product.monitoring import load_monitor


def list_runs(
    runs_dir: Path,
    *,
    status: str | None = None,
    provider: str | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    """List canonical run artifacts, newest first, with optional filters."""

    if not runs_dir.exists():
        return []
    rows = []
    for run_dir in sorted((path for path in runs_dir.iterdir() if path.is_dir()), key=lambda path: path.name, reverse=True):
        try:
            run = ArtifactStore.read_run(run_dir)
        except FileNotFoundError:
            continue
        summary = _read_json(run_dir / "run_summary.json")
        run["summary"] = summary or run.get("summary", {})
        run["run_dir"] = str(run_dir)
        if status and run.get("status") != status:
            continue
        if provider and run.get("provider") != provider:
            continue
        if query and query.lower() not in _search_text(run).lower():
            continue
        rows.append(run)
    return rows


def resolve_run_dir(runs_dir: Path, run_ref: str) -> Path:
    """Resolve a run id under ``runs_dir``."""

    if "/" in run_ref or "\\" in run_ref or run_ref in {"", ".", ".."}:
        raise ValueError("invalid run reference")
    candidate = runs_dir / run_ref
    if not candidate.is_dir():
        raise FileNotFoundError(f"{candidate} does not exist")
    try:
        candidate.resolve().relative_to(runs_dir.resolve())
    except ValueError as exc:
        raise ValueError("run reference must be under runs directory") from exc
    return candidate


def run_detail(run_dir: Path) -> dict[str, Any]:
    """Return one export-ready run detail payload."""

    detail = {
        "run": ArtifactStore.read_run(run_dir),
        "summary": _read_json(run_dir / "run_summary.json"),
        "events": ArtifactStore.read_jsonl(run_dir / "events.jsonl"),
        "forecasts": ArtifactStore.read_jsonl(run_dir / "forecasts.jsonl"),
        "eval": _read_json(run_dir / "eval.json"),
        "train": _read_json(run_dir / "train.json"),
        "provider": _read_json(run_dir / "provider.json"),
    }
    if (run_dir / "monitor.json").exists():
        detail["monitor"] = load_monitor(run_dir)
    return detail


def compare_runs(left_dir: Path, right_dir: Path) -> list[dict[str, Any]]:
    """Compare high-value summary fields between two runs."""

    left = run_detail(left_dir)
    right = run_detail(right_dir)
    comparisons = []
    for label, path in {
        "status": ("run", "status"),
        "provider": ("run", "provider"),
        "forecast_count": ("summary", "forecast_count"),
        "duration_seconds": ("summary", "duration_seconds"),
        "total_tokens": ("summary", "token_counts", "total_tokens"),
        "eval_brier": ("summary", "eval", "brier_score"),
        "train_brier": ("summary", "train", "brier_score"),
        "warnings": ("summary", "warning_count"),
        "errors": ("summary", "error_count"),
    }.items():
        comparisons.append({"metric": label, "left": _nested_get(left, path), "right": _nested_get(right, path)})
    return comparisons


def export_run(run_dir: Path, output_path: Path) -> Path:
    """Write a single portable JSON export for one run."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(run_detail(run_dir), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _search_text(run: dict[str, Any]) -> str:
    values = [
        run.get("run_id"),
        run.get("status"),
        run.get("provider"),
        run.get("command"),
        run.get("run_dir"),
    ]
    return " ".join(str(value) for value in values if value is not None)


def _read_json(path: Path) -> Any:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _nested_get(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


__all__ = ["compare_runs", "export_run", "list_runs", "resolve_run_dir", "run_detail"]
