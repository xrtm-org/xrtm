"""Editable local WebUI workbench services for workflow canvas operations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from xrtm.product.history import compare_runs, resolve_run_dir
from xrtm.product.read_models import list_run_records, read_run_detail
from xrtm.product.workflow_runner import run_workflow_blueprint
from xrtm.product.workflows import (
    AGGREGATE_CANDIDATES_IMPLEMENTATION,
    WorkflowBlueprint,
    WorkflowRegistry,
    aggregate_candidate_upstreams,
    validate_product_blueprint,
    validate_workflow_name,
)

MAX_SAFE_QUESTION_LIMIT = 25


class WorkbenchInputError(ValueError):
    """Raised when a workbench form submission is invalid or unsafe."""


@dataclass(frozen=True)
class WorkbenchRunResult:
    run_id: str
    run_dir: Path
    baseline_run_id: str | None
    compare_rows: list[dict[str, Any]]


def workbench_snapshot(
    runs_dir: Path,
    workflows_dir: Path,
    *,
    run_ref: str | None = None,
    workflow_name: str | None = None,
    compare_ref: str | None = None,
) -> dict[str, Any]:
    """Return the server-rendered workbench model."""

    registry = workflow_registry_for(workflows_dir)
    runs = list_run_records(runs_dir)
    selected_run_detail: dict[str, Any] | None = None
    selected_run_ref = _selected_run_ref(runs, run_ref)
    selected_run_dir: Path | None = None
    if selected_run_ref is not None:
        selected_run_dir = resolve_run_dir(runs_dir, selected_run_ref)
        selected_run_detail = read_run_detail(selected_run_dir)

    workflow_summaries = registry.list_workflows()
    selected_workflow_name = workflow_name or _workflow_name_from_run(selected_run_detail) or _first_workflow_name(workflow_summaries)
    selected_workflow: WorkflowBlueprint | None = None
    workflow_error: str | None = None
    if selected_workflow_name is not None:
        try:
            selected_workflow = registry.load(selected_workflow_name)
        except (FileNotFoundError, ValueError) as exc:
            workflow_error = str(exc)

    validation = validate_workbench_workflow(registry, selected_workflow_name) if selected_workflow_name else None
    compare_rows: list[dict[str, Any]] = []
    compare_error: str | None = None
    if compare_ref and selected_run_dir is not None:
        try:
            compare_rows = compare_runs(resolve_run_dir(runs_dir, compare_ref), selected_run_dir)
        except (FileNotFoundError, ValueError) as exc:
            compare_error = str(exc)

    return {
        "runs_dir": str(runs_dir),
        "workflows_dir": str(_workflow_root(workflows_dir)),
        "runs": runs,
        "selected_run_ref": selected_run_ref,
        "selected_run": selected_run_detail,
        "workflows": [workflow.__dict__ for workflow in workflow_summaries],
        "selected_workflow_name": selected_workflow_name,
        "selected_workflow": selected_workflow.to_json_dict() if selected_workflow is not None else None,
        "selected_workflow_source": _workflow_source(workflow_summaries, selected_workflow_name),
        "workflow_error": workflow_error,
        "validation": validation,
        "canvas": workflow_canvas(selected_workflow, selected_run_detail),
        "safe_edit": safe_edit_model(selected_workflow) if selected_workflow is not None else None,
        "compare_ref": compare_ref,
        "compare_rows": compare_rows,
        "compare_error": compare_error,
        "limits": {"max_questions": MAX_SAFE_QUESTION_LIMIT},
    }


def workflow_registry_for(workflows_dir: Path) -> WorkflowRegistry:
    """Build a workbench registry rooted at the configured local workflows dir."""

    return WorkflowRegistry(local_roots=(_workflow_root(workflows_dir),))


def clone_workflow_for_edit(
    registry: WorkflowRegistry,
    *,
    source_name: str,
    target_name: str,
    overwrite: bool = False,
) -> Path:
    """Clone a builtin/local workflow into the editable local workflow root."""

    source_name = _required_name(source_name, "source workflow")
    target_name = _required_name(target_name, "target workflow")
    source = registry.validate(source_name)
    payload = source.to_json_dict()
    payload["name"] = target_name
    cloned = WorkflowBlueprint.from_payload(payload)
    validate_product_blueprint(cloned)
    try:
        return registry.save(cloned, overwrite=overwrite)
    except FileExistsError as exc:
        raise WorkbenchInputError(str(exc)) from exc


def validate_workbench_workflow(registry: WorkflowRegistry, workflow_name: str | None) -> dict[str, Any]:
    """Validate one workflow for safe product execution and return a UI-friendly result."""

    if not workflow_name:
        return {"ok": False, "errors": ["Select a workflow first."]}
    try:
        blueprint = registry.validate(workflow_name)
    except (FileNotFoundError, ValueError) as exc:
        return {"ok": False, "errors": str(exc).splitlines()}
    return {"ok": True, "errors": [], "workflow": blueprint.name}


def apply_workbench_edit(
    registry: WorkflowRegistry,
    *,
    workflow_name: str,
    values: Mapping[str, str],
) -> WorkflowBlueprint:
    """Apply the MVP safe-edit form to an existing local workflow."""

    workflow_name = _required_name(workflow_name, "workflow")
    _ensure_local_workflow(registry, workflow_name)
    blueprint = registry.load(workflow_name)
    allowed = _allowed_edit_fields(blueprint)
    unexpected = sorted(set(values) - allowed)
    if unexpected:
        raise WorkbenchInputError("unsupported edit field(s): " + ", ".join(unexpected))

    if "questions_limit" not in values:
        raise WorkbenchInputError("questions_limit is required")
    if "artifacts_write_report" not in values:
        raise WorkbenchInputError("artifacts_write_report is required")

    limit = _parse_question_limit(values["questions_limit"])
    write_report = _parse_bool(values["artifacts_write_report"], field="artifacts_write_report")
    payload = blueprint.to_json_dict()
    payload["questions"]["limit"] = limit
    payload["artifacts"]["write_report"] = write_report

    for editor in aggregate_weight_editors(blueprint):
        node_name = editor["node"]
        contributor_names = [contributor["name"] for contributor in editor["contributors"]]
        for contributor in contributor_names:
            key = f"weight:{node_name}:{contributor}"
            if key not in values:
                raise WorkbenchInputError(f"{key} is required")
        submitted = {
            contributor: _parse_weight(values[f"weight:{node_name}:{contributor}"], node=node_name, contributor=contributor)
            for contributor in contributor_names
        }
        payload["graph"]["nodes"][node_name].setdefault("config", {})["weights"] = _normalize_weights(submitted)

    updated = WorkflowBlueprint.from_payload(payload)
    validate_product_blueprint(updated)
    registry.save(updated, overwrite=True)
    return updated


def run_workbench_workflow(
    registry: WorkflowRegistry,
    *,
    workflow_name: str,
    runs_dir: Path,
    baseline_run_ref: str | None = None,
    user: str | None = None,
) -> WorkbenchRunResult:
    """Validate and run an editable workflow, comparing to the baseline run when present."""

    workflow_name = _required_name(workflow_name, "workflow")
    blueprint = registry.validate(workflow_name)
    baseline_run_dir: Path | None = None
    baseline_run_id: str | None = None
    if baseline_run_ref:
        baseline_run_dir = resolve_run_dir(runs_dir, baseline_run_ref)
        baseline_run_id = baseline_run_dir.name
    result = run_workflow_blueprint(
        blueprint,
        command=f"xrtm web workflow run {workflow_name}",
        runs_dir=runs_dir,
        user=user,
    )
    rows = compare_runs(baseline_run_dir, result.run.run_dir) if baseline_run_dir is not None else []
    return WorkbenchRunResult(
        run_id=result.run.run_id,
        run_dir=result.run.run_dir,
        baseline_run_id=baseline_run_id,
        compare_rows=rows,
    )


def workflow_canvas(blueprint: WorkflowBlueprint | None, run_detail: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a compact canvas model with blueprint nodes and optional run status."""

    if blueprint is None:
        return {"nodes": [], "edges": [], "parallel_groups": {}, "conditional_routes": {}}
    status_by_node = _status_by_node(blueprint, run_detail)
    node_names = list(blueprint.graph.nodes) + list(blueprint.graph.parallel_groups)
    depths = _node_depths(blueprint)
    rows_by_depth: dict[int, int] = {}
    nodes = []
    for name in node_names:
        node = blueprint.graph.nodes.get(name)
        kind = "parallel-group" if node is None else node.kind
        implementation = None if node is None else node.implementation
        description = "Parallel group: " + ", ".join(blueprint.graph.parallel_groups[name].nodes) if node is None else node.description
        depth = depths.get(name, 0)
        row = rows_by_depth.get(depth, 0)
        rows_by_depth[depth] = row + 1
        nodes.append(
            {
                "name": name,
                "kind": kind,
                "implementation": implementation,
                "description": description or "",
                "status": status_by_node.get(name, "not-run"),
                "x": 30 + depth * 230,
                "y": 30 + row * 115,
            }
        )
    edges = [{"from": edge.from_node, "to": edge.to_node} for edge in blueprint.graph.edges]
    for source, route in blueprint.graph.conditional_routes.items():
        for label, target in route.routes.items():
            edges.append({"from": source, "to": target, "label": label})
    return {
        "nodes": nodes,
        "edges": edges,
        "parallel_groups": {name: list(group.nodes) for name, group in blueprint.graph.parallel_groups.items()},
        "conditional_routes": {name: route.to_json_dict() for name, route in blueprint.graph.conditional_routes.items()},
    }


