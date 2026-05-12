# Python API Reference

This reference documents the stable Python entrypoints for working with XRTM programmatically.

The product architecture now has three practical layers:

| Layer | Import path | Use case |
| --- | --- | --- |
| **Product workflow API** | `xrtm.product` | Load shipped workflows, validate them, compile them, run them, and inspect workflow metadata or dry-run competition packs. |
| **Workflow graph layer** | `xrtm.product` | Build or inspect blueprint graphs with nodes, edges, parallel groups, and traces. |
| **Lower-level forecasting primitives** | `xrtm.forecast` | Work directly with `Orchestrator`, agents, model factories, and other framework components when you need custom code-level systems. |

Most users who want code-level control should start with `xrtm.product` and only drop to `xrtm.forecast` when the shipped workflow abstractions stop being enough.

## Stable product imports

```python
from xrtm.product import (
    CompetitionPackRegistry,
    GraphSpec,
    NodeSpec,
    EdgeSpec,
    ParallelGroupSpec,
    QuestionSourceSpec,
    RuntimeProfileSpec,
    WorkflowBlueprint,
    WorkflowGraphState,
    WorkflowRegistry,
    build_demo_workflow_blueprint,
    compile_workflow_blueprint,
    explain_blueprint,
    list_builtin_competition_packs,
    list_builtin_workflow_nodes,
    run_workflow_blueprint,
    validate_product_blueprint,
)
```

## Load and inspect a shipped workflow

```python
from xrtm.product import WorkflowRegistry, explain_blueprint

registry = WorkflowRegistry()
workflow = registry.load("flagship-benchmark")
details = explain_blueprint(workflow)

print(workflow.title)
print(details["summary"])
print(details["runtime_requirements"])
```

Use `WorkflowRegistry.load()` for a specific blueprint and `WorkflowRegistry.list_workflows()` when you want the shipped plus local inventory.

## Validate a safe product workflow

```python
from xrtm.product import WorkflowRegistry, validate_product_blueprint

workflow = WorkflowRegistry().load("demo-provider-free")
validate_product_blueprint(workflow)
```

`validate_product_blueprint()` enforces the safe product node library used by the Type 2 low-code customization path. It is the right validator for product-facing blueprints, not for arbitrary framework experiments.

## Run a workflow blueprint

```python
from pathlib import Path

from xrtm.product import WorkflowRegistry, run_workflow_blueprint

workflow = WorkflowRegistry().load("demo-provider-free")
result = run_workflow_blueprint(
    workflow,
    command="python-api-demo",
    runs_dir=Path("runs"),
)

print(result.run.run_dir)
print(result.eval_brier_score)
```

This writes the same canonical run artifacts as the CLI, including:

- `run.json`
- `questions.jsonl`
- `forecasts.jsonl`
- `eval.json`
- `train.json`
- `provider.json`
- `events.jsonl`
- `run_summary.json`
- `blueprint.json`
- `graph_trace.jsonl`
- `report.html` when report writing is enabled

## Build a custom workflow blueprint

```python
from xrtm.product import (
    EdgeSpec,
    GraphSpec,
    NodeSpec,
    QuestionSourceSpec,
    RuntimeProfileSpec,
    WorkflowBlueprint,
)

workflow = WorkflowBlueprint(
    name="custom-demo",
    title="Custom demo workflow",
    description="Minimal custom workflow built from product nodes.",
    workflow_kind="demo",
    questions=QuestionSourceSpec(limit=2),
    runtime=RuntimeProfileSpec(provider="mock"),
    graph=GraphSpec(
        entry="load_questions",
        nodes={
            "load_questions": NodeSpec(
                kind="tool",
                implementation="xrtm.product.workflow_nodes.load_questions_node",
            ),
            "forecast": NodeSpec(
                kind="model",
                implementation="xrtm.product.workflow_nodes.forecast_node",
            ),
            "score": NodeSpec(
                kind="scorer",
                implementation="xrtm.product.workflow_nodes.score_node",
            ),
        },
        edges=(
            EdgeSpec(from_node="load_questions", to_node="forecast"),
            EdgeSpec(from_node="forecast", to_node="score"),
        ),
    ),
)
```

This is the Python equivalent of the JSON blueprint format used by the workflow registry.

## Compile a workflow graph without running it

```python
from xrtm.product import WorkflowRegistry, compile_workflow_blueprint

workflow = WorkflowRegistry().load("flagship-benchmark")
compiled = compile_workflow_blueprint(workflow)

print(compiled.entry_node)
print(sorted(compiled.node_adapters))
```

Use this when you want to inspect the execution graph, attach custom node callables in tests, or reason about graph topology separately from full workflow execution.

## Inspect builtin workflow nodes

```python
from xrtm.product import list_builtin_workflow_nodes

for node in list_builtin_workflow_nodes():
    print(node.name, node.kind, node.implementation)
```

Builtin workflow nodes are heterogeneous on purpose: tools, model-backed nodes, deterministic non-LLM baselines, scorers, routers, aggregators, human gates, and competition-export nodes all share the same workflow graph surface.

## Dry-run competition packs

```python
from xrtm.product import CompetitionPackRegistry, list_builtin_competition_packs

packs = list_builtin_competition_packs()
pack = CompetitionPackRegistry().load("metaculus-cup")

print([item.name for item in packs])
print(pack.workflow_name)
```

Competition packs describe dry-run live-workflow exports. They are intentionally conservative:

- they produce redacted review bundles
- they do not attempt network submission
- they keep human-review expectations explicit

The current builtin pack is `metaculus-cup`, backed by the `metaculus-cup-dryrun` workflow.

## When to drop down to `xrtm.forecast`

Use `xrtm.forecast` directly when you need lower-level framework control, such as:

- custom `Orchestrator` graphs outside the product workflow contract
- custom agent classes or model/provider factories
- framework-level experimentation that intentionally bypasses the safe product node library

That lower layer remains valuable, but the product-first path is now `xrtm.product`.
