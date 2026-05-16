"""Product services shared by the XRTM CLI, TUI, and local WebUI."""

from xrtm.product.competition import (
    CompetitionPack,
    CompetitionPackRegistry,
    competition_submission_payload,
    list_builtin_competition_packs,
)
from xrtm.product.pipeline import PipelineOptions, PipelineResult, run_pipeline
from xrtm.product.workbench import (
    WorkbenchInputError,
    apply_workbench_edit,
    clone_workflow_for_edit,
    workbench_snapshot,
    workflow_canvas,
)
from xrtm.product.workflow_graph import WorkflowGraphState, compile_workflow_blueprint, graph_trace_rows
from xrtm.product.workflow_nodes import (
    BuiltinWorkflowNodeDefinition,
    competition_submission_node,
    list_builtin_workflow_nodes,
)
from xrtm.product.workflow_runner import (
    build_demo_workflow_blueprint,
    run_workflow_blueprint,
    workflow_to_pipeline_options,
)
from xrtm.product.workflows import (
    DEFAULT_LOCAL_WORKFLOWS_DIR,
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
    WorkflowRegistry,
    WorkflowSummary,
    explain_blueprint,
    validate_product_blueprint,
)

__all__ = [
    "DEFAULT_LOCAL_WORKFLOWS_DIR",
    "ArtifactPolicy",
    "BuiltinWorkflowNodeDefinition",
    "CompetitionPack",
    "CompetitionPackRegistry",
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
    "WorkbenchInputError",
    "apply_workbench_edit",
    "build_demo_workflow_blueprint",
    "clone_workflow_for_edit",
    "competition_submission_node",
    "competition_submission_payload",
    "compile_workflow_blueprint",
    "explain_blueprint",
    "graph_trace_rows",
    "list_builtin_competition_packs",
    "list_builtin_workflow_nodes",
    "run_pipeline",
    "run_workflow_blueprint",
    "validate_product_blueprint",
    "workbench_snapshot",
    "workflow_canvas",
    "workflow_to_pipeline_options",
]