def safe_edit_model(blueprint: WorkflowBlueprint) -> dict[str, Any]:
    """Return the explicitly supported safe-edit controls for a workflow."""

    return {
        "questions_limit": {
            "value": blueprint.questions.limit,
            "min": 1,
            "max": MAX_SAFE_QUESTION_LIMIT,
        },
        "artifacts_write_report": blueprint.artifacts.write_report,
        "aggregate_weight_editors": aggregate_weight_editors(blueprint),
        "limitations": [
            "No node add/delete.",
            "No implementation edits.",
            "No arbitrary JSON config editor.",
            "No new question source or corpus.",
            "Execution stays inside the safe product node library.",
        ],
    }


def aggregate_weight_editors(blueprint: WorkflowBlueprint) -> list[dict[str, Any]]:
    """Describe editable aggregate-node weights constrained to upstream candidate nodes."""

    editors = []
    for node_name, node in blueprint.graph.nodes.items():
        if node.implementation != AGGREGATE_CANDIDATES_IMPLEMENTATION:
            continue
        contributors = aggregate_candidate_upstreams(blueprint, node_name)
        if not contributors:
            continue
        current_weights = node.config.get("weights", {}) if isinstance(node.config.get("weights", {}), dict) else {}
        normalized = _defaulted_normalized_weights(contributors, current_weights)
        editors.append(
            {
                "node": node_name,
                "contributors": [
                    {
                        "name": contributor,
                        "weight": normalized[contributor],
                        "percent": round(normalized[contributor] * 100),
                    }
                    for contributor in contributors
                ],
            }
        )
    return editors


