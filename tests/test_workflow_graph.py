from __future__ import annotations

import asyncio

import pytest
from xrtm.forecast.kit.agents.base import Agent

from xrtm.product.workflow_graph import WorkflowGraphState, compile_workflow_blueprint, graph_trace_rows
from xrtm.product.workflows import (
    ConditionalRouteSpec,
    EdgeSpec,
    GraphSpec,
    NodeSpec,
    ParallelGroupSpec,
    QuestionSourceSpec,
    RuntimeProfileSpec,
    WorkflowBlueprint,
)


def _blueprint(*, graph: GraphSpec) -> WorkflowBlueprint:
    return WorkflowBlueprint(
        name="test-workflow",
        title="Test workflow",
        description="Workflow graph compiler test fixture.",
        workflow_kind="test",
        questions=QuestionSourceSpec(limit=1),
        runtime=RuntimeProfileSpec(provider="mock"),
        graph=graph,
    )


def test_graph_compiler_runs_sequential_nodes() -> None:
    blueprint = _blueprint(
        graph=GraphSpec(
            entry="load",
            nodes={
                "load": NodeSpec(kind="tool", implementation="tests.load"),
                "finish": NodeSpec(kind="tool", implementation="tests.finish"),
            },
            edges=(EdgeSpec(from_node="load", to_node="finish"),),
        )
    )

    def load(*, state: WorkflowGraphState) -> dict[str, int]:
        state.context["value"] = 1
        return {"value": 1}

    def finish(*, state: WorkflowGraphState, upstream: dict[str, object]) -> dict[str, int]:
        assert upstream["load"] == {"value": 1}
        return {"value": state.context["value"] + 1}

    compiled = compile_workflow_blueprint(
        blueprint,
        node_callables={"tests.load": load, "tests.finish": finish},
    )
    state = WorkflowGraphState(subject_id="sequence")

    state = asyncio.run(compiled.orchestrator.run(state, entry_node=compiled.entry_node))

    assert state.execution_path == ["load", "finish"]
    assert state.node_reports["finish"] == {"value": 2}


def test_graph_compiler_supports_agent_nodes() -> None:
    class IncrementAgent(Agent):
        async def run(self, input_data, **kwargs):
            assert kwargs["node_name"] == "agent"
            return {"value": input_data["value"] + 1}

    blueprint = _blueprint(
        graph=GraphSpec(
            entry="load",
            nodes={
                "load": NodeSpec(kind="tool", implementation="tests.load"),
                "agent": NodeSpec(kind="agent", implementation="tests.agent"),
            },
            edges=(EdgeSpec(from_node="load", to_node="agent"),),
        )
    )

    compiled = compile_workflow_blueprint(
        blueprint,
        node_callables={
            "tests.load": lambda *, state: {"value": 1},
            "tests.agent": IncrementAgent,
        },
    )
    state = WorkflowGraphState(subject_id="agent")

    state = asyncio.run(compiled.orchestrator.run(state, entry_node=compiled.entry_node))

    assert state.node_reports["agent"] == {"value": 2}


def test_graph_compiler_supports_conditional_routes() -> None:
    blueprint = _blueprint(
        graph=GraphSpec(
            entry="decide",
            nodes={
                "decide": NodeSpec(kind="router", implementation="tests.decide"),
                "left": NodeSpec(kind="tool", implementation="tests.left"),
                "right": NodeSpec(kind="tool", implementation="tests.right"),
            },
            conditional_routes={
                "decide": ConditionalRouteSpec(route_field="route", routes={"left": "left", "right": "right"})
            },
        )
    )

    compiled = compile_workflow_blueprint(
        blueprint,
        node_callables={
            "tests.decide": lambda *, state: {"route": "left"},
            "tests.left": lambda *, state: {"branch": "left"},
            "tests.right": lambda *, state: {"branch": "right"},
        },
    )
    state = WorkflowGraphState(subject_id="branch")

    state = asyncio.run(compiled.orchestrator.run(state, entry_node=compiled.entry_node))

    assert state.execution_path == ["decide", "left"]
    assert "right" not in state.node_reports


def test_graph_compiler_supports_parallel_groups_and_trace_rows() -> None:
    blueprint = _blueprint(
        graph=GraphSpec(
            entry="fanout",
            nodes={
                "left": NodeSpec(kind="tool", implementation="tests.left"),
                "right": NodeSpec(kind="tool", implementation="tests.right"),
                "aggregate": NodeSpec(
                    kind="aggregator",
                    implementation="tests.aggregate",
                    config={"value_field": "value"},
                ),
            },
            edges=(EdgeSpec(from_node="fanout", to_node="aggregate"),),
            parallel_groups={"fanout": ParallelGroupSpec(nodes=("left", "right"))},
        )
    )

    def aggregate(*, upstream: dict[str, object], config: dict[str, object]) -> dict[str, int]:
        total = int(upstream["left"]["value"]) + int(upstream["right"]["value"])
        assert config["value_field"] == "value"
        return {"value": total}

    compiled = compile_workflow_blueprint(
        blueprint,
        node_callables={
            "tests.left": lambda *, state: {"value": 2},
            "tests.right": lambda *, state: {"value": 3},
            "tests.aggregate": aggregate,
        },
    )
    state = WorkflowGraphState(subject_id="parallel")

    state = asyncio.run(compiled.orchestrator.run(state, entry_node=compiled.entry_node))

    assert state.node_reports["aggregate"] == {"value": 5}
    trace = graph_trace_rows(compiled, state)
    assert any(row["node"] == "left" for row in trace)
    assert any(row["node"] == "right" for row in trace)
    assert any(row["node"] == "fanout" and row["kind"] == "parallel-group" for row in trace)


def test_graph_compiler_records_failure_trace() -> None:
    blueprint = _blueprint(
        graph=GraphSpec(entry="boom", nodes={"boom": NodeSpec(kind="tool", implementation="tests.boom")})
    )
    compiled = compile_workflow_blueprint(blueprint, node_callables={"tests.boom": lambda *, state: (_ for _ in ()).throw(ValueError("boom"))})
    state = WorkflowGraphState(subject_id="failure")

    with pytest.raises(ValueError, match="boom"):
        asyncio.run(compiled.orchestrator.run(state, entry_node=compiled.entry_node))

    trace_rows = state.context["graph_trace_rows"]
    assert trace_rows[0]["node"] == "boom"
    assert trace_rows[0]["status"] == "failed"
    assert trace_rows[0]["error"] == "boom"
