"""Versioned observability contracts for product run artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

EVENT_SCHEMA_VERSION = "xrtm.events.v1"
SUMMARY_SCHEMA_VERSION = "xrtm.run-summary.v1"
MONITOR_SCHEMA_VERSION = "xrtm.monitor.v1"

EVENT_TYPES = frozenset(
    {
        "run_started",
        "run_completed",
        "run_failed",
        "provider_request_started",
        "provider_request_completed",
        "forecast_written",
        "eval_completed",
        "train_completed",
        "competition_submission_prepared",
        "workflow_blueprint_attached",
        "monitor_started",
        "monitor_cycle_started",
        "monitor_cycle_completed",
        "monitor_status_changed",
        "warning",
        "error",
    }
)

MONITOR_STATES = frozenset({"created", "running", "paused", "degraded", "failed", "halted"})


@dataclass(frozen=True)
class EventRecord:
    """One line in a product ``events.jsonl`` stream."""

    event_type: str
    timestamp: str
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: uuid4().hex)
    schema_version: str = EVENT_SCHEMA_VERSION

    def to_json_dict(self) -> dict[str, Any]:
        validate_event_type(self.event_type)
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            **self.payload,
        }


@dataclass(frozen=True)
class MonitorThresholds:
    """User-tunable monitor thresholds persisted in ``monitor.json``."""

    probability_delta: float = 0.10
    confidence_shift: float = 0.20
    stale_after_seconds: int = 3600
    provider_failures: int = 1
    eval_brier_score: float = 0.25

    def __post_init__(self) -> None:
        for name, value in {
            "probability_delta": self.probability_delta,
            "confidence_shift": self.confidence_shift,
            "eval_brier_score": self.eval_brier_score,
        }.items():
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.stale_after_seconds < 1:
            raise ValueError("stale_after_seconds must be at least 1")
        if self.provider_failures < 1:
            raise ValueError("provider_failures must be at least 1")

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "probability_delta": self.probability_delta,
            "confidence_shift": self.confidence_shift,
            "stale_after_seconds": self.stale_after_seconds,
            "provider_failures": self.provider_failures,
            "eval_brier_score": self.eval_brier_score,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> "MonitorThresholds":
        if not payload:
            return cls()
        defaults = cls()
        return cls(
            probability_delta=float(payload.get("probability_delta", defaults.probability_delta)),
            confidence_shift=float(payload.get("confidence_shift", defaults.confidence_shift)),
            stale_after_seconds=int(payload.get("stale_after_seconds", defaults.stale_after_seconds)),
            provider_failures=int(payload.get("provider_failures", defaults.provider_failures)),
            eval_brier_score=float(payload.get("eval_brier_score", defaults.eval_brier_score)),
        )


def validate_event_type(event_type: str) -> None:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unsupported event type: {event_type}")


def validate_monitor_state(status: str) -> None:
    if status not in MONITOR_STATES:
        raise ValueError(f"unsupported monitor status: {status}")


def build_run_summary(
    *,
    status: str,
    provider: str,
    total_seconds: float,
    forecast_records: list[Any],
    eval_payload: dict[str, Any] | None = None,
    train_payload: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    """Build the versioned ``run_summary.json`` payload."""

    warning_count = len(warnings or [])
    error_count = len(errors or [])
    token_usage = _sum_token_usage(forecast_records)
    provider_latency_ms = _provider_latency_ms(forecast_records)
    eval_summary = (eval_payload or {}).get("summary_statistics", {})
    train_summary = (train_payload or {}).get("summary_statistics", {})
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": status,
        "provider": provider,
        "duration_seconds": total_seconds,
        "forecast_count": len(forecast_records),
        "provider_latency_ms": provider_latency_ms,
        "token_counts": token_usage,
        "warning_count": warning_count,
        "error_count": error_count,
        "eval": {
            "brier_score": eval_summary.get("brier_score"),
            "ece": eval_summary.get("ece"),
            "calibration_error": eval_summary.get("calibration_error"),
            "total_evaluations": (eval_payload or {}).get("total_evaluations"),
        },
        "train": {
            "brier_score": train_summary.get("brier_score"),
            "total_evaluations": (train_payload or {}).get("total_evaluations"),
            "training_samples": (train_payload or {}).get("training_samples"),
        },
    }


def monitor_summary(monitor: dict[str, Any]) -> dict[str, Any]:
    """Return compact monitor metrics for UI/API surfaces."""

    watches = monitor.get("watches", [])
    warning_count = 0
    error_count = 0
    update_count = 0
    degraded_count = 0
    for watch in watches:
        warning_count += len(watch.get("warnings", []))
        error_count += len(watch.get("errors", []))
        update_count += len(watch.get("trajectory", []))
        if watch.get("status") == "degraded":
            degraded_count += 1
    return {
        "schema_version": "xrtm.monitor-summary.v1",
        "status": monitor.get("status"),
        "watches": len(watches),
        "updates": update_count,
        "degraded_watches": degraded_count,
        "warning_count": warning_count,
        "error_count": error_count,
        "updated_at": monitor.get("updated_at"),
    }


def evaluate_probability_threshold(
    *,
    watch: dict[str, Any],
    probability: float,
    thresholds: MonitorThresholds,
) -> list[str]:
    """Return warnings triggered by a new monitor probability update."""

    trajectory = watch.get("trajectory", [])
    if not trajectory:
        return []
    previous_probability = trajectory[-1].get("probability")
    if previous_probability is None:
        return []
    previous = float(previous_probability)
    delta = abs(probability - previous)
    warnings: list[str] = []
    if delta >= thresholds.probability_delta:
        warnings.append(
            f"probability_delta threshold exceeded: {previous:.3f} -> {probability:.3f} (delta {delta:.3f})"
        )
    previous_confidence = abs(previous - 0.5) * 2
    current_confidence = abs(probability - 0.5) * 2
    confidence_delta = abs(current_confidence - previous_confidence)
    if confidence_delta >= thresholds.confidence_shift:
        warnings.append(f"confidence_shift threshold exceeded: delta {confidence_delta:.3f}")
    return warnings


def retention_candidates(*, runs_dir: Path, keep: int) -> list[Path]:
    """Return run directories that exceed the keep-count retention policy."""

    if keep < 1:
        raise ValueError("keep must be at least 1")
    if not runs_dir.exists():
        return []
    run_dirs = sorted((path for path in runs_dir.iterdir() if path.is_dir()), key=lambda path: path.name, reverse=True)
    return sorted(run_dirs[keep:])


def _sum_token_usage(records: list[Any]) -> dict[str, int]:
    totals = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for record in records:
        usage = _provider_metadata(record).get("usage", {})
        for key in totals:
            totals[key] += int(usage.get(key, 0) or 0)
    return totals


def _provider_latency_ms(records: list[Any]) -> dict[str, float | None]:
    values = []
    for record in records:
        metadata = _provider_metadata(record)
        response_metadata = metadata.get("response_metadata", {})
        latency = response_metadata.get("latency_ms") or metadata.get("latency_ms")
        if latency is not None:
            values.append(float(latency))
    if not values:
        return {"mean": None, "max": None}
    return {"mean": sum(values) / len(values), "max": max(values)}


def _provider_metadata(record: Any) -> dict[str, Any]:
    metadata = getattr(record, "provider_metadata", None)
    if isinstance(metadata, dict):
        return metadata
    if isinstance(record, dict):
        payload = record.get("provider_metadata", {})
        if isinstance(payload, dict):
            return payload
    return {}


__all__ = [
    "EVENT_SCHEMA_VERSION",
    "EVENT_TYPES",
    "MONITOR_SCHEMA_VERSION",
    "MONITOR_STATES",
    "SUMMARY_SCHEMA_VERSION",
    "EventRecord",
    "MonitorThresholds",
    "build_run_summary",
    "evaluate_probability_threshold",
    "monitor_summary",
    "retention_candidates",
    "validate_event_type",
    "validate_monitor_state",
]
