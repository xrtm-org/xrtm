from xrtm.product import (
    CompetitionPackRegistry,
    WorkflowAuthoringService,
    WorkflowRegistry,
    compile_workflow_blueprint,
    explain_blueprint,
    list_builtin_competition_packs,
    list_builtin_workflow_nodes,
    save_sandbox_profile,
    save_sandbox_workflow,
    validate_product_blueprint,
)


def test_product_api_exports_blueprint_graph_and_competition_surfaces() -> None:
    workflow = WorkflowRegistry().load("demo-provider-free")
    validate_product_blueprint(workflow)
    explanation = explain_blueprint(workflow)
    compiled = compile_workflow_blueprint(workflow)
    packs = list_builtin_competition_packs()
    pack = CompetitionPackRegistry().load("metaculus-cup")
    node_names = {node.name for node in list_builtin_workflow_nodes()}
    authoring = WorkflowAuthoringService(WorkflowRegistry())
    templates = authoring.list_starter_templates()
    scratch = authoring.create_workflow_from_scratch("api-authoring-demo")

    assert compiled.entry_node == workflow.graph.entry
    assert "runtime_requirements" in explanation
    assert packs
    assert pack.workflow_name == "metaculus-cup-dryrun"
    assert "competition-submission" in node_names
    assert templates
    assert callable(save_sandbox_workflow)
    assert callable(save_sandbox_profile)
    validate_product_blueprint(scratch)
