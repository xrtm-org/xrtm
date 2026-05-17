from __future__ import annotations

import json
from pathlib import Path

import pytest

from xrtm.product import WorkflowAuthoringService, WorkflowRegistry, validate_product_blueprint
from xrtm.product.workflow_authoring import WorkflowAuthoringError
from xrtm.product.workflows import NodeSpec


def test_workflow_authoring_lists_templates_and_persists_workflows(tmp_path: Path) -> None:
    workflows_dir = tmp_path / "workflows"
    registry = WorkflowRegistry(local_roots=(workflows_dir,))
    service = WorkflowAuthoringService(registry)

    templates = service.list_starter_templates()
    assert [template.template_id for template in templates] == ["provider-free-demo", "ensemble-starter"]

    scratch = service.create_workflow_from_scratch("scratch-authoring")
    assert scratch.graph.entry == "load_questions"
    assert scratch.runtime.provider == "mock"
    scratch_path = service.persist_workflow(scratch)
    assert scratch_path == workflows_dir / "scratch-authoring.json"
    assert registry.validate("scratch-authoring").title == scratch.title

    template = service.create_workflow_from_template("ensemble-starter", "ensemble-authoring")
    assert "candidate_fanout" in template.graph.parallel_groups
    assert template.artifacts.write_report is False
    template_path = service.persist_workflow(template)
    saved = json.loads(template_path.read_text(encoding="utf-8"))
    assert saved["name"] == "ensemble-authoring"

    cloned = service.clone_workflow("demo-provider-free", target_name="cloned-demo")
    clone_path = service.persist_workflow(cloned)
    assert clone_path == workflows_dir / "cloned-demo.json"
    assert registry.validate("cloned-demo").name == "cloned-demo"


def test_workflow_authoring_updates_safe_workflow_fields(tmp_path: Path) -> None:
    service = WorkflowAuthoringService(WorkflowRegistry(local_roots=(tmp_path / "workflows",)))
    blueprint = service.create_workflow_from_scratch("editable-authoring")

    updated = service.update_metadata(
        blueprint,
        title="Editable Authoring Workflow",
        description="Customized workflow fields for authoring coverage.",
        workflow_kind="benchmark",
        tags=("authoring", "customized"),
    )
    updated = service.update_questions(updated, limit=4)
    updated = service.update_runtime(
        updated,
        provider="local-llm",
        base_url="http://127.0.0.1:11434/v1",
        model="phi-4-mini",
        api_key="placeholder",
        max_tokens=512,
    )
    updated = service.update_artifacts(updated, write_report=False, write_blueprint_copy=False)
    updated = service.update_scoring(updated, write_train_backtest=False)

    assert updated.title == "Editable Authoring Workflow"
    assert updated.questions.limit == 4
    assert updated.runtime.provider == "local-llm"
    assert updated.runtime.model == "phi-4-mini"
    assert updated.runtime.max_tokens == 512
    assert updated.artifacts.write_report is False
    assert updated.artifacts.write_blueprint_copy is False
    assert updated.scoring.write_train_backtest is False
    assert updated.tags == ("authoring", "customized")
    validate_product_blueprint(updated)


def test_workflow_authoring_applies_graph_mutations_without_breaking_validation(tmp_path: Path) -> None:
    service = WorkflowAuthoringService(WorkflowRegistry(local_roots=(tmp_path / "workflows",)))
    blueprint = service.create_workflow_from_scratch("graph-authoring")

    updated = service.add_node(
        blueprint,
        node_name="bootstrap",
        node=NodeSpec(
            kind="tool",
            implementation="xrtm.product.workflow_nodes.load_questions_node",
            description="Bootstrap the guided flow before the main load node.",
        ),
        outgoing_to=("load_questions",),
        set_as_entry=True,
    )
    assert updated.graph.entry == "bootstrap"

    updated = service.add_node(
        updated,
        node_name="question_context",
        node=NodeSpec(
            kind="tool",
            implementation="xrtm.product.workflow_nodes.question_context_node",
            description="Add explicit question context before forecasting.",
        ),
        incoming_from=("load_questions",),
        outgoing_to=("forecast",),
    )
    updated = service.remove_edge(updated, from_node="load_questions", to_node="forecast")
    updated = service.update_node(updated, "question_context", description="Inject question context for downstream nodes.")
    assert updated.graph.nodes["question_context"].description == "Inject question context for downstream nodes."

    updated = service.add_edge(updated, from_node="load_questions", to_node="forecast")
    updated = service.remove_node(updated, "question_context")

    assert "question_context" not in updated.graph.nodes
    validate_product_blueprint(updated)


def test_workflow_authoring_rejects_invalid_edits(tmp_path: Path) -> None:
    service = WorkflowAuthoringService(WorkflowRegistry(local_roots=(tmp_path / "workflows",)))
    blueprint = service.create_workflow_from_scratch("invalid-authoring")

    with pytest.raises(WorkflowAuthoringError, match="workflow node already exists"):
        service.add_node(
            blueprint,
            node_name="forecast",
            node=NodeSpec(kind="model", implementation="xrtm.product.workflow_nodes.forecast_node"),
        )

    with pytest.raises(WorkflowAuthoringError, match="unreachable nodes or groups"):
        service.add_node(
            blueprint,
            node_name="orphan",
            node=NodeSpec(kind="tool", implementation="xrtm.product.workflow_nodes.question_context_node"),
        )

    with pytest.raises(WorkflowAuthoringError, match="set a different entry"):
        service.remove_node(blueprint, "load_questions")

    with pytest.raises(WorkflowAuthoringError, match="outside the safe product node library"):
        service.update_node(blueprint, "forecast", implementation="xrtm.product.workflow_nodes.not_allowed")

    with pytest.raises(WorkflowAuthoringError, match="unreachable nodes or groups"):
        service.remove_edge(blueprint, from_node="forecast", to_node="score")

    ensemble = service.create_workflow_from_template("ensemble-starter", "ensemble-invalid")
    with pytest.raises(WorkflowAuthoringError, match="non-upstream candidate"):
        service.update_node(
            ensemble,
            "aggregate_candidates",
            config={"weights": {"missing_candidate": 1.0}},
            replace_config=True,
        )
