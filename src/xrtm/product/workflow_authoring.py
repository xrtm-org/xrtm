"""Shared safe authoring services for product workflow creation and editing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, cast

from xrtm.product.workflow_runner import build_demo_workflow_blueprint
from xrtm.product.workflows import (
    ArtifactPolicy,
    EdgeSpec,
    GraphSpec,
    NodeSpec,
    ParallelGroupSpec,
    QuestionSourceSpec,
    RuntimeProfileSpec,
    ScoringPolicy,
    WorkflowBlueprint,
    WorkflowRegistry,
    validate_product_blueprint,
)

_UNSET = object()


class WorkflowAuthoringError(ValueError):
    """Raised when a shared workflow authoring operation is invalid or unsafe."""


@dataclass(frozen=True)
class WorkflowStarterTemplate:
    template_id: str
    title: str
    description: str
    workflow_kind: str = "workflow"
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class _WorkflowStarterTemplateDefinition:
    template: WorkflowStarterTemplate
    builder: Any


def list_workflow_starter_templates() -> tuple[WorkflowStarterTemplate, ...]:
    return tuple(definition.template for definition in _STARTER_TEMPLATES)


def build_workflow_from_scratch(
    name: str,
    *,
    title: str | None = None,
    description: str | None = None,
    workflow_kind: str = "workflow",
    question_limit: int = 2,
    max_tokens: int = 768,
) -> WorkflowBlueprint:
    blueprint = build_demo_workflow_blueprint(
        name=name,
        title=title or _default_title(name),
        description=description
        or "Minimal safe provider-free starter workflow created from scratch for guided authoring flows.",
        provider="mock",
        limit=question_limit,
        max_tokens=max_tokens,
        workflow_kind=workflow_kind,
    )
    payload = blueprint.to_json_dict()
    payload["tags"] = ["starter", "scratch", "provider-free"]
    return _blueprint_from_payload(payload)


def build_workflow_from_template(
    template_id: str,
    name: str,
    *,
    title: str | None = None,
    description: str | None = None,
) -> WorkflowBlueprint:
    definition = _template_definition(template_id)
    return _blueprint_from_payload(definition.builder(name=name, title=title, description=description).to_json_dict())


def clone_workflow_blueprint(
    registry: WorkflowRegistry,
    *,
    source_name: str,
    target_name: str,
    title: str | None = None,
    description: str | None = None,
) -> WorkflowBlueprint:
    try:
        source = registry.validate(source_name)
    except (FileNotFoundError, ValueError) as exc:
        raise WorkflowAuthoringError(str(exc)) from exc
    payload = source.to_json_dict()
    payload["name"] = target_name
    if title is not None:
        payload["title"] = title
    if description is not None:
        payload["description"] = description
    return _blueprint_from_payload(payload)


def persist_authored_workflow(
    registry: WorkflowRegistry,
    blueprint: WorkflowBlueprint,
    *,
    overwrite: bool = False,
    destination_root: Path | None = None,
) -> Path:
    validated = _blueprint_from_payload(blueprint.to_json_dict())
    try:
        return registry.save(validated, overwrite=overwrite, destination_root=destination_root)
    except FileExistsError as exc:
        raise WorkflowAuthoringError(str(exc)) from exc


def update_workflow_metadata(
    blueprint: WorkflowBlueprint,
    *,
    name: str | None | object = _UNSET,
    title: str | None | object = _UNSET,
    description: str | None | object = _UNSET,
    workflow_kind: str | None | object = _UNSET,
    tags: Iterable[str] | object = _UNSET,
) -> WorkflowBlueprint:
    payload = blueprint.to_json_dict()
    if name is not _UNSET:
        payload["name"] = name
    if title is not _UNSET:
        payload["title"] = title
    if description is not _UNSET:
        payload["description"] = description
    if workflow_kind is not _UNSET:
        payload["workflow_kind"] = workflow_kind
    if tags is not _UNSET:
        payload["tags"] = list(cast(Iterable[str], tags))
    return _blueprint_from_payload(payload)


def update_workflow_questions(
    blueprint: WorkflowBlueprint,
    *,
    source: str | None | object = _UNSET,
    corpus_id: str | None | object = _UNSET,
    limit: int | object = _UNSET,
) -> WorkflowBlueprint:
    payload = blueprint.to_json_dict()
    questions = payload["questions"]
    if source is not _UNSET:
        questions["source"] = source
    if corpus_id is not _UNSET:
        questions["corpus_id"] = corpus_id
    if limit is not _UNSET:
        questions["limit"] = limit
    return _blueprint_from_payload(payload)


def update_workflow_runtime(
    blueprint: WorkflowBlueprint,
    *,
    provider: str | None | object = _UNSET,
    base_url: str | None | object = _UNSET,
    model: str | None | object = _UNSET,
    api_key: str | None | object = _UNSET,
    max_tokens: int | object = _UNSET,
) -> WorkflowBlueprint:
    payload = blueprint.to_json_dict()
    runtime = payload["runtime"]
    if provider is not _UNSET:
        runtime["provider"] = provider
    if base_url is not _UNSET:
        runtime["base_url"] = base_url
    if model is not _UNSET:
        runtime["model"] = model
    if api_key is not _UNSET:
        runtime["api_key"] = api_key
    if max_tokens is not _UNSET:
        runtime["max_tokens"] = max_tokens
    return _blueprint_from_payload(payload)


def update_workflow_artifacts(
    blueprint: WorkflowBlueprint,
    *,
    write_report: bool | object = _UNSET,
    write_blueprint_copy: bool | object = _UNSET,
    write_graph_trace: bool | object = _UNSET,
) -> WorkflowBlueprint:
    payload = blueprint.to_json_dict()
    artifacts = payload["artifacts"]
    if write_report is not _UNSET:
        artifacts["write_report"] = write_report
    if write_blueprint_copy is not _UNSET:
        artifacts["write_blueprint_copy"] = write_blueprint_copy
    if write_graph_trace is not _UNSET:
        artifacts["write_graph_trace"] = write_graph_trace
    return _blueprint_from_payload(payload)


def update_workflow_scoring(
    blueprint: WorkflowBlueprint,
    *,
    write_eval: bool | object = _UNSET,
    write_train_backtest: bool | object = _UNSET,
) -> WorkflowBlueprint:
    payload = blueprint.to_json_dict()
    scoring = payload["scoring"]
    if write_eval is not _UNSET:
        scoring["write_eval"] = write_eval
    if write_train_backtest is not _UNSET:
        scoring["write_train_backtest"] = write_train_backtest
    return _blueprint_from_payload(payload)


def add_workflow_node(
    blueprint: WorkflowBlueprint,
    *,
    node_name: str,
    node: NodeSpec,
    incoming_from: Iterable[str] = (),
    outgoing_to: Iterable[str] = (),
    set_as_entry: bool = False,
) -> WorkflowBlueprint:
    payload = blueprint.to_json_dict()
    nodes = payload["graph"]["nodes"]
    if node_name in nodes:
        raise WorkflowAuthoringError(f"workflow node already exists: {node_name}")
    nodes[node_name] = node.to_json_dict()
    edges = payload["graph"].setdefault("edges", [])
    for source_name in incoming_from:
        edges.append({"from_node": source_name, "to_node": node_name})
    for target_name in outgoing_to:
        edges.append({"from_node": node_name, "to_node": target_name})
    if set_as_entry:
        payload["graph"]["entry"] = node_name
    return _blueprint_from_payload(payload)


def update_workflow_node(
    blueprint: WorkflowBlueprint,
    node_name: str,
    *,
    kind: str | object = _UNSET,
    implementation: str | None | object = _UNSET,
    runtime: str | None | object = _UNSET,
    description: str | None | object = _UNSET,
    optional: bool | object = _UNSET,
    config: Mapping[str, Any] | object = _UNSET,
    replace_config: bool = False,
) -> WorkflowBlueprint:
    payload = blueprint.to_json_dict()
    nodes = payload["graph"]["nodes"]
    if node_name not in nodes:
        raise WorkflowAuthoringError(f"workflow node does not exist: {node_name}")
    node_payload = dict(nodes[node_name])
    if kind is not _UNSET:
        node_payload["kind"] = kind
    if implementation is not _UNSET:
        node_payload["implementation"] = implementation
    if runtime is not _UNSET:
        node_payload["runtime"] = runtime
    if description is not _UNSET:
        node_payload["description"] = description
    if optional is not _UNSET:
        node_payload["optional"] = optional
    if config is not _UNSET:
        if not isinstance(config, Mapping):
            raise WorkflowAuthoringError("workflow node config must be an object")
        next_config = dict(config) if replace_config else {**dict(node_payload.get("config", {})), **dict(config)}
        node_payload["config"] = next_config
    nodes[node_name] = node_payload
    return _blueprint_from_payload(payload)


def remove_workflow_node(blueprint: WorkflowBlueprint, node_name: str) -> WorkflowBlueprint:
    if node_name == blueprint.graph.entry:
        raise WorkflowAuthoringError(f"set a different entry before removing workflow node: {node_name}")
    payload = blueprint.to_json_dict()
    nodes = payload["graph"]["nodes"]
    if node_name not in nodes:
        raise WorkflowAuthoringError(f"workflow node does not exist: {node_name}")
    del nodes[node_name]
    graph = payload["graph"]
    graph["edges"] = [
        edge for edge in graph.get("edges", []) if edge["from_node"] != node_name and edge["to_node"] != node_name
    ]
    for group_name, group in graph.get("parallel_groups", {}).items():
        remaining = [member for member in group.get("nodes", []) if member != node_name]
        if len(remaining) == len(group.get("nodes", [])):
            continue
        if not remaining:
            raise WorkflowAuthoringError(f"removing {node_name} would empty parallel group: {group_name}")
        group["nodes"] = remaining
    graph.get("conditional_routes", {}).pop(node_name, None)
    return _blueprint_from_payload(payload)


def add_workflow_edge(blueprint: WorkflowBlueprint, *, from_node: str, to_node: str) -> WorkflowBlueprint:
    payload = blueprint.to_json_dict()
    edges = payload["graph"].setdefault("edges", [])
    if any(edge["from_node"] == from_node and edge["to_node"] == to_node for edge in edges):
        raise WorkflowAuthoringError(f"workflow edge already exists: {from_node} -> {to_node}")
    edges.append({"from_node": from_node, "to_node": to_node})
    return _blueprint_from_payload(payload)


def remove_workflow_edge(blueprint: WorkflowBlueprint, *, from_node: str, to_node: str) -> WorkflowBlueprint:
    payload = blueprint.to_json_dict()
    edges = payload["graph"].get("edges", [])
    remaining = [edge for edge in edges if edge["from_node"] != from_node or edge["to_node"] != to_node]
    if len(remaining) == len(edges):
        raise WorkflowAuthoringError(f"workflow edge does not exist: {from_node} -> {to_node}")
    payload["graph"]["edges"] = remaining
    return _blueprint_from_payload(payload)


def set_workflow_entry(blueprint: WorkflowBlueprint, entry: str) -> WorkflowBlueprint:
    payload = blueprint.to_json_dict()
    payload["graph"]["entry"] = entry
    return _blueprint_from_payload(payload)


class WorkflowAuthoringService:
    """Shared backend authoring surface for CLI and WebUI workflow flows."""

    def __init__(self, registry: WorkflowRegistry) -> None:
        self.registry = registry

    def list_starter_templates(self) -> tuple[WorkflowStarterTemplate, ...]:
        return list_workflow_starter_templates()

    def create_workflow_from_scratch(self, name: str, **kwargs: Any) -> WorkflowBlueprint:
        return build_workflow_from_scratch(name, **kwargs)

    def create_workflow_from_template(self, template_id: str, name: str, **kwargs: Any) -> WorkflowBlueprint:
        return build_workflow_from_template(template_id, name, **kwargs)

    def clone_workflow(self, source_name: str, *, target_name: str, **kwargs: Any) -> WorkflowBlueprint:
        return clone_workflow_blueprint(self.registry, source_name=source_name, target_name=target_name, **kwargs)

    def persist_workflow(
        self,
        blueprint: WorkflowBlueprint,
        *,
        overwrite: bool = False,
        destination_root: Path | None = None,
    ) -> Path:
        return persist_authored_workflow(
            self.registry,
            blueprint,
            overwrite=overwrite,
            destination_root=destination_root,
        )

    def update_metadata(self, blueprint: WorkflowBlueprint, **kwargs: Any) -> WorkflowBlueprint:
        return update_workflow_metadata(blueprint, **kwargs)

    def update_questions(self, blueprint: WorkflowBlueprint, **kwargs: Any) -> WorkflowBlueprint:
        return update_workflow_questions(blueprint, **kwargs)

    def update_runtime(self, blueprint: WorkflowBlueprint, **kwargs: Any) -> WorkflowBlueprint:
        return update_workflow_runtime(blueprint, **kwargs)

    def update_artifacts(self, blueprint: WorkflowBlueprint, **kwargs: Any) -> WorkflowBlueprint:
        return update_workflow_artifacts(blueprint, **kwargs)

    def update_scoring(self, blueprint: WorkflowBlueprint, **kwargs: Any) -> WorkflowBlueprint:
        return update_workflow_scoring(blueprint, **kwargs)

    def add_node(self, blueprint: WorkflowBlueprint, **kwargs: Any) -> WorkflowBlueprint:
        return add_workflow_node(blueprint, **kwargs)

    def update_node(self, blueprint: WorkflowBlueprint, node_name: str, **kwargs: Any) -> WorkflowBlueprint:
        return update_workflow_node(blueprint, node_name, **kwargs)

    def remove_node(self, blueprint: WorkflowBlueprint, node_name: str) -> WorkflowBlueprint:
        return remove_workflow_node(blueprint, node_name)

    def add_edge(self, blueprint: WorkflowBlueprint, *, from_node: str, to_node: str) -> WorkflowBlueprint:
        return add_workflow_edge(blueprint, from_node=from_node, to_node=to_node)

    def remove_edge(self, blueprint: WorkflowBlueprint, *, from_node: str, to_node: str) -> WorkflowBlueprint:
        return remove_workflow_edge(blueprint, from_node=from_node, to_node=to_node)

    def set_entry(self, blueprint: WorkflowBlueprint, entry: str) -> WorkflowBlueprint:
        return set_workflow_entry(blueprint, entry)


def _blueprint_from_payload(payload: dict[str, Any]) -> WorkflowBlueprint:
    try:
        blueprint = WorkflowBlueprint.from_payload(payload)
        validate_product_blueprint(blueprint)
        return blueprint
    except ValueError as exc:
        raise WorkflowAuthoringError(str(exc)) from exc


def _default_title(name: str) -> str:
    parts = str(name).replace(".", " ").replace("-", " ").replace("_", " ").split()
    return " ".join(part.capitalize() for part in parts) or "Workflow"


def _build_provider_free_template(*, name: str, title: str | None, description: str | None) -> WorkflowBlueprint:
    blueprint = build_demo_workflow_blueprint(
        name=name,
        title=title or "Provider-free workflow starter",
        description=description
        or "Curated single-path starter blueprint mirroring the released provider-free compatibility runner.",
        provider="mock",
        limit=2,
        max_tokens=768,
        workflow_kind="workflow",
    )
    payload = blueprint.to_json_dict()
    payload["tags"] = ["starter", "template", "provider-free", "single-path"]
    return WorkflowBlueprint.from_payload(payload)


def _build_ensemble_template(*, name: str, title: str | None, description: str | None) -> WorkflowBlueprint:
    return WorkflowBlueprint(
        name=name,
        title=title or "Deterministic ensemble workflow starter",
        description=description
        or "Curated safe ensemble starter with a provider-free candidate, baseline branch, and aggregate weights.",
        workflow_kind="workflow",
        questions=QuestionSourceSpec(limit=2),
        runtime=RuntimeProfileSpec(provider="mock"),
        graph=GraphSpec(
            entry="load_questions",
            nodes={
                "load_questions": NodeSpec(
                    kind="tool",
                    implementation="xrtm.product.workflow_nodes.load_questions_node",
                    description="Load the released question slice for authoring previews.",
                ),
                "question_context": NodeSpec(
                    kind="tool",
                    implementation="xrtm.product.workflow_nodes.question_context_node",
                    description="Extract question context for downstream authoring-safe nodes.",
                ),
                "provider_free_control": NodeSpec(
                    kind="model",
                    implementation="xrtm.product.workflow_nodes.provider_free_candidate_node",
                    runtime="provider-free-demo",
                    description="Generate deterministic provider-free candidate forecasts.",
                ),
                "time_series_baseline": NodeSpec(
                    kind="model",
                    implementation="xrtm.product.workflow_nodes.time_series_baseline_node",
                    runtime="time-series-baseline",
                    description="Generate the released deterministic baseline forecasts.",
                ),
                "aggregate_candidates": NodeSpec(
                    kind="aggregator",
                    implementation="xrtm.product.workflow_nodes.aggregate_candidate_forecasts_node",
                    description="Combine safe upstream candidate outputs into official workflow records.",
                    config={
                        "strategy": "weighted-mean",
                        "weights": {
                            "provider_free_control": 0.65,
                            "time_series_baseline": 0.35,
                        },
                    },
                ),
                "score": NodeSpec(
                    kind="scorer",
                    implementation="xrtm.product.workflow_nodes.score_node",
                    description="Score the aggregated offline ensemble outputs.",
                ),
                "backtest": NodeSpec(
                    kind="model",
                    implementation="xrtm.product.workflow_nodes.backtest_node",
                    description="Write compact backtest evidence for the starter workflow.",
                ),
            },
            edges=(
                EdgeSpec(from_node="load_questions", to_node="question_context"),
                EdgeSpec(from_node="question_context", to_node="candidate_fanout"),
                EdgeSpec(from_node="candidate_fanout", to_node="aggregate_candidates"),
                EdgeSpec(from_node="aggregate_candidates", to_node="score"),
                EdgeSpec(from_node="score", to_node="backtest"),
            ),
            parallel_groups={
                "candidate_fanout": ParallelGroupSpec(nodes=("provider_free_control", "time_series_baseline"))
            },
        ),
        artifacts=ArtifactPolicy(write_report=False, write_blueprint_copy=True, write_graph_trace=True),
        scoring=ScoringPolicy(write_eval=True, write_train_backtest=True),
        tags=("starter", "template", "ensemble", "provider-free"),
    )


def _template_definition(template_id: str) -> _WorkflowStarterTemplateDefinition:
    for definition in _STARTER_TEMPLATES:
        if definition.template.template_id == template_id:
            return definition
    raise WorkflowAuthoringError(f"unknown workflow starter template: {template_id}")


_STARTER_TEMPLATES = (
    _WorkflowStarterTemplateDefinition(
        template=WorkflowStarterTemplate(
            template_id="provider-free-demo",
            title="Provider-free workflow starter",
            description="Single-path deterministic starter that mirrors the released provider-free compatibility runner.",
            tags=("starter", "template", "provider-free", "single-path"),
        ),
        builder=_build_provider_free_template,
    ),
    _WorkflowStarterTemplateDefinition(
        template=WorkflowStarterTemplate(
            template_id="ensemble-starter",
            title="Deterministic ensemble starter",
            description="Parallel provider-free and baseline branches with safe aggregate weights for authoring flows.",
            tags=("starter", "template", "ensemble", "provider-free"),
        ),
        builder=_build_ensemble_template,
    ),
)


__all__ = [
    "WorkflowAuthoringError",
    "WorkflowAuthoringService",
    "WorkflowStarterTemplate",
    "add_workflow_edge",
    "add_workflow_node",
    "build_workflow_from_scratch",
    "build_workflow_from_template",
    "clone_workflow_blueprint",
    "list_workflow_starter_templates",
    "persist_authored_workflow",
    "remove_workflow_edge",
    "remove_workflow_node",
    "set_workflow_entry",
    "update_workflow_artifacts",
    "update_workflow_metadata",
    "update_workflow_node",
    "update_workflow_questions",
    "update_workflow_runtime",
    "update_workflow_scoring",
]
