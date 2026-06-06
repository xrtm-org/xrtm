"""Product services shared by the XRTM CLI."""

from xrtm.product.pipeline import PipelineOptions, PipelineResult, run_pipeline
from xrtm.product.workflow_graph import WorkflowGraphState, compile_workflow_blueprint, graph_trace_rows
from xrtm.product.workflow_nodes import (
    BuiltinWorkflowNodeDefinition,
    list_builtin_workflow_nodes,
)
from xrtm.product.workflow_runner import (
    build_demo_workflow_blueprint,
    run_workflow_blueprint,
    workflow_to_pipeline_options,
)
from xrtm.forecast.core.schemas.workflow import (
    WORKFLOW_SCHEMA_VERSION,
    ArtifactPolicy,
    ConditionalRouteSpec,
    EdgeSpec,
    GraphSpec,
    NodeSpec,
    ParallelGroupSpec,
    QuestionSourceSpec,
    RuntimeProfileSpec,
    ScoringPolicy,
    WorkflowBlueprint,
    WorkflowSummary,
)
from xrtm.product.workflows import (
    DEFAULT_LOCAL_WORKFLOWS_DIR,
    WorkflowRegistry,
)

__all__ = [
    "DEFAULT_LOCAL_WORKFLOWS_DIR",
    "ArtifactPolicy",
    "BuiltinWorkflowNodeDefinition",
    "ConditionalRouteSpec",
    "EdgeSpec",
    "GraphSpec",
    "NodeSpec",
    "ParallelGroupSpec",
    "PipelineOptions",
    "PipelineResult",
    "QuestionSourceSpec",
    "RuntimeProfileSpec",
    "ScoringPolicy",
    "WORKFLOW_SCHEMA_VERSION",
    "WorkflowBlueprint",
    "WorkflowGraphState",
    "WorkflowRegistry",
    "WorkflowSummary",
    "build_demo_workflow_blueprint",
    "compile_workflow_blueprint",
    "graph_trace_rows",
    "list_builtin_workflow_nodes",
    "run_pipeline",
    "run_workflow_blueprint",
    "workflow_to_pipeline_options",
]
