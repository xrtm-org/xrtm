"""Competition pack registry and dry-run submission helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from xrtm.product.artifacts import utc_now


@dataclass(frozen=True)
class CompetitionPack:
    """One live-competition integration contract for dry-run workflow exports."""

    name: str
    title: str
    description: str
    workflow_name: str
    source: str
    submission_format: str
    submission_artifact: str = "competition_submission.json"
    default_endpoint: str | None = None
    auth_env_var: str | None = None
    review_required: bool = True
    dry_run_only: bool = True

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "workflow_name": self.workflow_name,
            "source": self.source,
            "submission_format": self.submission_format,
            "submission_artifact": self.submission_artifact,
            "default_endpoint": self.default_endpoint,
            "auth_env_var": self.auth_env_var,
            "review_required": self.review_required,
            "dry_run_only": self.dry_run_only,
        }


BUILTIN_COMPETITION_PACKS = (
    CompetitionPack(
        name="metaculus-cup",
        title="Metaculus Cup dry-run pack",
        description=(
            "Prepare a dry-run submission bundle for a Metaculus-Cup-style workflow without sending network "
            "traffic or requiring credentials."
        ),
        workflow_name="metaculus-cup-dryrun",
        source="metaculus-cup",
        submission_format="xrtm.competition.metaculus-cup.v1",
        submission_artifact="competition_submission.json",
        default_endpoint="https://www.metaculus.com/api2/questions/forecast/",
        auth_env_var="METACULUS_TOKEN",
    ),
)


class CompetitionPackRegistry:
    """List and load builtin competition packs."""

    def list_packs(self) -> list[CompetitionPack]:
        return sorted(BUILTIN_COMPETITION_PACKS, key=lambda pack: pack.name)

    def load(self, name: str) -> CompetitionPack:
        for pack in BUILTIN_COMPETITION_PACKS:
            if pack.name == name:
                return pack
        raise FileNotFoundError(f"competition pack does not exist: {name}")


def list_builtin_competition_packs() -> tuple[CompetitionPack, ...]:
    return BUILTIN_COMPETITION_PACKS


def competition_submission_payload(
    pack: CompetitionPack,
    records: tuple[Any, ...],
    *,
    run_id: str,
    config: dict[str, Any] | None = None,
    review_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a redacted dry-run submission bundle from workflow records."""

    payload_config = dict(config or {})
    transport = _redact_sensitive_fields(payload_config.get("transport", {}))
    forecasts = []
    for record in records:
        output = record.output
        forecasts.append(
            {
                "question_id": record.question_id,
                "probability": output.probability,
                "reasoning": output.reasoning,
                "forecast_id": f"{run_id}:{record.question_id}",
                "metadata": _redact_sensitive_fields(output.metadata.model_dump(mode="json")),
            }
        )
    return {
        "competition": pack.to_json_dict(),
        "mode": "dry-run" if pack.dry_run_only else "prepared",
        "generated_at": utc_now(),
        "instructions": "Review this bundle manually before any live submission. XRTM did not send network traffic.",
        "review_status": _redact_sensitive_fields(review_status or {"status": "not-required"}),
        "run_id": run_id,
        "submission": {
            "format": pack.submission_format,
            "transport": {
                "endpoint": pack.default_endpoint,
                "auth_env_var": pack.auth_env_var,
                **transport,
            },
            "forecast_count": len(forecasts),
            "forecasts": forecasts,
        },
    }


def _redact_sensitive_fields(value: Any, *, key_name: str = "") -> Any:
    sensitive = {"api_key", "authorization", "token", "secret", "password"}
    if isinstance(value, dict):
        return {str(key): _redact_sensitive_fields(item, key_name=str(key)) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_sensitive_fields(item, key_name=key_name) for item in value]
    if isinstance(value, tuple):
        return [_redact_sensitive_fields(item, key_name=key_name) for item in value]
    lowered = key_name.lower()
    if any(marker in lowered for marker in sensitive):
        return "[redacted]"
    return value


__all__ = [
    "CompetitionPack",
    "CompetitionPackRegistry",
    "competition_submission_payload",
    "list_builtin_competition_packs",
]