def _workflow_root(workflows_dir: Path) -> Path:
    return workflows_dir if workflows_dir.is_absolute() else Path.cwd() / workflows_dir


def _selected_run_ref(runs: list[dict[str, Any]], run_ref: str | None) -> str | None:
    if run_ref:
        return run_ref
    if runs:
        return str(runs[0].get("run_id"))
    return None


def _workflow_name_from_run(run_detail: dict[str, Any] | None) -> str | None:
    if not run_detail:
        return None
    blueprint = run_detail.get("blueprint")
    if isinstance(blueprint, dict) and isinstance(blueprint.get("name"), str):
        return blueprint["name"]
    workflow = run_detail.get("workflow")
    if isinstance(workflow, dict) and isinstance(workflow.get("name"), str):
        return workflow["name"]
    return None


def _first_workflow_name(workflow_summaries: list[Any]) -> str | None:
    return workflow_summaries[0].name if workflow_summaries else None


def _workflow_source(workflow_summaries: list[Any], workflow_name: str | None) -> dict[str, Any] | None:
    if workflow_name is None:
        return None
    for summary in workflow_summaries:
        if summary.name == workflow_name:
            return summary.__dict__
    return None


def _required_name(value: str, label: str) -> str:
    name = str(value or "").strip()
    if not name:
        raise WorkbenchInputError(f"{label} is required")
    try:
        validate_workflow_name(name)
    except ValueError as exc:
        raise WorkbenchInputError(str(exc)) from exc
    return name


