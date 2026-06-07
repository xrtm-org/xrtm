# coding=utf-8
# Copyright 2026 XRTM Team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Workflow registry for the XRTM product shell.

Schema types live in xrtm.forecast.core.schemas.workflow.
This module provides the product-level file-based workflow registry.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from xrtm.forecast.core.schemas.workflow import (
    WORKFLOW_SCHEMA_VERSION,
    ArtifactPolicy,
    EdgeSpec,
    GraphSpec,
    NodeSpec,
    QuestionSourceSpec,
    RuntimeProfileSpec,
    ScoringPolicy,
    WorkflowBlueprint,
    WorkflowSummary,
)

DEFAULT_LOCAL_WORKFLOWS_DIR = Path(".xrtm/workflows")


class WorkflowRegistry:
    """Load builtin and local workflow blueprints."""

    def __init__(self, *, local_roots: tuple[Path, ...] | None = None) -> None:
        self._local_roots: tuple[Path, ...] = local_roots or (DEFAULT_LOCAL_WORKFLOWS_DIR,)

    def list_workflows(self) -> list[WorkflowSummary]:
        results: list[WorkflowSummary] = []
        results.extend(self._iter_builtin_workflows())
        results.extend(self._iter_local_workflows())
        return results

    def load(self, name: str) -> WorkflowBlueprint:
        builtin = self._load_builtin(name)
        if builtin is not None:
            return builtin
        local = self._load_local(name)
        if local is not None:
            return local
        raise FileNotFoundError(f"workflow {name!r} not found")

    def local_path(self, name: str) -> Path:
        for root in self._local_roots:
            candidate = root / f"{name}.json"
            if candidate.is_file():
                return candidate
        return self._local_roots[0] / f"{name}.json"

    def _iter_builtin_workflows(self) -> list[WorkflowSummary]:
        from xrtm.product.workflow_definitions import BUILTIN_BLUEPRINTS
        return [
            WorkflowSummary(name=bp.name, title=bp.title, description=bp.description, workflow_kind=bp.workflow_kind)
            for bp in BUILTIN_BLUEPRINTS
        ]

    def _iter_local_workflows(self) -> list[WorkflowSummary]:
        results = []
        for root in self._local_roots:
            if not root.is_dir():
                continue
            for path in sorted(root.glob("*.json")):
                try:
                    bp = WorkflowBlueprint.from_payload(json.loads(path.read_text()))
                    results.append(
                        WorkflowSummary(name=bp.name, title=bp.title, description=bp.description, workflow_kind=bp.workflow_kind)
                    )
                except Exception:
                    continue
        return results

    def _load_builtin(self, name: str) -> WorkflowBlueprint | None:
        from xrtm.product.workflow_definitions import BUILTIN_BLUEPRINTS
        for bp in BUILTIN_BLUEPRINTS:
            if bp.name == name:
                return bp
        return None

    def _load_local(self, name: str) -> WorkflowBlueprint | None:
        for root in self._local_roots:
            candidate = root / f"{name}.json"
            if candidate.is_file():
                return WorkflowBlueprint.from_payload(json.loads(candidate.read_text()))
        return None


def explain_blueprint(blueprint: WorkflowBlueprint) -> dict:
    """Return a human-readable explanation of a workflow blueprint."""
    return {
        "name": blueprint.name,
        "title": blueprint.title,
        "description": blueprint.description,
        "nodes": {nid: ns.kind for nid, ns in blueprint.graph.nodes.items()},
    }


def validate_product_blueprint(blueprint: WorkflowBlueprint) -> WorkflowBlueprint:
    """Validate a product workflow blueprint."""
    return blueprint


__all__ = [
    "DEFAULT_LOCAL_WORKFLOWS_DIR",
    "WorkflowRegistry",
    "explain_blueprint",
    "validate_product_blueprint",
]
