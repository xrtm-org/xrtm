"""Editable local WebUI workbench services for workflow canvas operations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from xrtm.product import launch as launch_module
from xrtm.product.history import compare_runs, resolve_run_dir
from xrtm.product.read_models import list_run_records, read_run_detail
from xrtm.product.workflow_authoring import (
    WorkflowAuthoringError,
    WorkflowAuthoringService,
    add_workflow_edge,
    add_workflow_node,
    clone_workflow_blueprint,
    persist_authored_workflow,
    remove_workflow_edge,
    remove_workflow_node,
    set_workflow_entry,
    update_workflow_artifacts,
    update_workflow_metadata,
    update_workflow_node,
    update_workflow_questions,
    update_workflow_runtime,
    update_workflow_scoring,
)
from xrtm.product.workflow_nodes import list_builtin_workflow_nodes
from xrtm.product.workflows import (
    AGGREGATE_CANDIDATES_IMPLEMENTATION,
    NodeSpec,
    WorkflowBlueprint,
    WorkflowRegistry,
    aggregate_candidate_upstreams,
    validate_product_blueprint,
    validate_workflow_name,
)

MAX_SAFE_QUESTION_LIMIT = 25
WORKFLOW_KIND_OPTIONS = ("workflow", "demo", "benchmark", "competition")
RUNTIME_PROVIDER_OPTIONS = ("mock", "local-llm")
_DEFAULT_NODE_RUNTIMES = {
    "xrtm.product.workflow_nodes.provider_free_candidate_node": "provider-free-demo",
    "xrtm.product.workflow_nodes.candidate_forecast_node": "local-openai-compatible",
    "xrtm.product.workflow_nodes.time_series_baseline_node": "time-series-baseline",
}


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
        "authoring_catalog": workbench_authoring_catalog(registry),
        "selected_run_ref": selected_run_ref,
        "selected_run": selected_run_detail,
        "workflows": [workflow.__dict__ for workflow in workflow_summaries],
        "selected_workflow_name": selected_workflow_name,
        "selected_workflow": selected_workflow.to_json_dict() if selected_workflow is not None else None,
        "selected_workflow_source": _workflow_source(workflow_summaries, selected_workflow_name),
        "workflow_error": workflow_error,
        "validation": validation,
        "canvas": workflow_canvas(selected_workflow, selected_run_detail),
        "authoring": authoring_model(selected_workflow) if selected_workflow is not None else None,
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
    try:
        cloned = clone_workflow_blueprint(registry, source_name=source_name, target_name=target_name)
        return persist_authored_workflow(registry, cloned, overwrite=overwrite)
    except WorkflowAuthoringError as exc:
        raise WorkbenchInputError(str(exc)) from exc


def validate_workbench_workflow(registry: WorkflowRegistry, workflow_name: str | None) -> dict[str, Any]:
    """Validate one workflow for safe product execution and return a UI-friendly result."""

    if not workflow_name:
        return {"ok": False, "errors": ["Select a workflow first."]}
    report = launch_module.authored_workflow_validation_report(
        workflow_name=workflow_name,
        registry=registry,
    )
    return {
        "ok": report["ok"],
        "errors": list(report["errors"]),
        "workflow": report.get("workflow"),
    }


def preview_workbench_edit(
    registry: WorkflowRegistry,
    *,
    workflow_name: str,
    values: Mapping[str, str],
) -> WorkflowBlueprint:
    """Validate a safe-edit submission without persisting it."""

    workflow_name = _required_name(workflow_name, "workflow")
    _ensure_local_workflow(registry, workflow_name)
    blueprint = registry.load(workflow_name)
    return _updated_workbench_blueprint(blueprint, values)



def apply_workbench_edit(
    registry: WorkflowRegistry,
    *,
    workflow_name: str,
    values: Mapping[str, str],
) -> WorkflowBlueprint:
    """Apply the MVP safe-edit form to an existing local workflow."""

    updated = preview_workbench_edit(registry, workflow_name=workflow_name, values=values)
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
    baseline_run_dir: Path | None = None
    baseline_run_id: str | None = None
    if baseline_run_ref:
        baseline_run_dir = resolve_run_dir(runs_dir, baseline_run_ref)
        baseline_run_id = baseline_run_dir.name
    result = launch_module.run_authored_workflow(
        workflow_name=workflow_name,
        registry=registry,
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
        "supported_edits": [
            {
                "key": "questions_limit",
                "label": "Questions limit",
                "detail": f"Choose between 1 and {MAX_SAFE_QUESTION_LIMIT} questions for the cloned workflow.",
            },
            {
                "key": "artifacts_write_report",
                "label": "Write HTML report",
                "detail": "Toggle whether the candidate run writes report.html.",
            },
            {
                "key": "aggregate_weight_editors",
                "label": "Aggregate candidate weights",
                "detail": "Adjust supported upstream candidate weights only; no arbitrary node config editing is exposed.",
            },
        ],
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


def workbench_authoring_catalog(registry: WorkflowRegistry) -> dict[str, Any]:
    """Describe supported workflow creation and visual-authoring primitives."""

    service = WorkflowAuthoringService(registry)
    return {
        "creation_modes": [
            {
                "key": "scratch",
                "label": "Start from scratch",
                "detail": "Create a new safe provider-free starter workflow and open it in a draft session.",
            },
            {
                "key": "template",
                "label": "Start from template",
                "detail": "Use a curated starter template, then adjust the graph and core fields visually.",
            },
            {
                "key": "clone",
                "label": "Clone existing workflow",
                "detail": "Clone a built-in or local workflow into a local authoring draft before editing it.",
            },
        ],
        "templates": [template.__dict__ for template in service.list_starter_templates()],
        "node_catalog": _node_catalog(),
        "workflow_kind_options": list(WORKFLOW_KIND_OPTIONS),
        "runtime_provider_options": list(RUNTIME_PROVIDER_OPTIONS),
        "limits": {"max_questions": MAX_SAFE_QUESTION_LIMIT},
        "limitations": authoring_limitations(),
    }


def create_workbench_workflow(
    registry: WorkflowRegistry,
    *,
    creation_mode: str,
    draft_workflow_name: str,
    source_workflow_name: str | None = None,
    template_id: str | None = None,
    title: str | None = None,
    description: str | None = None,
) -> WorkflowBlueprint:
    """Create one authored workflow through the shared authoring service."""

    service = WorkflowAuthoringService(registry)
    draft_workflow_name = _required_name(draft_workflow_name, "draft workflow")
    title = _non_empty_or_none(title)
    description = _non_empty_or_none(description)
    if creation_mode == "scratch":
        return service.create_workflow_from_scratch(
            draft_workflow_name,
            title=title,
            description=description,
        )
    if creation_mode == "template":
        template_name = str(template_id or "").strip()
        if not template_name:
            raise WorkbenchInputError("template_id is required")
        return service.create_workflow_from_template(
            template_name,
            draft_workflow_name,
            title=title,
            description=description,
        )
    if creation_mode == "clone":
        source_name = _required_name(str(source_workflow_name or ""), "source workflow")
        return service.clone_workflow(
            source_name,
            target_name=draft_workflow_name,
            title=title,
            description=description,
        )
    raise WorkbenchInputError(f"unsupported creation mode: {creation_mode}")


def authoring_model(blueprint: WorkflowBlueprint) -> dict[str, Any]:
    """Return the supported core-field and graph authoring model for one workflow."""

    weights_by_node = {item["node"]: item["contributors"] for item in aggregate_weight_editors(blueprint)}
    return {
        "core_form": {
            "title": blueprint.title,
            "description": blueprint.description,
            "workflow_kind": blueprint.workflow_kind,
            "tags": ", ".join(blueprint.tags),
            "questions_limit": str(blueprint.questions.limit),
            "runtime_provider": blueprint.runtime.provider,
            "runtime_base_url": blueprint.runtime.base_url or "",
            "runtime_model": blueprint.runtime.model or "",
            "runtime_max_tokens": str(blueprint.runtime.max_tokens),
            "artifacts_write_report": "true" if blueprint.artifacts.write_report else "false",
            "artifacts_write_blueprint_copy": "true" if blueprint.artifacts.write_blueprint_copy else "false",
            "artifacts_write_graph_trace": "true" if blueprint.artifacts.write_graph_trace else "false",
            "scoring_write_eval": "true" if blueprint.scoring.write_eval else "false",
            "scoring_write_train_backtest": "true" if blueprint.scoring.write_train_backtest else "false",
        },
        "workflow_kind_options": list(WORKFLOW_KIND_OPTIONS),
        "runtime_provider_options": list(RUNTIME_PROVIDER_OPTIONS),
        "node_catalog": _node_catalog(),
        "limitations": authoring_limitations(),
        "graph": {
            "entry": blueprint.graph.entry,
            "targets": _graph_targets(blueprint),
            "nodes": [
                {
                    "name": name,
                    "kind": node.kind,
                    "implementation": node.implementation,
                    "runtime": node.runtime,
                    "description": node.description or "",
                    "optional": node.optional,
                    "is_entry": blueprint.graph.entry == name,
                    "aggregate_weights": weights_by_node.get(name, []),
                }
                for name, node in blueprint.graph.nodes.items()
            ],
            "edges": [{"from": edge.from_node, "to": edge.to_node} for edge in blueprint.graph.edges],
            "parallel_groups": {name: list(group.nodes) for name, group in blueprint.graph.parallel_groups.items()},
            "conditional_routes": {
                name: route.to_json_dict() for name, route in blueprint.graph.conditional_routes.items()
            },
            "gaps": [
                "Parallel-group and conditional-route editing stay read-only in this pass; inspect them visually and use basic node, edge, and entry edits for iteration.",
            ],
        },
    }


def apply_workbench_authoring_action(blueprint: WorkflowBlueprint, *, action: Mapping[str, Any]) -> WorkflowBlueprint:
    """Apply one supported WebUI authoring action to an in-memory workflow."""

    action_type = str(action.get("type") or "").strip()
    if not action_type:
        raise WorkbenchInputError("authoring action type is required")

    updated = blueprint
    if action_type == "update-core":
        metadata = _mapping_or_none(action.get("metadata"))
        if metadata is not None:
            updated = update_workflow_metadata(
                updated,
                title=_string_or_none_from_mapping(metadata, "title", required=True),
                description=_string_or_none_from_mapping(metadata, "description", required=True),
                workflow_kind=_string_or_none_from_mapping(metadata, "workflow_kind", required=True),
                tags=_tags_from_mapping(metadata, "tags"),
            )
        questions = _mapping_or_none(action.get("questions"))
        if questions is not None:
            updated = update_workflow_questions(updated, limit=_int_from_mapping(questions, "limit"))
        runtime = _mapping_or_none(action.get("runtime"))
        if runtime is not None:
            updated = update_workflow_runtime(
                updated,
                provider=_string_or_none_from_mapping(runtime, "provider", required=True),
                base_url=_optional_string_from_mapping(runtime, "base_url"),
                model=_optional_string_from_mapping(runtime, "model"),
                max_tokens=_int_from_mapping(runtime, "max_tokens"),
            )
        artifacts = _mapping_or_none(action.get("artifacts"))
        if artifacts is not None:
            updated = update_workflow_artifacts(
                updated,
                write_report=_bool_from_mapping(artifacts, "write_report"),
                write_blueprint_copy=_bool_from_mapping(artifacts, "write_blueprint_copy"),
                write_graph_trace=_bool_from_mapping(artifacts, "write_graph_trace"),
            )
        scoring = _mapping_or_none(action.get("scoring"))
        if scoring is not None:
            updated = update_workflow_scoring(
                updated,
                write_eval=_bool_from_mapping(scoring, "write_eval"),
                write_train_backtest=_bool_from_mapping(scoring, "write_train_backtest"),
            )
    elif action_type == "add-node":
        node_name = _required_name(str(action.get("node_name") or ""), "node")
        implementation = str(action.get("implementation") or "").strip()
        definition = _node_catalog_entry(implementation)
        updated = add_workflow_node(
            updated,
            node_name=node_name,
            node=NodeSpec(
                kind=definition["kind"],
                implementation=definition["implementation"],
                runtime=_optional_string_value(action.get("runtime")) or definition.get("default_runtime"),
                description=_non_empty_or_none(action.get("description")) or definition["summary"],
                optional=_bool_value(action.get("optional"), field="optional", default=False),
            ),
            incoming_from=_string_list(action.get("incoming_from")),
            outgoing_to=_string_list(action.get("outgoing_to")),
            set_as_entry=_bool_value(action.get("set_as_entry"), field="set_as_entry", default=False),
        )
    elif action_type == "update-node":
        node_name = _required_name(str(action.get("node_name") or ""), "node")
        kwargs: dict[str, Any] = {
            "description": _string_or_none(action.get("description")),
            "optional": _bool_value(action.get("optional"), field="optional", default=False),
            "runtime": _optional_string_value(action.get("runtime")),
        }
        raw_weights = _mapping_or_none(action.get("weights"))
        if raw_weights:
            contributors = {
                name: _parse_weight(value, node=node_name, contributor=str(name))
                for name, value in raw_weights.items()
            }
            kwargs["config"] = {"weights": _normalize_weights(contributors)}
        updated = update_workflow_node(updated, node_name, **kwargs)
    elif action_type == "remove-node":
        updated = remove_workflow_node(updated, _required_name(str(action.get("node_name") or ""), "node"))
    elif action_type == "add-edge":
        updated = add_workflow_edge(
            updated,
            from_node=_required_name(str(action.get("from_node") or ""), "edge source"),
            to_node=_required_name(str(action.get("to_node") or ""), "edge target"),
        )
    elif action_type == "remove-edge":
        updated = remove_workflow_edge(
            updated,
            from_node=_required_name(str(action.get("from_node") or ""), "edge source"),
            to_node=_required_name(str(action.get("to_node") or ""), "edge target"),
        )
    elif action_type == "set-entry":
        updated = set_workflow_entry(updated, _required_name(str(action.get("entry") or ""), "entry"))
    else:
        raise WorkbenchInputError(f"unsupported authoring action: {action_type}")

    try:
        validate_product_blueprint(updated)
    except ValueError as exc:
        raise WorkbenchInputError(str(exc)) from exc
    return updated


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


def _non_empty_or_none(value: Any) -> str | None:
    text = str(value).strip()
    return text or None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_string_value(value: Any) -> str | None:
    return _string_or_none(value)


def _mapping_or_none(value: Any) -> Mapping[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise WorkbenchInputError("authoring action payload must use JSON objects")
    return value


def _bool_value(raw: Any, *, field: str, default: bool) -> bool:
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    return _parse_bool(str(raw), field=field)


def _bool_from_mapping(mapping: Mapping[str, Any], key: str) -> bool:
    return _bool_value(mapping.get(key), field=key, default=False)


def _int_from_mapping(mapping: Mapping[str, Any], key: str) -> int:
    raw = mapping.get(key)
    if raw is None:
        raise WorkbenchInputError(f"{key} is required")
    if key == "limit":
        return _parse_question_limit(str(raw))
    try:
        value = int(str(raw).strip())
    except ValueError as exc:
        raise WorkbenchInputError(f"{key} must be an integer") from exc
    if value < 1:
        raise WorkbenchInputError(f"{key} must be >= 1")
    return value


def _string_or_none_from_mapping(mapping: Mapping[str, Any], key: str, *, required: bool = False) -> str | None:
    value = _string_or_none(mapping.get(key))
    if required and value is None:
        raise WorkbenchInputError(f"{key} is required")
    return value


def _optional_string_from_mapping(mapping: Mapping[str, Any], key: str) -> str | None:
    if key not in mapping:
        return None
    return _optional_string_value(mapping.get(key))


def _tags_from_mapping(mapping: Mapping[str, Any], key: str) -> tuple[str, ...]:
    value = mapping.get(key)
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(part.strip() for part in value.split(",") if part.strip())
    if isinstance(value, list):
        tags = []
        for item in value:
            text = str(item).strip()
            if text:
                tags.append(text)
        return tuple(tags)
    raise WorkbenchInputError(f"{key} must be a string or list")


def _string_list(value: Any) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    items = value if isinstance(value, list) else [value]
    names: list[str] = []
    for item in items:
        name = _required_name(str(item), "graph target")
        names.append(name)
    return tuple(names)


def _node_catalog() -> list[dict[str, Any]]:
    return [
        {
            "name": definition.name,
            "kind": definition.kind,
            "implementation": definition.implementation,
            "summary": definition.summary,
            "default_runtime": _DEFAULT_NODE_RUNTIMES.get(definition.implementation),
        }
        for definition in list_builtin_workflow_nodes()
    ]


def _node_catalog_entry(implementation: str) -> dict[str, Any]:
    for item in _node_catalog():
        if item["implementation"] == implementation:
            return item
    raise WorkbenchInputError(f"unsupported node implementation: {implementation}")


def _graph_targets(blueprint: WorkflowBlueprint) -> list[dict[str, Any]]:
    targets = [{"name": name, "kind": "node"} for name in blueprint.graph.nodes]
    targets.extend({"name": name, "kind": "parallel-group"} for name in blueprint.graph.parallel_groups)
    return targets


def authoring_limitations() -> list[str]:
    return [
        "Only shared safe-product workflow fields and graph mutations are exposed.",
        "Node implementations stay inside the built-in product workflow node catalog.",
        "Parallel-group and conditional-route editing remain read-only in this pass.",
        "API keys are not persisted as authored workflow fields from the WebUI.",
    ]


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



def _updated_workbench_blueprint(blueprint: WorkflowBlueprint, values: Mapping[str, str]) -> WorkflowBlueprint:
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
    updated = blueprint

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
        updated = update_workflow_node(updated, node_name, config={"weights": _normalize_weights(submitted)})
    updated = update_workflow_questions(updated, limit=limit)
    updated = update_workflow_artifacts(updated, write_report=write_report)
    return updated


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
    "RUNTIME_PROVIDER_OPTIONS",
    "WorkbenchInputError",
    "WorkbenchRunResult",
    "WORKFLOW_KIND_OPTIONS",
    "aggregate_weight_editors",
    "apply_workbench_authoring_action",
    "apply_workbench_edit",
    "authoring_limitations",
    "authoring_model",
    "preview_workbench_edit",
    "clone_workflow_for_edit",
    "create_workbench_workflow",
    "run_workbench_workflow",
    "safe_edit_model",
    "validate_workbench_workflow",
    "workbench_authoring_catalog",
    "workbench_snapshot",
    "workflow_canvas",
    "workflow_registry_for",
]