def _ensure_local_workflow(registry: WorkflowRegistry, workflow_name: str) -> None:
    if registry.local_path(workflow_name).exists():
        return
    raise WorkbenchInputError("clone this workflow into the local workflows directory before editing")


def _allowed_edit_fields(blueprint: WorkflowBlueprint) -> set[str]:
    fields = {"questions_limit", "artifacts_write_report"}
    for editor in aggregate_weight_editors(blueprint):
        node_name = editor["node"]
        fields.update(f"weight:{node_name}:{contributor['name']}" for contributor in editor["contributors"])
    return fields


def _parse_question_limit(raw: str) -> int:
    try:
        value = int(str(raw).strip())
    except ValueError as exc:
        raise WorkbenchInputError("questions.limit must be an integer") from exc
    if value < 1 or value > MAX_SAFE_QUESTION_LIMIT:
        raise WorkbenchInputError(f"questions.limit must be between 1 and {MAX_SAFE_QUESTION_LIMIT}")
    return value


def _parse_bool(raw: str, *, field: str) -> bool:
    normalized = str(raw).strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise WorkbenchInputError(f"{field} must be true or false")


def _parse_weight(raw: str, *, node: str, contributor: str) -> float:
    try:
        value = float(str(raw).strip())
    except ValueError as exc:
        raise WorkbenchInputError(f"weight for {node}/{contributor} must be numeric") from exc
    if not math.isfinite(value) or value < 0 or value > 100:
        raise WorkbenchInputError(f"weight for {node}/{contributor} must be between 0 and 100")
    return value


def _normalize_weights(weights: Mapping[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        raise WorkbenchInputError("at least one aggregate weight must be greater than zero")
    return {name: value / total for name, value in weights.items()}


def _defaulted_normalized_weights(contributors: list[str], current_weights: Mapping[str, Any]) -> dict[str, float]:
    raw: dict[str, float] = {}
    for contributor in contributors:
        try:
            value = float(current_weights.get(contributor, 1.0))
        except (TypeError, ValueError):
            value = 1.0
        raw[contributor] = value if math.isfinite(value) and value >= 0 else 1.0
    if sum(raw.values()) <= 0:
        return {contributor: 1.0 / len(contributors) for contributor in contributors}
    return _normalize_weights(raw)


def _status_by_node(blueprint: WorkflowBlueprint, run_detail: dict[str, Any] | None) -> dict[str, str]:
    if not run_detail:
        return {}
    run_blueprint = run_detail.get("blueprint")
    if isinstance(run_blueprint, dict) and run_blueprint.get("name") != blueprint.name:
        return {}
    statuses: dict[str, str] = {}
    for row in run_detail.get("graph_trace", []):
        if isinstance(row, dict) and isinstance(row.get("node"), str):
            statuses[row["node"]] = str(row.get("status", "observed"))
    return statuses


def _node_depths(blueprint: WorkflowBlueprint) -> dict[str, int]:
    names = set(blueprint.graph.nodes) | set(blueprint.graph.parallel_groups)
    depths = {name: 0 for name in names}
    if blueprint.graph.entry in depths:
        depths[blueprint.graph.entry] = 0
    transitions: list[tuple[str, str]] = [(edge.from_node, edge.to_node) for edge in blueprint.graph.edges]
    for source, route in blueprint.graph.conditional_routes.items():
        transitions.extend((source, target) for target in route.routes.values())
    for group_name, group in blueprint.graph.parallel_groups.items():
        transitions.extend((group_name, member) for member in group.nodes)
    for _ in range(max(len(transitions), 1)):
        changed = False
        for source, target in transitions:
            if source not in depths or target not in depths:
                continue
            next_depth = depths[source] + 1
            if next_depth > depths[target]:
                depths[target] = next_depth
                changed = True
        if not changed:
            break
    return depths


__all__ = [
    "MAX_SAFE_QUESTION_LIMIT",
    "WorkbenchInputError",
    "WorkbenchRunResult",
    "aggregate_weight_editors",
    "apply_workbench_edit",
    "clone_workflow_for_edit",
    "run_workbench_workflow",
    "safe_edit_model",
    "validate_workbench_workflow",
    "workbench_snapshot",
    "workflow_canvas",
    "workflow_registry_for",
]
