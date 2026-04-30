"""Canonical run artifact storage for XRTM product workflows."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from xrtm.product.observability import EventRecord, retention_candidates


@dataclass
class RunArtifact:
    """Metadata for one product run directory."""

    run_id: str
    run_dir: Path
    status: str
    command: str
    provider: str
    created_at: str
    updated_at: str
    package_versions: dict[str, str]
    artifacts: dict[str, str] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["run_dir"] = str(self.run_dir)
        return data


class ArtifactStore:
    """Writes and reads the canonical ``runs/<run-id>`` layout."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def create_run(self, *, command: str, provider: str, package_versions: dict[str, str]) -> RunArtifact:
        now = utc_now()
        run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
        run_dir = self.root / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        (run_dir / "logs").mkdir()
        run = RunArtifact(
            run_id=run_id,
            run_dir=run_dir,
            status="running",
            command=command,
            provider=provider,
            created_at=now,
            updated_at=now,
            package_versions=package_versions,
        )
        self.write_json(run, "run.json", run.to_json_dict())
        self.write_json(run, "monitor.json", {"status": "idle", "watches": []})
        return run

    def write_json(self, run: RunArtifact, name: str, payload: Any) -> Path:
        path = run.run_dir / name
        path.write_text(json.dumps(to_json_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        run.artifacts[name] = str(path)
        run.updated_at = utc_now()
        return path

    def write_jsonl(self, run: RunArtifact, name: str, rows: list[Any]) -> Path:
        path = run.run_dir / name
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(to_json_safe(row), sort_keys=True) + "\n")
        run.artifacts[name] = str(path)
        run.updated_at = utc_now()
        return path

    def append_event(self, run: RunArtifact, event: str, **payload: Any) -> None:
        path = run.run_dir / "events.jsonl"
        record = EventRecord(event_type=event, timestamp=utc_now(), payload=payload).to_json_dict()
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(to_json_safe(record), sort_keys=True) + "\n")
        run.artifacts["events.jsonl"] = str(path)
        run.updated_at = utc_now()

    def write_summary(self, run: RunArtifact, payload: dict[str, Any]) -> Path:
        run.summary = payload
        return self.write_json(run, "run_summary.json", payload)

    def finish(self, run: RunArtifact, *, status: str, errors: list[str] | None = None) -> None:
        run.status = status
        run.errors = errors or run.errors
        run.updated_at = utc_now()
        self.write_json(run, "run.json", run.to_json_dict())

    @staticmethod
    def read_run(run_dir: Path) -> dict[str, Any]:
        run_path = run_dir / "run.json"
        if not run_path.exists():
            raise FileNotFoundError(f"{run_path} does not exist")
        return json.loads(run_path.read_text(encoding="utf-8"))

    @staticmethod
    def read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    @staticmethod
    def cleanup_runs(*, runs_dir: Path, keep: int, dry_run: bool = True) -> list[Path]:
        candidates = retention_candidates(runs_dir=runs_dir, keep=keep)
        if not dry_run:
            for path in candidates:
                shutil.rmtree(path)
        return candidates


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_json_safe(value: Any) -> Any:
    """Convert Pydantic/dataclass/datetime-rich objects into JSON-safe values."""

    if hasattr(value, "model_dump"):
        return to_json_safe(value.model_dump(mode="json"))
    if hasattr(value, "to_json_dict"):
        return to_json_safe(value.to_json_dict())
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): to_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_json_safe(item) for item in value]
    return value


__all__ = ["ArtifactStore", "RunArtifact", "to_json_safe", "utc_now"]
