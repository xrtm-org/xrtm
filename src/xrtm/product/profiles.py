"""Local workflow profiles for repeatable product runs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from xrtm.product.pipeline import PipelineOptions

PROFILE_SCHEMA_VERSION = "xrtm.profile.v1"
DEFAULT_PROFILES_DIR = Path(".xrtm/profiles")
STARTER_PROFILE_LIMIT = 5
_PROFILE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class WorkflowProfile:
    """A saved provider/run configuration."""

    name: str
    provider: str = "mock"
    limit: int = 2
    runs_dir: str = "runs"
    base_url: str | None = None
    model: str | None = None
    max_tokens: int = 768
    write_report: bool = True
    user: str | None = None
    schema_version: str = PROFILE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        validate_profile_name(self.name)
        if self.provider not in {"mock", "local-llm"}:
            raise ValueError(f"unsupported provider: {self.provider}")
        if self.limit < 1:
            raise ValueError("limit must be at least 1")
        if self.max_tokens < 1:
            raise ValueError("max_tokens must be at least 1")

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "provider": self.provider,
            "limit": self.limit,
            "runs_dir": self.runs_dir,
            "base_url": self.base_url,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "write_report": self.write_report,
            "user": self.user,
        }

    def to_pipeline_options(self, *, runs_dir: Path | None = None, command: str | None = None) -> PipelineOptions:
        return PipelineOptions(
            provider=self.provider,
            limit=self.limit,
            runs_dir=runs_dir or Path(self.runs_dir),
            base_url=self.base_url,
            model=self.model,
            max_tokens=self.max_tokens,
            write_report=self.write_report,
            command=command or f"xrtm run profile {self.name}",
            user=self.user,
        )

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "WorkflowProfile":
        return cls(
            name=str(payload["name"]),
            provider=str(payload.get("provider", "mock")),
            limit=int(payload.get("limit", 2)),
            runs_dir=str(payload.get("runs_dir", "runs")),
            base_url=payload.get("base_url"),
            model=payload.get("model"),
            max_tokens=int(payload.get("max_tokens", 768)),
            write_report=bool(payload.get("write_report", True)),
            user=payload.get("user"),
            schema_version=str(payload.get("schema_version", PROFILE_SCHEMA_VERSION)),
        )


class ProfileStore:
    """Filesystem-backed profile storage."""

    def __init__(self, root: Path = DEFAULT_PROFILES_DIR) -> None:
        self.root = root

    def create(self, profile: WorkflowProfile, *, overwrite: bool = False) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.path_for(profile.name)
        if path.exists() and not overwrite:
            raise FileExistsError(f"profile already exists: {profile.name}")
        path.write_text(json.dumps(profile.to_json_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def load(self, name: str) -> WorkflowProfile:
        path = self.path_for(name)
        if not path.exists():
            raise FileNotFoundError(f"profile does not exist: {name}")
        return WorkflowProfile.from_payload(json.loads(path.read_text(encoding="utf-8")))

    def list_profiles(self) -> list[WorkflowProfile]:
        if not self.root.exists():
            return []
        profiles = []
        for path in sorted(self.root.glob("*.json")):
            profiles.append(WorkflowProfile.from_payload(json.loads(path.read_text(encoding="utf-8"))))
        return profiles

    def path_for(self, name: str) -> Path:
        validate_profile_name(name)
        return self.root / f"{name}.json"


def validate_profile_name(name: str) -> None:
    if name in {"", ".", ".."}:
        raise ValueError("profile name may not be empty, '.', or '..'")
    if not _PROFILE_NAME.fullmatch(name):
        raise ValueError("profile name may only contain letters, numbers, dots, underscores, and dashes")


def starter_profile(name: str, *, runs_dir: Path = Path("runs"), user: str | None = None) -> WorkflowProfile:
    """Create the minimal reusable local profile suggested after xrtm start."""

    return WorkflowProfile(
        name=name,
        provider="mock",
        limit=STARTER_PROFILE_LIMIT,
        runs_dir=str(runs_dir),
        user=user,
    )


__all__ = [
    "DEFAULT_PROFILES_DIR",
    "PROFILE_SCHEMA_VERSION",
    "ProfileStore",
    "STARTER_PROFILE_LIMIT",
    "WorkflowProfile",
    "starter_profile",
]
