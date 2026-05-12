"""Workflow blueprints and registry for the XRTM product shell."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import Any

WORKFLOW_SCHEMA_VERSION = "xrtm.workflow.v1"
DEFAULT_LOCAL_WORKFLOWS_DIR = Path(".xrtm/workflows")
_WORKFLOW_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")
_SUPPORTED_PROVIDERS = {"mock", "local-llm"}
_SUPPORTED_QUESTION_SOURCES = {"real-binary-corpus"}
ALLOWED_PRODUCT_NODE_KINDS = frozenset({"tool", "model", "scorer", "aggregator", "router", "human-gate", "agent"})


def validate_workflow_name(name: str) -> None:
    if name in {"", ".", ".."}:
        raise ValueError("workflow name may not be empty, '.', or '..'")
    if not _WORKFLOW_NAME.fullmatch(name):
        raise ValueError("workflow name may only contain letters, numbers, dots, underscores, and dashes")


def _mapping(value: Any, *, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    return value


def _list_of_strings(value: Any, *, context: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{context} must be a list of non-empty strings")
    return list(value)


def _string(payload: dict[str, Any], key: str, *, context: str, default: str | None = None) -> str:
    value = payload.get(key, default)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{context}.{key} must be a non-empty string")
    return value


def _optional_string(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string when provided")
    return value


def _integer(payload: dict[str, Any], key: str, *, context: str, default: int) -> int:
    value = payload.get(key, default)
    if not isinstance(value, int) or value < 1:
        raise ValueError(f"{context}.{key} must be an integer >= 1")
    return value


def _boolean(payload: dict[str, Any], key: str, *, default: bool) -> bool:
    value = payload.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be true or false")
    return value


@dataclass(frozen=True)
class QuestionSourceSpec:
    source: str = "real-binary-corpus"
    corpus_id: str = "xrtm-real-binary-v1"
    limit: int = 2

    def __post_init__(self) -> None:
        if self.source not in _SUPPORTED_QUESTION_SOURCES:
            raise ValueError(f"unsupported question source: {self.source}")
        if self.limit < 1:
            raise ValueError("question source limit must be at least 1")

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "QuestionSourceSpec":
        data = _mapping(payload, context="questions")
        return cls(
            source=_string(data, "source", context="questions", default="real-binary-corpus"),
            corpus_id=_string(data, "corpus_id", context="questions", default="xrtm-real-binary-v1"),
            limit=_integer(data, "limit", context="questions", default=2),
        )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "corpus_id": self.corpus_id,
            "limit": self.limit,
        }


@dataclass(frozen=True)
class RuntimeProfileSpec:
    provider: str = "mock"
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    max_tokens: int = 768

    def __post_init__(self) -> None:
        if self.provider not in _SUPPORTED_PROVIDERS:
            raise ValueError(f"unsupported workflow runtime provider: {self.provider}")
        if self.max_tokens < 1:
            raise ValueError("runtime max_tokens must be at least 1")

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "RuntimeProfileSpec":
        data = _mapping(payload, context="runtime")
        return cls(
            provider=_string(data, "provider", context="runtime", default="mock"),
            base_url=_optional_string(data, "base_url"),
            model=_optional_string(data, "model"),
            api_key=_optional_string(data, "api_key"),
            max_tokens=_integer(data, "max_tokens", context="runtime", default=768),
        )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "api_key": self.api_key,
            "max_tokens": self.max_tokens,
        }


@dataclass(frozen=True)
class NodeSpec:
    kind: str
    implementation: str | None = None
    runtime: str | None = None
    description: str | None = None
    optional: bool = False
    config: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "NodeSpec":
        data = _mapping(payload, context="graph.nodes")
        kind = data.get("kind", data.get("type"))
        if not isinstance(kind, str) or not kind:
            raise ValueError("graph.nodes.*.kind must be a non-empty string")
        config = data.get("config", {})
        if not isinstance(config, dict):
            raise ValueError("graph.nodes.*.config must be an object when provided")
        return cls(
            kind=kind,
            implementation=_optional_string(data, "implementation"),
            runtime=_optional_string(data, "runtime"),
            description=_optional_string(data, "description"),
            optional=_boolean(data, "optional", default=False),
            config=dict(config),
        )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "implementation": self.implementation,
            "runtime": self.runtime,
            "description": self.description,
            "optional": self.optional,
            "config": self.config,
        }


@dataclass(frozen=True)
class EdgeSpec:
    from_node: str
    to_node: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "EdgeSpec":
        data = _mapping(payload, context="graph.edges")
        from_node = data.get("from_node", data.get("from"))
        to_node = data.get("to_node", data.get("to"))
        if not isinstance(from_node, str) or not from_node:
            raise ValueError("graph.edges.*.from_node must be a non-empty string")
        if not isinstance(to_node, str) or not to_node:
            raise ValueError("graph.edges.*.to_node must be a non-empty string")
        return cls(from_node=from_node, to_node=to_node)

    def to_json_dict(self) -> dict[str, Any]:
        return {"from_node": self.from_node, "to_node": self.to_node}


@dataclass(frozen=True)
class ParallelGroupSpec:
    nodes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.nodes:
            raise ValueError("parallel groups must include at least one node")

    @classmethod
    def from_payload(cls, payload: Any) -> "ParallelGroupSpec":
        if isinstance(payload, dict):
            nodes = payload.get("nodes")
        else:
            nodes = payload
        return cls(nodes=tuple(_list_of_strings(nodes, context="graph.parallel_groups.*.nodes")))

    def to_json_dict(self) -> dict[str, Any]:
        return {"nodes": list(self.nodes)}


@dataclass(frozen=True)
class ConditionalRouteSpec:
    route_field: str = "route"
    routes: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.route_field:
            raise ValueError("conditional route field may not be empty")
        if not self.routes:
            raise ValueError("conditional routes must define at least one branch")
        for key, value in self.routes.items():
            if not key or not value:
                raise ValueError("conditional route keys and targets must be non-empty strings")

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ConditionalRouteSpec":
        data = _mapping(payload, context="graph.conditional_routes")
        routes = _mapping(data.get("routes", {}), context="graph.conditional_routes.*.routes")
        normalized_routes: dict[str, str] = {}
        for key, value in routes.items():
            if not isinstance(key, str) or not key:
                raise ValueError("graph.conditional_routes.*.routes keys must be non-empty strings")
            if not isinstance(value, str) or not value:
                raise ValueError("graph.conditional_routes.*.routes values must be non-empty strings")
            normalized_routes[key] = value
        return cls(
            route_field=_string(data, "route_field", context="graph.conditional_routes", default="route"),
            routes=normalized_routes,
        )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "route_field": self.route_field,
            "routes": self.routes,
        }


@dataclass(frozen=True)
class GraphSpec:
    entry: str
    nodes: dict[str, NodeSpec]
    edges: tuple[EdgeSpec, ...] = ()
    parallel_groups: dict[str, ParallelGroupSpec] = field(default_factory=dict)
    conditional_routes: dict[str, ConditionalRouteSpec] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.nodes:
            raise ValueError("graph.nodes must define at least one node")
        available_targets = set(self.nodes) | set(self.parallel_groups)
        if self.entry not in available_targets:
            raise ValueError(f"graph.entry must reference a node or parallel group, got: {self.entry}")
        for group_name, group in self.parallel_groups.items():
            missing = [node for node in group.nodes if node not in self.nodes]
            if missing:
                raise ValueError(f"graph.parallel_groups.{group_name} references unknown nodes: {', '.join(missing)}")
        for edge in self.edges:
            if edge.from_node not in available_targets:
                raise ValueError(f"graph edge references unknown source: {edge.from_node}")
            if edge.to_node not in available_targets:
                raise ValueError(f"graph edge references unknown target: {edge.to_node}")
        for source_name, route in self.conditional_routes.items():
            if source_name not in available_targets:
                raise ValueError(f"graph conditional route references unknown source: {source_name}")
            missing_targets = [target for target in route.routes.values() if target not in available_targets]
            if missing_targets:
                raise ValueError(
                    f"graph.conditional_routes.{source_name} references unknown targets: {', '.join(missing_targets)}"
                )

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "GraphSpec":
        data = _mapping(payload, context="graph")
        raw_nodes = _mapping(data.get("nodes", {}), context="graph.nodes")
        nodes = {name: NodeSpec.from_payload(node_payload) for name, node_payload in raw_nodes.items()}
        raw_parallel = _mapping(data.get("parallel_groups", {}), context="graph.parallel_groups")
        parallel_groups = {
            name: ParallelGroupSpec.from_payload(group_payload) for name, group_payload in raw_parallel.items()
        }
        raw_conditional = _mapping(data.get("conditional_routes", {}), context="graph.conditional_routes")
        conditional_routes = {
            name: ConditionalRouteSpec.from_payload(route_payload) for name, route_payload in raw_conditional.items()
        }
        raw_edges = data.get("edges", [])
        if not isinstance(raw_edges, list):
            raise ValueError("graph.edges must be a list")
        edges = tuple(EdgeSpec.from_payload(item) for item in raw_edges)
        entry = data.get("entry")
        if entry is None:
            entry = next(iter(nodes))
        if not isinstance(entry, str) or not entry:
            raise ValueError("graph.entry must be a non-empty string")
        return cls(
            entry=entry,
            nodes=nodes,
            edges=edges,
            parallel_groups=parallel_groups,
            conditional_routes=conditional_routes,
        )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "entry": self.entry,
            "nodes": {name: node.to_json_dict() for name, node in self.nodes.items()},
            "edges": [edge.to_json_dict() for edge in self.edges],
            "parallel_groups": {name: group.to_json_dict() for name, group in self.parallel_groups.items()},
            "conditional_routes": {name: route.to_json_dict() for name, route in self.conditional_routes.items()},
        }


@dataclass(frozen=True)
class ArtifactPolicy:
    write_report: bool = True
    write_blueprint_copy: bool = True
    write_graph_trace: bool = True

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> "ArtifactPolicy":
        data = _mapping(payload or {}, context="artifacts")
        return cls(
            write_report=_boolean(data, "write_report", default=True),
            write_blueprint_copy=_boolean(data, "write_blueprint_copy", default=True),
            write_graph_trace=_boolean(data, "write_graph_trace", default=True),
        )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "write_report": self.write_report,
            "write_blueprint_copy": self.write_blueprint_copy,
            "write_graph_trace": self.write_graph_trace,
        }


@dataclass(frozen=True)
class ScoringPolicy:
    write_eval: bool = True
    write_train_backtest: bool = True

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> "ScoringPolicy":
        data = _mapping(payload or {}, context="scoring")
        return cls(
            write_eval=_boolean(data, "write_eval", default=True),
            write_train_backtest=_boolean(data, "write_train_backtest", default=True),
        )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "write_eval": self.write_eval,
            "write_train_backtest": self.write_train_backtest,
        }


@dataclass(frozen=True)
class WorkflowBlueprint:
    name: str
    title: str
    description: str
    workflow_kind: str
    questions: QuestionSourceSpec
    runtime: RuntimeProfileSpec
    graph: GraphSpec
    artifacts: ArtifactPolicy = field(default_factory=ArtifactPolicy)
    scoring: ScoringPolicy = field(default_factory=ScoringPolicy)
    schema_version: str = WORKFLOW_SCHEMA_VERSION
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        validate_workflow_name(self.name)
        if self.schema_version != WORKFLOW_SCHEMA_VERSION:
            raise ValueError(f"unsupported workflow schema version: {self.schema_version}")
        if not self.title:
            raise ValueError("workflow title may not be empty")
        if not self.description:
            raise ValueError("workflow description may not be empty")
        if not self.workflow_kind:
            raise ValueError("workflow_kind may not be empty")

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "WorkflowBlueprint":
        data = _mapping(payload, context="workflow")
        questions_payload = data.get("questions", data.get("question_source"))
        if questions_payload is None:
            raise ValueError("workflow.questions is required")
        return cls(
            schema_version=_string(data, "schema_version", context="workflow", default=WORKFLOW_SCHEMA_VERSION),
            name=_string(data, "name", context="workflow"),
            title=_string(data, "title", context="workflow"),
            description=_string(data, "description", context="workflow"),
            workflow_kind=_string(data, "workflow_kind", context="workflow", default="workflow"),
            questions=QuestionSourceSpec.from_payload(questions_payload),
            runtime=RuntimeProfileSpec.from_payload(data.get("runtime", {})),
            graph=GraphSpec.from_payload(data.get("graph", {})),
            artifacts=ArtifactPolicy.from_payload(data.get("artifacts")),
            scoring=ScoringPolicy.from_payload(data.get("scoring")),
            tags=tuple(_list_of_strings(data.get("tags", []), context="workflow.tags")) if "tags" in data else (),
        )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "workflow_kind": self.workflow_kind,
            "questions": self.questions.to_json_dict(),
            "runtime": self.runtime.to_json_dict(),
            "graph": self.graph.to_json_dict(),
            "artifacts": self.artifacts.to_json_dict(),
            "scoring": self.scoring.to_json_dict(),
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class WorkflowSummary:
    name: str
    title: str
    workflow_kind: str
    description: str
    source: str
    runtime_provider: str
    question_limit: int
    path: str


class WorkflowRegistry:
    """Load builtin and local workflow blueprints."""

    def __init__(self, *, local_roots: tuple[Path, ...] | None = None) -> None:
        self.local_roots = local_roots or (Path.cwd() / DEFAULT_LOCAL_WORKFLOWS_DIR,)

    def list_workflows(self) -> list[WorkflowSummary]:
        summaries: dict[str, WorkflowSummary] = {}
        for workflow in self._iter_builtin_workflows():
            summaries[workflow.name] = workflow
        for workflow in self._iter_local_workflows():
            summaries[workflow.name] = workflow
        return sorted(summaries.values(), key=lambda workflow: workflow.name)

    def load(self, name: str) -> WorkflowBlueprint:
        validate_workflow_name(name)
        local_match = self._load_local(name)
        if local_match is not None:
            return local_match
        builtin_match = self._load_builtin(name)
        if builtin_match is not None:
            return builtin_match
        raise FileNotFoundError(f"workflow does not exist: {name}")

    def validate(self, name: str) -> WorkflowBlueprint:
        blueprint = self.load(name)
        validate_product_blueprint(blueprint)
        return blueprint

    def clone(
        self,
        source_name: str,
        target_name: str,
        *,
        destination_root: Path | None = None,
        overwrite: bool = False,
    ) -> Path:
        blueprint = self.load(source_name)
        validate_workflow_name(target_name)
        destination = destination_root or self.local_roots[0]
        destination.mkdir(parents=True, exist_ok=True)
        path = destination / f"{target_name}.json"
        if path.exists() and not overwrite:
            raise FileExistsError(f"workflow already exists: {target_name}")
        payload = blueprint.to_json_dict()
        payload["name"] = target_name
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def explain(self, name: str) -> dict[str, Any]:
        blueprint = self.validate(name)
        return explain_blueprint(blueprint)

    def _iter_builtin_workflows(self) -> list[WorkflowSummary]:
        resource_root = files("xrtm.product.workflow_definitions")
        summaries: list[WorkflowSummary] = []
        for resource in sorted(resource_root.iterdir(), key=lambda item: item.name):
            if not resource.is_file() or not resource.name.endswith(".json"):
                continue
            blueprint = WorkflowBlueprint.from_payload(json.loads(resource.read_text(encoding="utf-8")))
            summaries.append(_summary_for_blueprint(blueprint, source="builtin", path=f"builtin:{resource.name}"))
        return summaries

    def _iter_local_workflows(self) -> list[WorkflowSummary]:
        summaries: list[WorkflowSummary] = []
        for root in self.local_roots:
            if not root.exists():
                continue
            for path in sorted(root.glob("*.json")):
                blueprint = WorkflowBlueprint.from_payload(json.loads(path.read_text(encoding="utf-8")))
                summaries.append(_summary_for_blueprint(blueprint, source="local", path=str(path)))
        return summaries

    def _load_builtin(self, name: str) -> WorkflowBlueprint | None:
        resource = files("xrtm.product.workflow_definitions") / f"{name}.json"
        if not resource.is_file():
            return None
        return WorkflowBlueprint.from_payload(json.loads(resource.read_text(encoding="utf-8")))

    def _load_local(self, name: str) -> WorkflowBlueprint | None:
        for root in self.local_roots:
            path = root / f"{name}.json"
            if path.exists():
                return WorkflowBlueprint.from_payload(json.loads(path.read_text(encoding="utf-8")))
        return None


def _summary_for_blueprint(blueprint: WorkflowBlueprint, *, source: str, path: str) -> WorkflowSummary:
    return WorkflowSummary(
        name=blueprint.name,
        title=blueprint.title,
        workflow_kind=blueprint.workflow_kind,
        description=blueprint.description,
        source=source,
        runtime_provider=blueprint.runtime.provider,
        question_limit=blueprint.questions.limit,
        path=path,
    )


def validate_product_blueprint(blueprint: WorkflowBlueprint) -> None:
    from xrtm.product.workflow_nodes import list_builtin_workflow_nodes

    allowed_implementations = {item.implementation for item in list_builtin_workflow_nodes()}
    allowed_implementations.add("xrtm.product.workflow_nodes.aggregate_node")
    errors: list[str] = []
    if blueprint.runtime.provider not in _SUPPORTED_PROVIDERS:
        errors.append(f"unsupported runtime provider for product workflows: {blueprint.runtime.provider}")
    if blueprint.questions.source not in _SUPPORTED_QUESTION_SOURCES:
        errors.append(f"unsupported question source for product workflows: {blueprint.questions.source}")
    for node_name, node in blueprint.graph.nodes.items():
        if node.kind not in ALLOWED_PRODUCT_NODE_KINDS:
            errors.append(f"{node_name}: unsupported node kind {node.kind!r}")
        if node.implementation and node.implementation not in allowed_implementations:
            errors.append(
                f"{node_name}: implementation {node.implementation!r} is outside the safe product node library"
            )
        if blueprint.workflow_kind == "benchmark" and node.implementation and "search" in node.implementation:
            errors.append(f"{node_name}: benchmark workflows may not include hidden network/search nodes")
    if errors:
        raise ValueError("workflow validation failed:\n- " + "\n- ".join(errors))


def explain_blueprint(blueprint: WorkflowBlueprint) -> dict[str, Any]:
    from xrtm.product.workflow_nodes import list_builtin_workflow_nodes

    catalog = {item.implementation: item for item in list_builtin_workflow_nodes()}
    runtime_requirements: list[str] = []
    uses_local_runtime = blueprint.runtime.provider == "local-llm" or any(
        node.runtime == "local-openai-compatible" or node.config.get("provider") == "local-llm"
        for node in blueprint.graph.nodes.values()
    )
    if uses_local_runtime:
        runtime_requirements.append(
            "Real-runtime mode needs a healthy local OpenAI-compatible endpoint and `--provider local-llm`."
        )
    if blueprint.runtime.provider == "mock":
        runtime_requirements.append("Provider-free mode works out of the box with no API keys or local model server.")
    if any(node.kind == "human-gate" for node in blueprint.graph.nodes.values()):
        runtime_requirements.append("Human-gate nodes require a human provider when the gated branch executes.")
    if blueprint.workflow_kind == "benchmark":
        runtime_requirements.append("Benchmark validation keeps Type 2 workflows on the safe product node library.")

    node_summaries = []
    for node_name, node in blueprint.graph.nodes.items():
        summary = catalog.get(node.implementation)
        node_summaries.append(
            {
                "name": node_name,
                "kind": node.kind,
                "runtime": node.runtime or blueprint.runtime.provider,
                "summary": summary.summary if summary is not None else (node.description or node.kind),
            }
        )

    expected_artifacts = [
        "run.json",
        "questions.jsonl",
        "forecasts.jsonl",
        "eval.json",
        "train.json",
        "provider.json",
        "events.jsonl",
        "run_summary.json",
        "blueprint.json",
        "graph_trace.jsonl",
    ]
    if blueprint.artifacts.write_report:
        expected_artifacts.append("report.html")

    return {
        "summary": (
            f"{blueprint.title} runs {len(blueprint.graph.nodes)} graph nodes over "
            f"{blueprint.questions.limit} questions and starts at {blueprint.graph.entry}."
        ),
        "runtime_requirements": runtime_requirements,
        "expected_artifacts": expected_artifacts,
        "parallel_groups": {name: list(group.nodes) for name, group in blueprint.graph.parallel_groups.items()},
        "conditional_routes": {
            name: route.to_json_dict() for name, route in blueprint.graph.conditional_routes.items()
        },
        "nodes": node_summaries,
    }


__all__ = [
    "DEFAULT_LOCAL_WORKFLOWS_DIR",
    "WORKFLOW_SCHEMA_VERSION",
    "ArtifactPolicy",
    "ConditionalRouteSpec",
    "EdgeSpec",
    "GraphSpec",
    "NodeSpec",
    "ParallelGroupSpec",
    "QuestionSourceSpec",
    "RuntimeProfileSpec",
    "ScoringPolicy",
    "WorkflowBlueprint",
    "WorkflowRegistry",
    "WorkflowSummary",
    "explain_blueprint",
    "validate_product_blueprint",
    "validate_workflow_name",
]
