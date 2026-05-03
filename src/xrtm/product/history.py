"""Run history helpers over canonical product artifacts."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from xrtm.product.artifacts import ArtifactStore
from xrtm.product.read_models import list_run_records, read_run_detail


def list_runs(
    runs_dir: Path,
    *,
    status: str | None = None,
    provider: str | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    """List canonical run artifacts, newest first, with optional filters."""

    return list_run_records(runs_dir, status=status, provider=provider, query=query)


def latest_run_dir(runs_dir: Path) -> Path:
    """Return the newest canonical run directory under ``runs_dir``."""

    if not runs_dir.exists():
        raise FileNotFoundError(f"no canonical runs found under {runs_dir}")
    for candidate in sorted((path for path in runs_dir.iterdir() if path.is_dir()), key=lambda path: path.name, reverse=True):
        try:
            ArtifactStore.read_run(candidate)
        except FileNotFoundError:
            continue
        return candidate
    raise FileNotFoundError(f"no canonical runs found under {runs_dir}")


def resolve_run_dir(runs_dir: Path, run_ref: str) -> Path:
    """Resolve a run id under ``runs_dir``."""

    if run_ref == "latest":
        return latest_run_dir(runs_dir)

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

    return read_run_detail(run_dir)


def compare_runs(left_dir: Path, right_dir: Path) -> list[dict[str, Any]]:
    """Compare high-value summary fields between two runs."""

    left = run_detail(left_dir)
    right = run_detail(right_dir)
    comparisons = []
    for label, path, preference in [
        ("status", ("run", "status"), None),
        ("provider", ("run", "provider"), None),
        ("user", ("run", "user"), None),
        ("forecast_count", ("summary", "forecast_count"), "higher"),
        ("duration_seconds", ("summary", "duration_seconds"), "lower"),
        ("total_tokens", ("summary", "token_counts", "total_tokens"), "lower"),
        ("eval_brier", ("summary", "eval", "brier_score"), "lower"),
        ("eval_ece", ("summary", "eval", "ece"), "lower"),
        ("train_brier", ("summary", "train", "brier_score"), "lower"),
        ("training_samples", ("summary", "train", "training_samples"), "higher"),
        ("warnings", ("summary", "warning_count"), "lower"),
        ("errors", ("summary", "error_count"), "lower"),
    ]:
        comparisons.append(
            _comparison_row(
                label,
                _nested_get(left, path),
                _nested_get(right, path),
                preference=preference,
            )
        )
    comparisons.extend(_question_level_comparisons(left, right))
    return comparisons


def export_run(run_dir: Path, output_path: Path, *, format: str = "json") -> Path:
    """Write a single portable export for one run.

    Args:
        run_dir: Directory containing the run artifacts
        output_path: Destination file path
        format: Export format, either "json" or "csv"

    Returns:
        Path to the written export file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if format == "csv":
        _export_run_csv(run_dir, output_path)
    elif format == "json":
        output_path.write_text(json.dumps(run_detail(run_dir), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        raise ValueError(f"Unsupported export format: {format}")

    return output_path


def _export_run_csv(run_dir: Path, output_path: Path) -> None:
    """Write forecasts as flattened CSV rows for spreadsheet/dataframe workflows."""

    detail = run_detail(run_dir)
    run_metadata = detail["run"]
    summary = detail.get("summary", {})
    forecasts = detail.get("forecasts", [])
    questions = {
        str(question.get("id")): question for question in detail.get("questions", []) if question.get("id") is not None
    }
    started_at = run_metadata.get("started_at") or run_metadata.get("created_at")
    completed_at = run_metadata.get("completed_at") or run_metadata.get("updated_at")

    rows = []
    for forecast in forecasts:
        output = forecast.get("output", {}) if isinstance(forecast.get("output"), dict) else {}
        question_id = str(forecast.get("question_id") or output.get("question_id") or "")
        question = _merge_question_payloads(
            questions.get(question_id, {}),
            forecast.get("question", {}) if isinstance(forecast.get("question"), dict) else {},
            output.get("question", {}) if isinstance(output.get("question"), dict) else {},
        )
        usage = (
            forecast.get("provider_metadata", {}).get("usage")
            or output.get("metadata", {}).get("raw_data", {}).get("usage")
            or {}
        )
        probability = forecast.get("probability", output.get("probability"))
        outcome = _question_outcome(question, fallback=forecast.get("outcome", output.get("outcome")))
        row = {
            "run_id": run_metadata.get("run_id"),
            "status": run_metadata.get("status"),
            "provider": run_metadata.get("provider"),
            "user": run_metadata.get("user"),
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_seconds": summary.get("duration_seconds"),
            "total_tokens": summary.get("token_counts", {}).get("total_tokens"),
            "eval_brier_score": summary.get("eval", {}).get("brier_score"),
            "eval_ece": summary.get("eval", {}).get("ece"),
            "train_brier_score": summary.get("train", {}).get("brier_score"),
            "question_id": question_id,
            "question_title": _first_non_empty(
                question.get("title"),
                question.get("question_text"),
                question.get("metadata", {}).get("raw_data", {}).get("title"),
            ),
            "question_text": _first_non_empty(
                question.get("question_text"),
                question.get("title"),
                question.get("description"),
                question.get("metadata", {}).get("raw_data", {}).get("content"),
            ),
            "question_description": _first_non_empty(
                question.get("description"),
                question.get("metadata", {}).get("raw_data", {}).get("content"),
            ),
            "resolution_date": _first_non_empty(
                question.get("resolution_date"),
                question.get("resolution_time"),
                question.get("metadata", {}).get("raw_data", {}).get("resolution_time"),
            ),
            "resolution_criteria": _first_non_empty(
                question.get("resolution_criteria"),
                question.get("metadata", {}).get("raw_data", {}).get("resolution_criteria"),
            ),
            "resolution_notes": _first_non_empty(
                question.get("resolution_notes"),
                question.get("metadata", {}).get("raw_data", {}).get("resolution_notes"),
            ),
            "source_url": _first_non_empty(
                question.get("source_url"),
                question.get("metadata", {}).get("raw_data", {}).get("source_metadata", {}).get("source_url"),
            ),
            "tags": _stringify_tags(
                question.get("tags") or question.get("metadata", {}).get("raw_data", {}).get("tags")
            ),
            "recorded_at": _first_non_empty(
                forecast.get("recorded_at"),
                output.get("recorded_at"),
                output.get("metadata", {}).get("created_at"),
            ),
            "forecast_probability": probability,
            "forecast_confidence": forecast.get("confidence", output.get("confidence")),
            "forecast_reasoning": forecast.get("reasoning", output.get("reasoning")),
            "resolved": _question_resolved(question, fallback=forecast.get("resolved", output.get("resolved"))),
            "outcome": outcome,
            "brier_score": _first_non_empty(
                forecast.get("brier_score"),
                output.get("brier_score"),
                _brier_score(probability, outcome),
            ),
            "tokens_used": forecast.get("tokens") or usage.get("total_tokens"),
        }
        rows.append(row)

    fieldnames = [
        "run_id",
        "status",
        "provider",
        "user",
        "started_at",
        "completed_at",
        "duration_seconds",
        "total_tokens",
        "eval_brier_score",
        "eval_ece",
        "train_brier_score",
        "question_id",
        "question_title",
        "question_text",
        "question_description",
        "resolution_date",
        "resolution_criteria",
        "resolution_notes",
        "source_url",
        "tags",
        "recorded_at",
        "forecast_probability",
        "forecast_confidence",
        "forecast_reasoning",
        "resolved",
        "outcome",
        "brier_score",
        "tokens_used",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        if rows:
            writer.writerows(rows)


def _question_level_comparisons(left: dict[str, Any], right: dict[str, Any]) -> list[dict[str, Any]]:
    left_rows = {str(row["question_id"]): row for row in _flatten_forecasts(left) if row.get("question_id")}
    right_rows = {str(row["question_id"]): row for row in _flatten_forecasts(right) if row.get("question_id")}
    shared_ids = sorted(set(left_rows) & set(right_rows))
    comparisons = [
        _comparison_row("shared_questions", len(shared_ids), len(shared_ids), preference="higher"),
        _comparison_row("left_only_questions", len(set(left_rows) - set(right_rows)), 0, preference="lower"),
        _comparison_row("right_only_questions", 0, len(set(right_rows) - set(left_rows)), preference="lower"),
    ]
    if not shared_ids:
        return comparisons

    probability_shifts: list[tuple[str, float]] = []
    left_shared_briers: list[float] = []
    right_shared_briers: list[float] = []
    improved = 0
    regressed = 0

    for question_id in shared_ids:
        left_row = left_rows[question_id]
        right_row = right_rows[question_id]
        left_probability = left_row.get("forecast_probability")
        right_probability = right_row.get("forecast_probability")
        if isinstance(left_probability, (int, float)) and isinstance(right_probability, (int, float)):
            probability_shifts.append((question_id, abs(float(right_probability) - float(left_probability))))

        left_brier = left_row.get("brier_score")
        right_brier = right_row.get("brier_score")
        if isinstance(left_brier, (int, float)) and isinstance(right_brier, (int, float)):
            left_brier_value = float(left_brier)
            right_brier_value = float(right_brier)
            left_shared_briers.append(left_brier_value)
            right_shared_briers.append(right_brier_value)
            if right_brier_value < left_brier_value:
                improved += 1
            elif right_brier_value > left_brier_value:
                regressed += 1

    if probability_shifts:
        largest_id, largest_shift = max(probability_shifts, key=lambda item: item[1])
        comparisons.append(
            _comparison_row(
                "avg_abs_probability_shift",
                0.0,
                sum(shift for _, shift in probability_shifts) / len(probability_shifts),
            )
        )
        comparisons.append(
            _comparison_row(
                f"largest_probability_shift ({largest_id})",
                0.0,
                largest_shift,
            )
        )

    if left_shared_briers and right_shared_briers:
        comparisons.append(
            _comparison_row(
                "shared_question_brier",
                sum(left_shared_briers) / len(left_shared_briers),
                sum(right_shared_briers) / len(right_shared_briers),
                preference="lower",
            )
        )
        comparisons.append(_comparison_row("shared_questions_improved", 0, improved, preference="higher"))
        comparisons.append(_comparison_row("shared_questions_regressed", 0, regressed, preference="lower"))

    return comparisons


def _flatten_forecasts(detail: dict[str, Any]) -> list[dict[str, Any]]:
    summary = detail.get("summary", {})
    run_metadata = detail.get("run", {})
    started_at = run_metadata.get("started_at") or run_metadata.get("created_at")
    completed_at = run_metadata.get("completed_at") or run_metadata.get("updated_at")
    rows: list[dict[str, Any]] = []
    for forecast in detail.get("forecasts", []):
        output = forecast.get("output", {}) if isinstance(forecast.get("output"), dict) else {}
        question_id = str(forecast.get("question_id") or output.get("question_id") or "")
        question = _merge_question_payloads(
            {str(item.get("id")): item for item in detail.get("questions", []) if item.get("id") is not None}.get(question_id, {}),
            forecast.get("question", {}) if isinstance(forecast.get("question"), dict) else {},
            output.get("question", {}) if isinstance(output.get("question"), dict) else {},
        )
        probability = forecast.get("probability", output.get("probability"))
        outcome = _question_outcome(question, fallback=forecast.get("outcome", output.get("outcome")))
        rows.append(
            {
                "run_id": run_metadata.get("run_id"),
                "started_at": started_at,
                "completed_at": completed_at,
                "eval_brier_score": summary.get("eval", {}).get("brier_score"),
                "eval_ece": summary.get("eval", {}).get("ece"),
                "train_brier_score": summary.get("train", {}).get("brier_score"),
                "question_id": question_id,
                "question_title": _first_non_empty(
                    question.get("title"),
                    question.get("question_text"),
                    question.get("metadata", {}).get("raw_data", {}).get("title"),
                ),
                "question_text": _first_non_empty(
                    question.get("question_text"),
                    question.get("title"),
                    question.get("description"),
                    question.get("metadata", {}).get("raw_data", {}).get("content"),
                ),
                "resolution_date": _first_non_empty(
                    question.get("resolution_date"),
                    question.get("resolution_time"),
                    question.get("metadata", {}).get("raw_data", {}).get("resolution_time"),
                ),
                "forecast_probability": probability,
                "resolved": _question_resolved(question, fallback=forecast.get("resolved", output.get("resolved"))),
                "outcome": outcome,
                "brier_score": _first_non_empty(
                    forecast.get("brier_score"),
                    output.get("brier_score"),
                    _brier_score(probability, outcome),
                ),
            }
        )
    return rows


def _comparison_row(metric: str, left: Any, right: Any, *, preference: str | None = None) -> dict[str, Any]:
    delta = _comparison_delta(left, right)
    return {
        "metric": metric,
        "left": left,
        "right": right,
        "delta": delta,
        "interpretation": _comparison_interpretation(delta=delta, preference=preference),
    }


def _comparison_delta(left: Any, right: Any) -> Any:
    if isinstance(left, bool) and isinstance(right, bool):
        return int(right) - int(left)
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return float(right) - float(left)
    if left == right:
        return 0
    return None


def _comparison_interpretation(*, delta: Any, preference: str | None) -> str:
    if preference == "lower" and isinstance(delta, (int, float)):
        if math.isclose(float(delta), 0.0, abs_tol=1e-12):
            return "lower is better; unchanged"
        return "lower is better; right improved" if delta < 0 else "lower is better; right regressed"
    if preference == "higher" and isinstance(delta, (int, float)):
        if math.isclose(float(delta), 0.0, abs_tol=1e-12):
            return "higher is better; unchanged"
        return "higher is better; right improved" if delta > 0 else "higher is better; right regressed"
    if delta == 0:
        return "unchanged"
    return "changed" if delta is None else "review in context"


def _merge_question_payloads(*candidates: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        merged = _deep_merge_dicts(merged, candidate)
    return merged


def _deep_merge_dicts(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dicts(merged[key], value)
        elif value not in (None, ""):
            merged[key] = value
    return merged


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _question_outcome(question: dict[str, Any], *, fallback: Any) -> bool | None:
    for candidate in (
        fallback,
        question.get("outcome"),
        question.get("resolved_outcome"),
        question.get("metadata", {}).get("raw_data", {}).get("resolved_outcome"),
    ):
        if isinstance(candidate, bool):
            return candidate
    return None


def _question_resolved(question: dict[str, Any], *, fallback: Any) -> bool | None:
    if isinstance(fallback, bool):
        return fallback
    outcome = _question_outcome(question, fallback=None)
    if outcome is not None:
        return True
    return None


def _brier_score(probability: Any, outcome: bool | None) -> float | None:
    if outcome is None or probability in (None, ""):
        return None
    try:
        probability_value = float(probability)
    except (TypeError, ValueError):
        return None
    target = 1.0 if outcome else 0.0
    return (probability_value - target) ** 2


def _stringify_tags(tags: Any) -> str | None:
    if isinstance(tags, list):
        return ",".join(str(tag) for tag in tags if tag not in (None, ""))
    if tags in (None, ""):
        return None
    return str(tags)


def _nested_get(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


__all__ = ["compare_runs", "export_run", "latest_run_dir", "list_runs", "resolve_run_dir", "run_detail"]
