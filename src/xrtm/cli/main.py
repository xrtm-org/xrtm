"""Top-level XRTM product command."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from shlex import quote as shell_quote
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from xrtm.cli.presenters import (
    canonical_artifact_inventory,
    pipeline_result_title,
    pipeline_success_details,
    print_available_corpora_table,
    print_benchmark_compare_report,
    print_benchmark_stress_report,
    print_local_llm_status,
    print_pipeline_result,
    print_post_run_summary,
    print_prepared_corpus_report,
    print_quickstart_summary,
    print_run_compare,
    print_runs_table,
    print_validation_report,
    profiles_dir_command_arg,
    runs_dir_command_arg,
)
from xrtm.product import (
    WorkflowAuthoringError,
    WorkflowAuthoringService,
    list_builtin_workflow_nodes,
    list_workflow_starter_templates,
)
from xrtm.product import launch as launch_module
from xrtm.product.artifacts import ArtifactStore
from xrtm.product.competition import CompetitionPackRegistry
from xrtm.product.doctor import run_doctor
from xrtm.product.history import (
    compare_runs,
    export_run,
    resolve_run_dir,
)
from xrtm.product.history import (
    list_runs as list_run_history,
)
from xrtm.product.history import (
    run_detail as history_run_detail,
)
from xrtm.product.monitoring import (
    list_monitors,
    load_monitor,
    run_monitor_daemon,
    run_monitor_once,
    set_monitor_status,
    start_monitor,
)
from xrtm.product.observability import MonitorThresholds
from xrtm.product.performance import PerformanceBudgetError, PerformanceOptions, run_performance_benchmark
from xrtm.product.pipeline import PipelineOptions, PipelineResult, run_pipeline
from xrtm.product.profiles import (
    DEFAULT_PROFILES_DIR,
    ProfileStore,
    WorkflowProfile,
    starter_profile,
)
from xrtm.product.providers import local_llm_status
from xrtm.product.reports import render_html_report
from xrtm.product.tui import render_tui_once, run_tui
from xrtm.product.validation import (
    BenchmarkArmOptions,
    BenchmarkCompareOptions,
    BenchmarkStressOptions,
    ValidationOptions,
    ValidationSafetyError,
    ValidationTierError,
    list_validation_corpora,
    prepare_validation_corpus,
    run_benchmark_compare,
    run_benchmark_stress_suite,
    run_validation,
)
from xrtm.product.web import create_web_server, web_snapshot
from xrtm.product.workbench import workbench_snapshot as workflow_workbench_snapshot
from xrtm.product.workflow_runner import run_workflow_blueprint
from xrtm.product.workflows import DEFAULT_LOCAL_WORKFLOWS_DIR, NodeSpec, WorkflowBlueprint, WorkflowRegistry
from xrtm.version import __version__

console = Console()
_WORKFLOW_PROVIDER_CHOICES = ("mock", "local-llm")
_WORKFLOW_KIND_CHOICES = ("workflow", "benchmark")
_WORKFLOW_TEMPLATES = list_workflow_starter_templates()
_WORKFLOW_TEMPLATE_CHOICES = tuple(template.template_id for template in _WORKFLOW_TEMPLATES)
_BUILTIN_WORKFLOW_NODES = {definition.name: definition for definition in list_builtin_workflow_nodes()}
_BUILTIN_WORKFLOW_NODE_CHOICES = tuple(_BUILTIN_WORKFLOW_NODES)


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """XRTM product cockpit for event forecasting."""


def _validation_options_from_args(
    *,
    corpus_id: str,
    command: str,
    split: str | None,
    provider: str,
    limit: int,
    iterations: int,
    runs_dir: Path,
    output_dir: Path,
    base_url: str | None,
    model: str | None,
    api_key: str | None,
    max_tokens: int,
    release_gate_mode: bool,
    allow_unsafe_local_llm: bool,
    no_artifacts: bool,
) -> ValidationOptions:
    return ValidationOptions(
        corpus_id=corpus_id,
        command=command,
        split=split,
        provider=provider,
        limit=limit,
        iterations=iterations,
        runs_dir=runs_dir,
        output_dir=output_dir,
        base_url=base_url,
        model=model,
        api_key=api_key,
        max_tokens=max_tokens,
        write_artifacts=not no_artifacts,
        release_gate_mode=release_gate_mode,
        allow_unsafe_local_llm=allow_unsafe_local_llm,
    )


def _run_validation_command(
    *,
    corpus_id: str,
    command: str,
    split: str | None,
    provider: str,
    limit: int,
    iterations: int,
    runs_dir: Path,
    output_dir: Path,
    base_url: str | None,
    model: str | None,
    api_key: str | None,
    max_tokens: int,
    release_gate_mode: bool,
    allow_unsafe_local_llm: bool,
    no_artifacts: bool,
    report_title: str,
) -> None:
    try:
        report = run_validation(
            _validation_options_from_args(
                corpus_id=corpus_id,
                command=command,
                split=split,
                provider=provider,
                limit=limit,
                iterations=iterations,
                runs_dir=runs_dir,
                output_dir=output_dir,
                base_url=base_url,
                model=model,
                api_key=api_key,
                max_tokens=max_tokens,
                release_gate_mode=release_gate_mode,
                allow_unsafe_local_llm=allow_unsafe_local_llm,
                no_artifacts=no_artifacts,
            )
        )
    except (ValidationTierError, ValidationSafetyError, ValueError, RuntimeError) as exc:
        raise click.ClickException(str(exc)) from exc

    print_validation_report(console, report, title=report_title)


def _list_registered_corpora(
    *,
    tier: str | None,
    release_gate_only: bool,
    title: str,
) -> None:
    from xrtm.data.corpora import CorpusTier

    tier_enum = CorpusTier(tier) if tier else None
    corpora = list_validation_corpora(tier=tier_enum, release_gate_only=release_gate_only)

    if not corpora:
        console.print("[yellow]No corpora found matching the filter criteria.[/yellow]")
        return

    print_available_corpora_table(console, corpora, title=title)


def _prepare_registered_corpus(
    *,
    corpus_id: str,
    cache_root: Path | None,
    refresh: bool,
    fixture_preview: bool,
    title: str,
) -> None:
    try:
        report = prepare_validation_corpus(
            corpus_id,
            cache_root=cache_root,
            refresh=refresh,
            use_hf_datasets=not fixture_preview,
        )
    except (ImportError, ValueError, RuntimeError) as exc:
        raise click.ClickException(str(exc)) from exc

    print_prepared_corpus_report(console, report, title=title)


def _profile_write_permission_message(profiles_dir: Path, exc: PermissionError) -> str:
    target = profiles_dir.resolve()
    return (
        f"Cannot write profiles under {target}: {exc}. "
        "Rerun from a writable workspace or pass --profiles-dir /writable/path."
    )


def _workflow_destination_root(workflows_dir: Path) -> Path:
    return workflows_dir if workflows_dir.is_absolute() else Path.cwd() / workflows_dir


def _workflow_registry(workflows_dir: Path | None = None) -> WorkflowRegistry:
    if workflows_dir is None:
        return WorkflowRegistry()
    root = workflows_dir if workflows_dir.is_absolute() else Path.cwd() / workflows_dir
    return WorkflowRegistry(local_roots=(root,))


def _workflow_authoring_service(workflows_dir: Path) -> WorkflowAuthoringService:
    return WorkflowAuthoringService(_workflow_registry(workflows_dir))


def _load_workflow(name: str, *, workflows_dir: Path | None = None) -> WorkflowBlueprint:
    try:
        return _workflow_registry(workflows_dir).load(name)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc


def _load_competition_pack(name: str):
    try:
        return CompetitionPackRegistry().load(name)
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc


def _execute_workflow(
    blueprint: WorkflowBlueprint,
    *,
    command: str,
    runs_dir: Path,
    user: str | None,
    limit: int | None = None,
    provider: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    max_tokens: int | None = None,
    write_report: bool | None = None,
) -> PipelineResult:
    try:
        return run_workflow_blueprint(
            blueprint,
            command=command,
            runs_dir=runs_dir,
            user=user,
            limit=limit,
            provider=provider,
            base_url=base_url,
            model=model,
            api_key=api_key,
            max_tokens=max_tokens,
            write_report=write_report,
        )
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


def _print_workflow_list() -> None:
    workflows = _workflow_registry().list_workflows()
    if not workflows:
        console.print("[yellow]No workflows found.[/yellow]")
        return
    table = Table(title="XRTM Workflows")
    table.add_column("Workflow", style="cyan")
    table.add_column("Kind", style="green")
    table.add_column("Source")
    table.add_column("Runtime")
    table.add_column("Questions", justify="right")
    for workflow in workflows:
        table.add_row(
            workflow.name,
            workflow.workflow_kind,
            workflow.source,
            workflow.runtime_provider,
            str(workflow.question_limit),
        )
    console.print(table)


def _print_workflow_show(blueprint: WorkflowBlueprint, *, source_path: str | None = None) -> None:
    summary = Table(title=f"Workflow: {blueprint.name}")
    summary.add_column("Field", style="cyan")
    summary.add_column("Value", style="green")
    summary.add_row("Title", blueprint.title)
    summary.add_row("Kind", blueprint.workflow_kind)
    summary.add_row("Description", blueprint.description)
    summary.add_row("Question source", blueprint.questions.source)
    summary.add_row("Corpus", blueprint.questions.corpus_id)
    summary.add_row("Default question limit", str(blueprint.questions.limit))
    summary.add_row("Runtime provider", blueprint.runtime.provider)
    summary.add_row("Default max tokens", str(blueprint.runtime.max_tokens))
    summary.add_row("Graph entry", blueprint.graph.entry)
    if source_path:
        summary.add_row("Source", source_path)
    console.print(summary)

    nodes = Table(title="Workflow graph nodes")
    nodes.add_column("Node", style="cyan")
    nodes.add_column("Kind", style="green")
    nodes.add_column("Runtime")
    nodes.add_column("Description")
    for name, node in blueprint.graph.nodes.items():
        nodes.add_row(name, node.kind, node.runtime or blueprint.runtime.provider, node.description or "")
    console.print(nodes)

    if blueprint.graph.edges:
        edges = Table(title="Workflow graph edges")
        edges.add_column("From", style="cyan")
        edges.add_column("To", style="green")
        for edge in blueprint.graph.edges:
            edges.add_row(edge.from_node, edge.to_node)
        console.print(edges)

    if blueprint.graph.parallel_groups:
        groups = Table(title="Parallel groups")
        groups.add_column("Group", style="cyan")
        groups.add_column("Members", style="green")
        for group_name, group in blueprint.graph.parallel_groups.items():
            groups.add_row(group_name, ", ".join(group.nodes))
        console.print(groups)


def _print_workflow_explain(name: str, *, workflows_dir: Path | None = None) -> None:
    try:
        explanation = launch_module.explain_registered_workflow(
            name,
            workflows_dir=workflows_dir or DEFAULT_LOCAL_WORKFLOWS_DIR,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    console.print(Panel(explanation["summary"], title=f"Workflow explanation: {name}", border_style="green"))
    console.print(Panel("\n".join(explanation["runtime_requirements"]), title="Runtime requirements", border_style="blue"))
    console.print(Panel("\n".join(explanation["expected_artifacts"]), title="Expected artifacts", border_style="magenta"))

    nodes = Table(title="Plain-language node roles")
    nodes.add_column("Node", style="cyan")
    nodes.add_column("Kind", style="green")
    nodes.add_column("Runtime")
    nodes.add_column("Role")
    for node in explanation["nodes"]:
        nodes.add_row(node["name"], node["kind"], node["runtime"], node["summary"])
    console.print(nodes)


def _workflow_json_object_callback(
    _: click.Context,
    param: click.Parameter,
    value: str | None,
) -> dict[str, Any] | None:
    if value is None:
        return None
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise click.BadParameter(f"{param.name} must be valid JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise click.BadParameter(f"{param.name} must decode to a JSON object")
    return payload


def _workflow_update_value(value: Any, *, clear: bool, label: str) -> tuple[bool, Any]:
    if value is not None and clear:
        raise click.ClickException(f"Cannot combine {label} with its clear flag.")
    if clear:
        return True, None
    if value is not None:
        return True, value
    return False, None


def _require_workflow_updates(updates: dict[str, Any], *, hint: str) -> None:
    if not updates:
        raise click.ClickException(f"No changes requested. {hint}")


def _persist_authored_workflow(
    service: WorkflowAuthoringService,
    blueprint: WorkflowBlueprint,
    *,
    workflows_dir: Path,
    overwrite: bool,
) -> Path:
    try:
        return service.persist_workflow(
            blueprint,
            overwrite=overwrite,
            destination_root=_workflow_destination_root(workflows_dir),
        )
    except WorkflowAuthoringError as exc:
        raise click.ClickException(str(exc)) from exc


def _workflow_dir_flag(workflows_dir: Path) -> str:
    return shell_quote(workflows_dir.as_posix())


def _print_workflow_authoring_success(
    *,
    action: str,
    name: str,
    path: Path,
    workflows_dir: Path,
    include_run: bool = True,
) -> None:
    workflows_flag = _workflow_dir_flag(workflows_dir)
    console.print(f"[green]Workflow {action}:[/green] {path}")
    console.print(f"[blue]Show:[/blue] xrtm workflow show {name} --workflows-dir {workflows_flag}")
    console.print(f"[blue]Explain:[/blue] xrtm workflow explain {name} --workflows-dir {workflows_flag}")
    console.print(f"[blue]Validate:[/blue] xrtm workflow validate {name} --workflows-dir {workflows_flag}")
    if include_run:
        console.print(f"[blue]Run:[/blue] xrtm workflow run {name} --workflows-dir {workflows_flag} --runs-dir runs")


def _load_workflow_for_authoring(name: str, *, workflows_dir: Path) -> WorkflowBlueprint:
    return _load_workflow(name, workflows_dir=workflows_dir)


def _builtin_node_definition(name: str):
    return _BUILTIN_WORKFLOW_NODES[name]


def _benchmark_arm_options(
    *,
    label: str,
    provider: str,
    base_url: str | None,
    model: str | None,
    api_key: str | None,
    max_tokens: int,
) -> BenchmarkArmOptions:
    return BenchmarkArmOptions(
        label=label,
        provider=provider,
        base_url=base_url,
        model=model,
        api_key=api_key,
        max_tokens=max_tokens,
    )


def _default_benchmark_arms(
    *,
    baseline_label: str,
    baseline_provider: str,
    baseline_base_url: str | None,
    baseline_model: str | None,
    baseline_api_key: str | None,
    baseline_max_tokens: int,
    candidate_label: str,
    candidate_provider: str,
    candidate_base_url: str | None,
    candidate_model: str | None,
    candidate_api_key: str | None,
    candidate_max_tokens: int,
) -> tuple[BenchmarkArmOptions, BenchmarkArmOptions]:
    return (
        _benchmark_arm_options(
            label=baseline_label,
            provider=baseline_provider,
            base_url=baseline_base_url,
            model=baseline_model,
            api_key=baseline_api_key,
            max_tokens=baseline_max_tokens,
        ),
        _benchmark_arm_options(
            label=candidate_label,
            provider=candidate_provider,
            base_url=candidate_base_url,
            model=candidate_model,
            api_key=candidate_api_key,
            max_tokens=candidate_max_tokens,
        ),
    )


def _show_local_llm_status(*, base_url: str | None, fail_on_unhealthy: bool) -> None:
    status = local_llm_status(base_url=base_url)
    print_local_llm_status(console, status)
    if fail_on_unhealthy and not status["healthy"]:
        error_msg = (
            f"{status['error'] or 'Endpoint health check failed'}\n\n"
            f"Troubleshooting steps:\n"
            f"1. Ensure your local LLM server is running (e.g., llama.cpp)\n"
            f"2. Verify the endpoint: curl {status['health_url']}\n"
            f"3. Check base URL: {status['base_url']}\n"
            f"4. Set correct URL: export XRTM_LOCAL_LLM_BASE_URL=http://localhost:YOUR_PORT/v1\n\n"
            f"For setup help, see: docs/getting-started.md"
        )
        raise click.ClickException(error_msg)


def _prompt_line(label: str, *, default: str | None = None) -> str | None:
    prompt = label
    if default:
        prompt = f"{prompt} [{default}]"
    click.echo(f"{prompt}: ", nl=False)
    line = click.get_text_stream("stdin").readline()
    if line == "":
        return default
    value = line.strip()
    if value:
        return value
    return default


def _playground_default_selector(*, registry: WorkflowRegistry) -> str:
    workflows = registry.list_workflows()
    if any(workflow.name == "demo-provider-free" for workflow in workflows):
        return "workflow:demo-provider-free"
    if workflows:
        return f"workflow:{workflows[0].name}"
    if _WORKFLOW_TEMPLATES:
        return f"template:{_WORKFLOW_TEMPLATES[0].template_id}"
    raise click.ClickException("no workflows or starter templates are available for xrtm playground")


def _print_playground_context_choices(*, registry: WorkflowRegistry) -> None:
    workflows = registry.list_workflows()
    workflow_table = Table(title="Workflow contexts")
    workflow_table.add_column("Selector", style="cyan")
    workflow_table.add_column("Runtime", style="green")
    workflow_table.add_column("Source")
    workflow_table.add_column("Title")
    for workflow in workflows:
        workflow_table.add_row(
            f"workflow:{workflow.name}",
            workflow.runtime_provider,
            workflow.source,
            workflow.title,
        )
    console.print(workflow_table)

    template_table = Table(title="Starter template contexts")
    template_table.add_column("Selector", style="cyan")
    template_table.add_column("Kind", style="green")
    template_table.add_column("Title")
    for template in _WORKFLOW_TEMPLATES:
        template_table.add_row(f"template:{template.template_id}", template.workflow_kind, template.title)
    console.print(template_table)


def _resolve_playground_context(
    *,
    workflow: str | None,
    template: str | None,
    workflows_dir: Path,
    registry: WorkflowRegistry,
) -> launch_module.SandboxContext:
    try:
        return launch_module.resolve_sandbox_context(
            workflow_name=workflow,
            template_id=template,
            workflows_dir=workflows_dir,
            registry=registry,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc


def _select_playground_context(
    *,
    workflow: str | None,
    template: str | None,
    workflows_dir: Path,
    registry: WorkflowRegistry,
) -> launch_module.SandboxContext:
    if workflow and template:
        raise click.ClickException("pass either --workflow or --template, not both")
    if workflow or template:
        return _resolve_playground_context(
            workflow=workflow,
            template=template,
            workflows_dir=workflows_dir,
            registry=registry,
        )

    _print_playground_context_choices(registry=registry)
    default_selector = _playground_default_selector(registry=registry)
    while True:
        selection = _prompt_line(
            "Choose a playground context as workflow:<name> or template:<id>",
            default=default_selector,
        )
        if not selection:
            selection = default_selector
        selector_type, separator, selector_name = selection.partition(":")
        selector_type = selector_type.strip().lower()
        selector_name = selector_name.strip()
        if not separator or not selector_name or selector_type not in {"workflow", "template"}:
            console.print("[yellow]Use workflow:<name> or template:<id>.[/yellow]")
            continue
        try:
            return _resolve_playground_context(
                workflow=selector_name if selector_type == "workflow" else None,
                template=selector_name if selector_type == "template" else None,
                workflows_dir=workflows_dir,
                registry=registry,
            )
        except click.ClickException as exc:
            console.print(f"[yellow]{exc.format_message()}[/yellow]")


def _prompt_playground_question(*, seed_question: str | None = None, required: bool) -> str | None:
    if seed_question is not None:
        return seed_question
    question = _prompt_line("Enter one exploratory playground question")
    if question:
        return question
    if required:
        raise click.ClickException("playground question is required; pass --question or enter one at the prompt")
    return None


def _playground_json(value: Any, *, limit: int = 1800) -> str:
    payload = json.dumps(value, indent=2, sort_keys=True)
    if len(payload) <= limit:
        return payload
    return f"{payload[: limit - 15].rstrip()}\n... [truncated]"


def _print_playground_session(session: launch_module.SandboxSessionResult, *, runs_dir: Path) -> None:
    console.print(
        Panel(
            "\n".join(
                [
                    session.labeling["display_label"],
                    *session.labeling["notes"],
                ]
            ),
            title="XRTM Playground",
            border_style="yellow",
        )
    )

    context_table = Table(title="Playground session")
    context_table.add_column("Field", style="cyan")
    context_table.add_column("Value", style="green")
    context_table.add_row("Context", f"{session.context.context_type}:{session.context.reference_name}")
    context_table.add_row("Workflow title", session.workflow.get("title", session.context.blueprint.title))
    context_table.add_row("Runtime provider", str(session.run.get("provider", session.context.blueprint.runtime.provider)))
    context_table.add_row("Run id", session.run_id)
    context_table.add_row("Run dir", str(session.run_dir))
    context_table.add_row("Status", str(session.run.get("status", "")))
    context_table.add_row("Questions", str(len(session.questions)))
    context_table.add_row("Duration (s)", f"{session.total_seconds:.3f}")
    token_counts = session.run_summary.get("token_counts", {})
    if token_counts:
        context_table.add_row("Total tokens", str(token_counts.get("total_tokens", 0)))
    console.print(context_table)

    question_panel = []
    for index, question in enumerate(session.questions, start=1):
        question_panel.append(f"{index}. {question.get('title') or question.get('description')}")
        description = question.get("description")
        if description and description != question.get("title"):
            question_panel.append(f"   prompt: {description}")
        if question.get("resolution_criteria"):
            question_panel.append(f"   resolution criteria: {question['resolution_criteria']}")
    console.print(Panel("\n".join(question_panel), title="Exploratory question", border_style="blue"))

    steps = Table(title="Step inspection")
    steps.add_column("#", style="cyan", justify="right")
    steps.add_column("Node", style="green")
    steps.add_column("Type")
    steps.add_column("Status")
    steps.add_column("Preview")
    steps.add_column("Artifacts")
    for step in session.inspection_steps:
        artifacts = ", ".join(artifact["name"] for artifact in step["artifacts"]) or "—"
        steps.add_row(
            str(step["order"]),
            f"{step['node_id']} ({step['label']})" if step["label"] != step["node_id"] else step["node_id"],
            str(step["node_type"]),
            str(step["status"]),
            str(step["output_preview"]),
            artifacts,
        )
    console.print(steps)

    for step in session.inspection_steps:
        detail_payload = {"output": step["output"]}
        if step["artifact_payloads"]:
            detail_payload["artifact_payloads"] = step["artifact_payloads"]
        if step["artifacts"]:
            detail_payload["artifacts"] = step["artifacts"]
        console.print(
            Panel(
                _playground_json(detail_payload),
                title=f"Step {step['order']}: {step['node_id']}",
                border_style="magenta",
            )
        )

    workflow_state = session.save_back["workflow"]
    profile_state = session.save_back["profile"]
    save_back_lines = [
        f"Workflow save-back: {workflow_state['status']} ({workflow_state['recommended_name']})",
        f"Profile save-back: {profile_state['status']}",
        "Explicit save-back actions stay outside this todo; this loop only reports readiness.",
    ]
    console.print(Panel("\n".join(save_back_lines), title="Explicit save-back readiness", border_style="green"))

    runs_dir_arg = runs_dir_command_arg(runs_dir)
    run_dir_arg = shell_quote(session.run_dir.as_posix())
    artifact_lines = [
        f"Read sandbox artifact: {session.run_dir / 'sandbox_session.json'}",
        f"Inspect later: xrtm artifacts inspect {run_dir_arg}",
        f"Show run later: xrtm runs show {session.run_id}{runs_dir_arg}",
    ]
    console.print(Panel("\n".join(artifact_lines), title="Inspectable artifacts", border_style="blue"))


@cli.command()
@click.option("--workflow", default=None, help="Seed the playground with an existing workflow name.")
@click.option("--template", type=click.Choice(_WORKFLOW_TEMPLATE_CHOICES), default=None, help="Seed the playground with a starter template id.")
@click.option("--question", default=None, help="Seed the first exploratory question.")
@click.option(
    "--workflows-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_LOCAL_WORKFLOWS_DIR,
    show_default=True,
)
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"), show_default=True)
def playground(workflow: str | None, template: str | None, question: str | None, workflows_dir: Path, runs_dir: Path) -> None:
    """Run the interactive exploratory sandbox loop for one custom question at a time."""

    registry = _workflow_registry(workflows_dir)
    active_context = _select_playground_context(
        workflow=workflow,
        template=template,
        workflows_dir=workflows_dir,
        registry=registry,
    )
    next_question = question
    require_question = True

    while True:
        question_text = _prompt_playground_question(seed_question=next_question, required=require_question)
        if question_text is None:
            console.print("[yellow]No exploratory question entered; leaving playground.[/yellow]")
            break
        try:
            session = launch_module.run_sandbox_session(
                context=active_context,
                runs_dir=runs_dir,
                question=question_text,
                registry=registry,
                workflows_dir=workflows_dir,
                command="xrtm playground",
            )
        except Exception as exc:
            raise click.ClickException(str(exc)) from exc

        _print_playground_session(session, runs_dir=runs_dir)
        next_question = None
        require_question = False

        action = (_prompt_line("Next action [r=rerun, c=change context, q=quit]", default="q") or "q").strip().lower()
        if action in {"q", "quit", "exit"}:
            return
        if action in {"c", "change", "context"}:
            active_context = _select_playground_context(
                workflow=None,
                template=None,
                workflows_dir=workflows_dir,
                registry=registry,
            )
            require_question = True
            continue
        if action in {"r", "rerun", "again"}:
            continue
        console.print("[yellow]Unknown action; leaving playground.[/yellow]")
        return


@cli.command()
def doctor() -> None:
    """Check default first-run readiness and package health."""

    if not run_doctor(console):
        raise click.exceptions.Exit(1)


@cli.command()
@click.option("--limit", type=int, default=2, show_default=True, help="Number of bundled questions to run in the guided local demo.")
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"), show_default=True)
@click.option("--user", default=None, help="User or analyst attribution for this run.")
def start(limit: int, runs_dir: Path, user: str | None) -> None:
    """Guided newcomer quickstart: readiness -> local demo -> next steps."""

    if not run_doctor(console, runs_dir=runs_dir, show_next_steps=False):
        raise click.exceptions.Exit(1)
    console.print(
        Panel(
            "\n".join(
                [
                    "Readiness checks passed.",
                    "Running the released install/demo workflow now.",
                    "This first run stays fully local and offline by default.",
                    "Use xrtm workflow list after this run to browse shipped workflows.",
                ]
            ),
            title="Guided quickstart",
            border_style="blue",
        )
    )
    result = _run_product_action(
        lambda: launch_module.run_start_quickstart(limit=limit, runs_dir=runs_dir, user=user)
    )
    print_pipeline_result(console, result, title="XRTM Quickstart")
    print_quickstart_summary(console, result, runs_dir=runs_dir)


@cli.command()
@click.option("--provider", type=click.Choice(["mock", "local-llm"]), default="mock", show_default=True)
@click.option("--limit", type=int, default=2, show_default=True, help="Number of real corpus questions to run.")
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"), show_default=True)
@click.option("--base-url", default=None, help="OpenAI-compatible local endpoint for --provider local-llm.")
@click.option("--model", default=None, help="Local model id served by the endpoint.")
@click.option("--api-key", default=None, help="API key for the local endpoint; defaults to test/env.")
@click.option("--max-tokens", type=int, default=768, show_default=True)
@click.option("--no-report", is_flag=True, help="Skip static report.html generation.")
@click.option("--user", default=None, help="User or analyst attribution for this run.")
def demo(
    provider: str,
    limit: int,
    runs_dir: Path,
    base_url: str | None,
    model: str | None,
    api_key: str | None,
    max_tokens: int,
    no_report: bool,
    user: str | None,
) -> None:
    """Run a bounded local product demo over the real binary corpus."""

    result = _run_product_action(
        lambda: launch_module.run_demo_workflow(
            provider=provider,
            limit=limit,
            runs_dir=runs_dir,
            base_url=base_url,
            model=model,
            api_key=api_key,
            max_tokens=max_tokens,
            write_report=not no_report,
            user=user,
            command="xrtm demo",
            name="demo-provider-free" if provider == "mock" else "demo-local-llm",
            title="XRTM Demo",
            description="Bounded product demo over the released real-binary corpus.",
        )
    )
    print_pipeline_result(console, result, title="XRTM Demo")
    print_post_run_summary(
        console,
        result,
        runs_dir=runs_dir,
        success_title="Run complete",
        success_label="xrtm demo completed",
        what_succeeded=pipeline_success_details(write_report=not no_report),
        write_report=not no_report,
    )


@cli.group("workflow")
def workflow_group() -> None:
    """Author, inspect, validate, explain, and run named workflow blueprints."""


@workflow_group.group("create")
def workflow_create_group() -> None:
    """Create local workflows without making raw JSON edits the primary path."""


@workflow_create_group.command("scratch")
@click.argument("name")
@click.option("--title", default=None, help="Optional display title for the authored workflow.")
@click.option("--description", default=None, help="Optional description for the authored workflow.")
@click.option(
    "--workflow-kind",
    type=click.Choice(_WORKFLOW_KIND_CHOICES),
    default="workflow",
    show_default=True,
    help="Workflow category to store in the safe shared schema.",
)
@click.option("--question-limit", type=int, default=2, show_default=True, help="Default question limit for authored runs.")
@click.option("--max-tokens", type=int, default=768, show_default=True, help="Default max token budget for authored runs.")
@click.option(
    "--workflows-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_LOCAL_WORKFLOWS_DIR,
    show_default=True,
)
@click.option("--overwrite", is_flag=True, help="Replace an existing local workflow with the same name.")
def workflow_create_scratch(
    name: str,
    title: str | None,
    description: str | None,
    workflow_kind: str,
    question_limit: int,
    max_tokens: int,
    workflows_dir: Path,
    overwrite: bool,
) -> None:
    """Create a provider-free starter workflow from scratch."""

    service = _workflow_authoring_service(workflows_dir)
    try:
        blueprint = service.create_workflow_from_scratch(
            name,
            title=title,
            description=description,
            workflow_kind=workflow_kind,
            question_limit=question_limit,
            max_tokens=max_tokens,
        )
    except WorkflowAuthoringError as exc:
        raise click.ClickException(str(exc)) from exc
    path = _persist_authored_workflow(service, blueprint, workflows_dir=workflows_dir, overwrite=overwrite)
    _print_workflow_authoring_success(action="created", name=blueprint.name, path=path, workflows_dir=workflows_dir)


@workflow_create_group.command("template")
@click.argument("template_id", type=click.Choice(_WORKFLOW_TEMPLATE_CHOICES))
@click.argument("name")
@click.option("--title", default=None, help="Optional display title override for the starter template.")
@click.option("--description", default=None, help="Optional description override for the starter template.")
@click.option(
    "--workflows-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_LOCAL_WORKFLOWS_DIR,
    show_default=True,
)
@click.option("--overwrite", is_flag=True, help="Replace an existing local workflow with the same name.")
def workflow_create_template(
    template_id: str,
    name: str,
    title: str | None,
    description: str | None,
    workflows_dir: Path,
    overwrite: bool,
) -> None:
    """Create a local workflow from a released safe starter template."""

    service = _workflow_authoring_service(workflows_dir)
    try:
        blueprint = service.create_workflow_from_template(
            template_id,
            name,
            title=title,
            description=description,
        )
    except WorkflowAuthoringError as exc:
        raise click.ClickException(str(exc)) from exc
    path = _persist_authored_workflow(service, blueprint, workflows_dir=workflows_dir, overwrite=overwrite)
    _print_workflow_authoring_success(action="created", name=blueprint.name, path=path, workflows_dir=workflows_dir)


def _workflow_clone_command(
    source_name: str,
    target_name: str,
    title: str | None,
    description: str | None,
    workflows_dir: Path,
    overwrite: bool,
) -> None:
    """Clone a workflow into a local editable blueprint."""

    service = _workflow_authoring_service(workflows_dir)
    try:
        blueprint = service.clone_workflow(
            source_name,
            target_name=target_name,
            title=title,
            description=description,
        )
    except WorkflowAuthoringError as exc:
        raise click.ClickException(str(exc)) from exc
    path = _persist_authored_workflow(service, blueprint, workflows_dir=workflows_dir, overwrite=overwrite)
    _print_workflow_authoring_success(action="cloned", name=target_name, path=path, workflows_dir=workflows_dir)


@workflow_group.command("clone")
@click.argument("source_name")
@click.argument("target_name")
@click.option("--title", default=None, help="Optional title override for the cloned workflow.")
@click.option("--description", default=None, help="Optional description override for the cloned workflow.")
@click.option(
    "--workflows-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_LOCAL_WORKFLOWS_DIR,
    show_default=True,
)
@click.option("--overwrite", is_flag=True, help="Replace an existing cloned workflow with the same name.")
def workflow_clone(
    source_name: str,
    target_name: str,
    title: str | None,
    description: str | None,
    workflows_dir: Path,
    overwrite: bool,
) -> None:
    """Clone a workflow into a local editable blueprint."""

    _workflow_clone_command(source_name, target_name, title, description, workflows_dir, overwrite)


@workflow_create_group.command("clone")
@click.argument("source_name")
@click.argument("target_name")
@click.option("--title", default=None, help="Optional title override for the cloned workflow.")
@click.option("--description", default=None, help="Optional description override for the cloned workflow.")
@click.option(
    "--workflows-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_LOCAL_WORKFLOWS_DIR,
    show_default=True,
)
@click.option("--overwrite", is_flag=True, help="Replace an existing cloned workflow with the same name.")
def workflow_create_clone(
    source_name: str,
    target_name: str,
    title: str | None,
    description: str | None,
    workflows_dir: Path,
    overwrite: bool,
) -> None:
    """Clone a workflow into a local editable blueprint."""

    _workflow_clone_command(source_name, target_name, title, description, workflows_dir, overwrite)


@workflow_group.group("edit")
def workflow_edit_group() -> None:
    """Safely edit workflow blueprints through the shared backend authoring layer."""


@workflow_edit_group.command("metadata")
@click.argument("name")
@click.option("--title", default=None, help="Update the workflow title.")
@click.option("--description", default=None, help="Update the workflow description.")
@click.option("--workflow-kind", type=click.Choice(_WORKFLOW_KIND_CHOICES), default=None, help="Update the workflow kind.")
@click.option("--tag", "tags", multiple=True, help="Replace workflow tags. Repeat to set multiple tags in order.")
@click.option("--clear-tags", is_flag=True, help="Remove all workflow tags.")
@click.option(
    "--workflows-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_LOCAL_WORKFLOWS_DIR,
    show_default=True,
)
def workflow_edit_metadata(
    name: str,
    title: str | None,
    description: str | None,
    workflow_kind: str | None,
    tags: tuple[str, ...],
    clear_tags: bool,
    workflows_dir: Path,
) -> None:
    """Edit top-level workflow metadata."""

    if tags and clear_tags:
        raise click.ClickException("Cannot combine --tag with --clear-tags.")
    updates: dict[str, Any] = {}
    if title is not None:
        updates["title"] = title
    if description is not None:
        updates["description"] = description
    if workflow_kind is not None:
        updates["workflow_kind"] = workflow_kind
    if clear_tags:
        updates["tags"] = ()
    elif tags:
        updates["tags"] = tags
    _require_workflow_updates(
        updates,
        hint="Pass one or more of --title, --description, --workflow-kind, --tag, or --clear-tags.",
    )

    service = _workflow_authoring_service(workflows_dir)
    blueprint = _load_workflow_for_authoring(name, workflows_dir=workflows_dir)
    try:
        updated = service.update_metadata(blueprint, **updates)
    except WorkflowAuthoringError as exc:
        raise click.ClickException(str(exc)) from exc
    path = _persist_authored_workflow(service, updated, workflows_dir=workflows_dir, overwrite=True)
    _print_workflow_authoring_success(action="updated", name=updated.name, path=path, workflows_dir=workflows_dir)


@workflow_edit_group.command("questions")
@click.argument("name")
@click.option("--source", type=click.Choice(("real-binary-corpus",)), default=None, help="Update the question source id.")
@click.option("--corpus-id", default=None, help="Update the released corpus identifier.")
@click.option("--limit", type=int, default=None, help="Update the default workflow question limit.")
@click.option(
    "--workflows-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_LOCAL_WORKFLOWS_DIR,
    show_default=True,
)
def workflow_edit_questions(
    name: str,
    source: str | None,
    corpus_id: str | None,
    limit: int | None,
    workflows_dir: Path,
) -> None:
    """Edit the safe released question-source settings."""

    updates: dict[str, Any] = {}
    if source is not None:
        updates["source"] = source
    if corpus_id is not None:
        updates["corpus_id"] = corpus_id
    if limit is not None:
        updates["limit"] = limit
    _require_workflow_updates(updates, hint="Pass one or more of --source, --corpus-id, or --limit.")

    service = _workflow_authoring_service(workflows_dir)
    blueprint = _load_workflow_for_authoring(name, workflows_dir=workflows_dir)
    try:
        updated = service.update_questions(blueprint, **updates)
    except WorkflowAuthoringError as exc:
        raise click.ClickException(str(exc)) from exc
    path = _persist_authored_workflow(service, updated, workflows_dir=workflows_dir, overwrite=True)
    _print_workflow_authoring_success(action="updated", name=updated.name, path=path, workflows_dir=workflows_dir)


@workflow_edit_group.command("runtime")
@click.argument("name")
@click.option("--provider", type=click.Choice(_WORKFLOW_PROVIDER_CHOICES), default=None, help="Update the workflow runtime provider.")
@click.option("--base-url", default=None, help="Set the workflow base URL override.")
@click.option("--clear-base-url", is_flag=True, help="Clear any workflow base URL override.")
@click.option("--model", default=None, help="Set the workflow model id.")
@click.option("--clear-model", is_flag=True, help="Clear any workflow model id.")
@click.option("--api-key", default=None, help="Set the workflow API key placeholder or env-backed literal.")
@click.option("--clear-api-key", is_flag=True, help="Clear any workflow API key literal.")
@click.option("--max-tokens", type=int, default=None, help="Update the workflow max token budget.")
@click.option(
    "--workflows-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_LOCAL_WORKFLOWS_DIR,
    show_default=True,
)
def workflow_edit_runtime(
    name: str,
    provider: str | None,
    base_url: str | None,
    clear_base_url: bool,
    model: str | None,
    clear_model: bool,
    api_key: str | None,
    clear_api_key: bool,
    max_tokens: int | None,
    workflows_dir: Path,
) -> None:
    """Edit the shared runtime profile used by a workflow."""

    updates: dict[str, Any] = {}
    if provider is not None:
        updates["provider"] = provider
    for label, value, clear in (
        ("--base-url", base_url, clear_base_url),
        ("--model", model, clear_model),
        ("--api-key", api_key, clear_api_key),
    ):
        requested, resolved = _workflow_update_value(value, clear=clear, label=label)
        if requested:
            updates[label.removeprefix("--").replace("-", "_")] = resolved
    if max_tokens is not None:
        updates["max_tokens"] = max_tokens
    _require_workflow_updates(
        updates,
        hint="Pass one or more of --provider, --base-url, --clear-base-url, --model, --clear-model, --api-key, --clear-api-key, or --max-tokens.",
    )

    service = _workflow_authoring_service(workflows_dir)
    blueprint = _load_workflow_for_authoring(name, workflows_dir=workflows_dir)
    try:
        updated = service.update_runtime(blueprint, **updates)
    except WorkflowAuthoringError as exc:
        raise click.ClickException(str(exc)) from exc
    path = _persist_authored_workflow(service, updated, workflows_dir=workflows_dir, overwrite=True)
    _print_workflow_authoring_success(action="updated", name=updated.name, path=path, workflows_dir=workflows_dir)


@workflow_edit_group.command("artifacts")
@click.argument("name")
@click.option("--write-report/--no-write-report", default=None, help="Enable or disable HTML report generation.")
@click.option(
    "--write-blueprint-copy/--no-write-blueprint-copy",
    default=None,
    help="Enable or disable blueprint.json artifact copies.",
)
@click.option(
    "--write-graph-trace/--no-write-graph-trace",
    default=None,
    help="Enable or disable graph_trace.jsonl artifact writes.",
)
@click.option(
    "--workflows-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_LOCAL_WORKFLOWS_DIR,
    show_default=True,
)
def workflow_edit_artifacts(
    name: str,
    write_report: bool | None,
    write_blueprint_copy: bool | None,
    write_graph_trace: bool | None,
    workflows_dir: Path,
) -> None:
    """Edit workflow artifact persistence flags."""

    updates = {
        key: value
        for key, value in {
            "write_report": write_report,
            "write_blueprint_copy": write_blueprint_copy,
            "write_graph_trace": write_graph_trace,
        }.items()
        if value is not None
    }
    _require_workflow_updates(
        updates,
        hint="Pass one or more of --write-report/--no-write-report, --write-blueprint-copy/--no-write-blueprint-copy, or --write-graph-trace/--no-write-graph-trace.",
    )

    service = _workflow_authoring_service(workflows_dir)
    blueprint = _load_workflow_for_authoring(name, workflows_dir=workflows_dir)
    try:
        updated = service.update_artifacts(blueprint, **updates)
    except WorkflowAuthoringError as exc:
        raise click.ClickException(str(exc)) from exc
    path = _persist_authored_workflow(service, updated, workflows_dir=workflows_dir, overwrite=True)
    _print_workflow_authoring_success(action="updated", name=updated.name, path=path, workflows_dir=workflows_dir)


@workflow_edit_group.command("scoring")
@click.argument("name")
@click.option("--write-eval/--no-write-eval", default=None, help="Enable or disable eval.json scoring output.")
@click.option(
    "--write-train-backtest/--no-write-train-backtest",
    default=None,
    help="Enable or disable train/backtest scoring output.",
)
@click.option(
    "--workflows-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_LOCAL_WORKFLOWS_DIR,
    show_default=True,
)
def workflow_edit_scoring(
    name: str,
    write_eval: bool | None,
    write_train_backtest: bool | None,
    workflows_dir: Path,
) -> None:
    """Edit workflow scoring and backtest artifact flags."""

    updates = {
        key: value
        for key, value in {
            "write_eval": write_eval,
            "write_train_backtest": write_train_backtest,
        }.items()
        if value is not None
    }
    _require_workflow_updates(
        updates,
        hint="Pass one or more of --write-eval/--no-write-eval or --write-train-backtest/--no-write-train-backtest.",
    )

    service = _workflow_authoring_service(workflows_dir)
    blueprint = _load_workflow_for_authoring(name, workflows_dir=workflows_dir)
    try:
        updated = service.update_scoring(blueprint, **updates)
    except WorkflowAuthoringError as exc:
        raise click.ClickException(str(exc)) from exc
    path = _persist_authored_workflow(service, updated, workflows_dir=workflows_dir, overwrite=True)
    _print_workflow_authoring_success(action="updated", name=updated.name, path=path, workflows_dir=workflows_dir)


@workflow_edit_group.group("node")
def workflow_edit_node_group() -> None:
    """Edit safe workflow graph nodes."""


@workflow_edit_node_group.command("add")
@click.argument("name")
@click.argument("node_name")
@click.option("--builtin", "builtin_name", type=click.Choice(_BUILTIN_WORKFLOW_NODE_CHOICES), required=True, help="Safe builtin node to add.")
@click.option("--from-node", "incoming_from", multiple=True, help="Add an incoming edge from this node or group. Repeatable.")
@click.option("--to-node", "outgoing_to", multiple=True, help="Add an outgoing edge to this node or group. Repeatable.")
@click.option("--description", default=None, help="Optional description override for the added node.")
@click.option("--runtime", default=None, help="Optional runtime override for the added node.")
@click.option("--optional/--required", default=None, help="Mark the added node optional or required.")
@click.option("--config-json", callback=_workflow_json_object_callback, default=None, help="JSON object to store in node config.")
@click.option("--entry", "set_as_entry", is_flag=True, help="Set the new node as the graph entry.")
@click.option(
    "--workflows-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_LOCAL_WORKFLOWS_DIR,
    show_default=True,
)
def workflow_edit_node_add(
    name: str,
    node_name: str,
    builtin_name: str,
    incoming_from: tuple[str, ...],
    outgoing_to: tuple[str, ...],
    description: str | None,
    runtime: str | None,
    optional: bool | None,
    config_json: dict[str, Any] | None,
    set_as_entry: bool,
    workflows_dir: Path,
) -> None:
    """Add a safe released node to a workflow graph."""

    definition = _builtin_node_definition(builtin_name)
    node = NodeSpec(
        kind=definition.kind,
        implementation=definition.implementation,
        runtime=runtime,
        description=description or definition.summary,
        optional=optional if optional is not None else False,
        config=config_json or {},
    )

    service = _workflow_authoring_service(workflows_dir)
    blueprint = _load_workflow_for_authoring(name, workflows_dir=workflows_dir)
    try:
        updated = service.add_node(
            blueprint,
            node_name=node_name,
            node=node,
            incoming_from=incoming_from,
            outgoing_to=outgoing_to,
            set_as_entry=set_as_entry,
        )
    except WorkflowAuthoringError as exc:
        raise click.ClickException(str(exc)) from exc
    path = _persist_authored_workflow(service, updated, workflows_dir=workflows_dir, overwrite=True)
    _print_workflow_authoring_success(action="updated", name=updated.name, path=path, workflows_dir=workflows_dir)


@workflow_edit_node_group.command("update")
@click.argument("name")
@click.argument("node_name")
@click.option("--builtin", "builtin_name", type=click.Choice(_BUILTIN_WORKFLOW_NODE_CHOICES), default=None, help="Swap to another safe builtin node definition.")
@click.option("--runtime", default=None, help="Set a runtime override for this node.")
@click.option("--clear-runtime", is_flag=True, help="Clear any node runtime override.")
@click.option("--description", default=None, help="Set the node description.")
@click.option("--clear-description", is_flag=True, help="Clear the node description.")
@click.option("--optional/--required", default=None, help="Mark the node optional or required.")
@click.option("--config-json", callback=_workflow_json_object_callback, default=None, help="JSON object to merge into node config.")
@click.option("--replace-config", is_flag=True, help="Replace the node config object instead of merging.")
@click.option(
    "--workflows-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_LOCAL_WORKFLOWS_DIR,
    show_default=True,
)
def workflow_edit_node_update(
    name: str,
    node_name: str,
    builtin_name: str | None,
    runtime: str | None,
    clear_runtime: bool,
    description: str | None,
    clear_description: bool,
    optional: bool | None,
    config_json: dict[str, Any] | None,
    replace_config: bool,
    workflows_dir: Path,
) -> None:
    """Update a safe workflow graph node."""

    if replace_config and config_json is None:
        raise click.ClickException("--replace-config requires --config-json.")
    updates: dict[str, Any] = {}
    if builtin_name is not None:
        definition = _builtin_node_definition(builtin_name)
        updates["kind"] = definition.kind
        updates["implementation"] = definition.implementation
    runtime_requested, runtime_value = _workflow_update_value(runtime, clear=clear_runtime, label="--runtime")
    if runtime_requested:
        updates["runtime"] = runtime_value
    description_requested, description_value = _workflow_update_value(
        description,
        clear=clear_description,
        label="--description",
    )
    if description_requested:
        updates["description"] = description_value
    if optional is not None:
        updates["optional"] = optional
    if config_json is not None:
        updates["config"] = config_json
        updates["replace_config"] = replace_config
    _require_workflow_updates(
        updates,
        hint="Pass one or more of --builtin, --runtime, --clear-runtime, --description, --clear-description, --optional/--required, or --config-json.",
    )

    service = _workflow_authoring_service(workflows_dir)
    blueprint = _load_workflow_for_authoring(name, workflows_dir=workflows_dir)
    try:
        updated = service.update_node(blueprint, node_name, **updates)
    except WorkflowAuthoringError as exc:
        raise click.ClickException(str(exc)) from exc
    path = _persist_authored_workflow(service, updated, workflows_dir=workflows_dir, overwrite=True)
    _print_workflow_authoring_success(action="updated", name=updated.name, path=path, workflows_dir=workflows_dir)


@workflow_edit_node_group.command("remove")
@click.argument("name")
@click.argument("node_name")
@click.option(
    "--workflows-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_LOCAL_WORKFLOWS_DIR,
    show_default=True,
)
def workflow_edit_node_remove(name: str, node_name: str, workflows_dir: Path) -> None:
    """Remove a workflow graph node."""

    service = _workflow_authoring_service(workflows_dir)
    blueprint = _load_workflow_for_authoring(name, workflows_dir=workflows_dir)
    try:
        updated = service.remove_node(blueprint, node_name)
    except WorkflowAuthoringError as exc:
        raise click.ClickException(str(exc)) from exc
    path = _persist_authored_workflow(service, updated, workflows_dir=workflows_dir, overwrite=True)
    _print_workflow_authoring_success(action="updated", name=updated.name, path=path, workflows_dir=workflows_dir)


@workflow_edit_group.group("edge")
def workflow_edit_edge_group() -> None:
    """Edit workflow graph edges."""


@workflow_edit_edge_group.command("add")
@click.argument("name")
@click.argument("from_node")
@click.argument("to_node")
@click.option(
    "--workflows-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_LOCAL_WORKFLOWS_DIR,
    show_default=True,
)
def workflow_edit_edge_add(name: str, from_node: str, to_node: str, workflows_dir: Path) -> None:
    """Add a graph edge between two existing nodes or groups."""

    service = _workflow_authoring_service(workflows_dir)
    blueprint = _load_workflow_for_authoring(name, workflows_dir=workflows_dir)
    try:
        updated = service.add_edge(blueprint, from_node=from_node, to_node=to_node)
    except WorkflowAuthoringError as exc:
        raise click.ClickException(str(exc)) from exc
    path = _persist_authored_workflow(service, updated, workflows_dir=workflows_dir, overwrite=True)
    _print_workflow_authoring_success(action="updated", name=updated.name, path=path, workflows_dir=workflows_dir)


@workflow_edit_edge_group.command("remove")
@click.argument("name")
@click.argument("from_node")
@click.argument("to_node")
@click.option(
    "--workflows-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_LOCAL_WORKFLOWS_DIR,
    show_default=True,
)
def workflow_edit_edge_remove(name: str, from_node: str, to_node: str, workflows_dir: Path) -> None:
    """Remove a graph edge between two existing nodes or groups."""

    service = _workflow_authoring_service(workflows_dir)
    blueprint = _load_workflow_for_authoring(name, workflows_dir=workflows_dir)
    try:
        updated = service.remove_edge(blueprint, from_node=from_node, to_node=to_node)
    except WorkflowAuthoringError as exc:
        raise click.ClickException(str(exc)) from exc
    path = _persist_authored_workflow(service, updated, workflows_dir=workflows_dir, overwrite=True)
    _print_workflow_authoring_success(action="updated", name=updated.name, path=path, workflows_dir=workflows_dir)


@workflow_edit_group.group("entry")
def workflow_edit_entry_group() -> None:
    """Edit the graph entry point."""


@workflow_edit_entry_group.command("set")
@click.argument("name")
@click.argument("entry")
@click.option(
    "--workflows-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_LOCAL_WORKFLOWS_DIR,
    show_default=True,
)
def workflow_edit_entry_set(name: str, entry: str, workflows_dir: Path) -> None:
    """Set the workflow graph entry node or group."""

    service = _workflow_authoring_service(workflows_dir)
    blueprint = _load_workflow_for_authoring(name, workflows_dir=workflows_dir)
    try:
        updated = service.set_entry(blueprint, entry)
    except WorkflowAuthoringError as exc:
        raise click.ClickException(str(exc)) from exc
    path = _persist_authored_workflow(service, updated, workflows_dir=workflows_dir, overwrite=True)
    _print_workflow_authoring_success(action="updated", name=updated.name, path=path, workflows_dir=workflows_dir)


@workflow_group.command("list")
@click.option(
    "--workflows-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_LOCAL_WORKFLOWS_DIR,
    show_default=True,
)
def workflow_list(workflows_dir: Path) -> None:
    """List shipped and local workflows."""

    workflows = _workflow_registry(workflows_dir).list_workflows()
    if not workflows:
        console.print("[yellow]No workflows found.[/yellow]")
        return
    table = Table(title="XRTM Workflows")
    table.add_column("Workflow", style="cyan")
    table.add_column("Kind", style="green")
    table.add_column("Source")
    table.add_column("Runtime")
    table.add_column("Questions", justify="right")
    for workflow in workflows:
        table.add_row(
            workflow.name,
            workflow.workflow_kind,
            workflow.source,
            workflow.runtime_provider,
            str(workflow.question_limit),
        )
    console.print(table)


@workflow_group.command("show")
@click.argument("name")
@click.option(
    "--workflows-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_LOCAL_WORKFLOWS_DIR,
    show_default=True,
)
def workflow_show(name: str, workflows_dir: Path) -> None:
    """Show one workflow blueprint in product terms."""

    blueprint = _load_workflow(name, workflows_dir=workflows_dir)
    summary = next((item for item in _workflow_registry(workflows_dir).list_workflows() if item.name == name), None)
    _print_workflow_show(blueprint, source_path=summary.path if summary is not None else None)


@workflow_group.command("validate")
@click.argument("name")
@click.option(
    "--workflows-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_LOCAL_WORKFLOWS_DIR,
    show_default=True,
)
def workflow_validate(name: str, workflows_dir: Path) -> None:
    """Validate one workflow blueprint."""

    try:
        blueprint = launch_module.validate_registered_workflow(name, workflows_dir=workflows_dir)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    console.print(f"[green]Workflow valid:[/green] {blueprint.name} ({blueprint.schema_version})")


@workflow_group.command("explain")
@click.argument("name")
@click.option(
    "--workflows-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_LOCAL_WORKFLOWS_DIR,
    show_default=True,
)
def workflow_explain(name: str, workflows_dir: Path) -> None:
    """Explain one workflow in plain product terms."""

    _print_workflow_explain(name, workflows_dir=workflows_dir)


@workflow_group.command("run")
@click.argument("name")
@click.option(
    "--workflows-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_LOCAL_WORKFLOWS_DIR,
    show_default=True,
)
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"), show_default=True)
@click.option("--limit", type=int, default=None, help="Override the workflow's default question limit.")
@click.option("--provider", type=click.Choice(["mock", "local-llm"]), default=None, help="Override the workflow runtime provider.")
@click.option("--base-url", default=None, help="Override the workflow's OpenAI-compatible endpoint URL.")
@click.option("--model", default=None, help="Override the workflow model id.")
@click.option("--api-key", default=None, help="Override the workflow API key.")
@click.option("--max-tokens", type=int, default=None, help="Override the workflow max token budget.")
@click.option("--no-report", is_flag=True, help="Skip static report.html generation.")
@click.option("--user", default=None, help="User or analyst attribution for this run.")
def workflow_run(
    name: str,
    workflows_dir: Path,
    runs_dir: Path,
    limit: int | None,
    provider: str | None,
    base_url: str | None,
    model: str | None,
    api_key: str | None,
    max_tokens: int | None,
    no_report: bool,
    user: str | None,
) -> None:
    """Run a named workflow blueprint."""

    blueprint = _load_workflow(name, workflows_dir=workflows_dir)
    result = _run_product_action(
        lambda: launch_module.run_registered_workflow(
            name,
            workflows_dir=workflows_dir,
            runs_dir=runs_dir,
            limit=limit,
            provider=provider,
            base_url=base_url,
            model=model,
            api_key=api_key,
            max_tokens=max_tokens,
            write_report=not no_report,
            user=user,
            command=f"xrtm workflow run {name}",
        )
    )
    print_pipeline_result(console, result, title=f"Workflow: {blueprint.title}")
    print_post_run_summary(
        console,
        result,
        runs_dir=runs_dir,
        success_title="Workflow run complete",
        success_label=f"xrtm workflow run {name} completed",
        what_succeeded=pipeline_success_details(write_report=not no_report),
        write_report=not no_report,
    )


@cli.group("competition")
def competition_group() -> None:
    """List and dry-run live competition packs."""


@competition_group.command("list")
def competition_list() -> None:
    """List builtin competition dry-run packs."""

    packs = CompetitionPackRegistry().list_packs()
    if not packs:
        console.print("[yellow]No competition packs found.[/yellow]")
        return
    table = Table(title="XRTM Competition Packs")
    table.add_column("Pack", style="cyan")
    table.add_column("Workflow", style="green")
    table.add_column("Mode")
    table.add_column("Artifact")
    for pack in packs:
        table.add_row(pack.name, pack.workflow_name, "dry-run" if pack.dry_run_only else "submit-ready", pack.submission_artifact)
    console.print(table)


@competition_group.command("dry-run")
@click.argument("name")
@click.option(
    "--workflows-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_LOCAL_WORKFLOWS_DIR,
    show_default=True,
)
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"), show_default=True)
@click.option("--limit", type=int, default=None, help="Override the workflow's default question limit.")
@click.option("--provider", type=click.Choice(["mock", "local-llm"]), default=None, help="Override the workflow runtime provider.")
@click.option("--base-url", default=None, help="Override the workflow's OpenAI-compatible endpoint URL.")
@click.option("--model", default=None, help="Override the workflow model id.")
@click.option("--api-key", default=None, help="Override the workflow API key.")
@click.option("--max-tokens", type=int, default=None, help="Override the workflow max token budget.")
@click.option("--no-report", is_flag=True, help="Skip static report.html generation.")
@click.option("--user", default=None, help="User or analyst attribution for this run.")
def competition_dry_run(
    name: str,
    workflows_dir: Path,
    runs_dir: Path,
    limit: int | None,
    provider: str | None,
    base_url: str | None,
    model: str | None,
    api_key: str | None,
    max_tokens: int | None,
    no_report: bool,
    user: str | None,
) -> None:
    """Run a competition workflow in dry-run mode and export a review bundle."""

    pack = _load_competition_pack(name)
    blueprint = _load_workflow(pack.workflow_name, workflows_dir=workflows_dir)
    result = _execute_workflow(
        blueprint,
        command=f"xrtm competition dry-run {name}",
        runs_dir=runs_dir,
        user=user,
        limit=limit,
        provider=provider,
        base_url=base_url,
        model=model,
        api_key=api_key,
        max_tokens=max_tokens,
        write_report=not no_report,
    )
    print_pipeline_result(console, result, title=f"Competition dry-run: {pack.title}")
    print_post_run_summary(
        console,
        result,
        runs_dir=runs_dir,
        success_title="Competition dry-run complete",
        success_label=f"xrtm competition dry-run {name} completed",
        what_succeeded=pipeline_success_details(write_report=not no_report),
        write_report=not no_report,
    )
    bundle_path = result.run.artifacts.get(pack.submission_artifact)
    lines = [
        f"Competition pack: {pack.title}",
        f"Workflow: {pack.workflow_name}",
        f"Dry-run bundle: {bundle_path or 'not written'}",
        "Review the bundle manually; no network submission was attempted.",
    ]
    console.print(Panel("\n".join(lines), title="Competition dry-run bundle", border_style="blue"))


@cli.group("profile")
def profile_group() -> None:
    """Create and reuse local workflow profiles."""


@profile_group.command("create")
@click.argument("name")
@click.option("--profiles-dir", type=click.Path(file_okay=False, path_type=Path), default=DEFAULT_PROFILES_DIR, show_default=True)
@click.option("--provider", type=click.Choice(["mock", "local-llm"]), default="mock", show_default=True)
@click.option("--limit", type=int, default=2, show_default=True, help="Number of real corpus questions to run.")
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"), show_default=True)
@click.option("--base-url", default=None, help="OpenAI-compatible local endpoint for --provider local-llm.")
@click.option("--model", default=None, help="Local model id served by the endpoint.")
@click.option("--max-tokens", type=int, default=768, show_default=True)
@click.option("--no-report", is_flag=True, help="Skip static report.html generation.")
@click.option("--overwrite", is_flag=True, help="Replace an existing profile with the same name.")
@click.option("--user", default=None, help="User or analyst attribution for this run.")
def profile_create(
    name: str,
    profiles_dir: Path,
    provider: str,
    limit: int,
    runs_dir: Path,
    base_url: str | None,
    model: str | None,
    max_tokens: int,
    no_report: bool,
    overwrite: bool,
    user: str | None,
) -> None:
    """Save a repeatable product workflow profile."""

    try:
        profile = WorkflowProfile(
            name=name,
            provider=provider,
            limit=limit,
            runs_dir=str(runs_dir),
            base_url=base_url,
            model=model,
            max_tokens=max_tokens,
            write_report=not no_report,
            user=user,
        )
        path = ProfileStore(profiles_dir).create(profile, overwrite=overwrite)
    except PermissionError as exc:
        raise click.ClickException(_profile_write_permission_message(profiles_dir, exc)) from exc
    except (FileExistsError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    profiles_dir_arg = profiles_dir_command_arg(profiles_dir)
    runs_dir_arg = runs_dir_command_arg(runs_dir)
    lines = [
        f"Profile written: {path}",
        f"Run it: xrtm run profile {name}{profiles_dir_arg}",
        f"Inspect it: xrtm profile show {name}{profiles_dir_arg}",
        f"Review runs in this workspace: xrtm runs list {runs_dir_arg}",
    ]
    console.print(Panel("\n".join(lines), title="Profile saved", border_style="green"))


@profile_group.command("starter")
@click.argument("name")
@click.option("--profiles-dir", type=click.Path(file_okay=False, path_type=Path), default=DEFAULT_PROFILES_DIR, show_default=True)
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"), show_default=True)
@click.option("--user", default=None, help="User or analyst attribution for this starter workflow.")
@click.option("--overwrite", is_flag=True, help="Replace an existing profile with the same name.")
def profile_starter(name: str, profiles_dir: Path, runs_dir: Path, user: str | None, overwrite: bool) -> None:
    """Scaffold the minimal reusable local profile suggested after xrtm start."""

    try:
        runs_dir.mkdir(parents=True, exist_ok=True)
        path = ProfileStore(profiles_dir).create(starter_profile(name, runs_dir=runs_dir, user=user), overwrite=overwrite)
    except PermissionError as exc:
        raise click.ClickException(_profile_write_permission_message(profiles_dir, exc)) from exc
    except (FileExistsError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    profiles_dir_arg = profiles_dir_command_arg(profiles_dir)
    runs_dir_arg = runs_dir_command_arg(runs_dir)
    lines = [
        f"Starter profile: {path}",
        f"Runs directory ready: {runs_dir}",
        f"Repeat this local workflow: xrtm run profile {name}{profiles_dir_arg}",
        f"Inspect the profile: xrtm profile show {name}{profiles_dir_arg}",
        f"Review future runs: xrtm runs list {runs_dir_arg}",
    ]
    console.print(Panel("\n".join(lines), title="Starter scaffold ready", border_style="green"))


@profile_group.command("list")
@click.option("--profiles-dir", type=click.Path(file_okay=False, path_type=Path), default=DEFAULT_PROFILES_DIR, show_default=True)
def profile_list(profiles_dir: Path) -> None:
    """List saved workflow profiles."""

    table = Table(title="XRTM Profiles")
    table.add_column("Name", style="cyan")
    table.add_column("Provider", style="green")
    table.add_column("Limit", justify="right")
    table.add_column("Runs dir")
    table.add_column("Model")
    for profile in ProfileStore(profiles_dir).list_profiles():
        table.add_row(profile.name, profile.provider, str(profile.limit), profile.runs_dir, profile.model or "")
    console.print(table)


@profile_group.command("show")
@click.argument("name")
@click.option("--profiles-dir", type=click.Path(file_okay=False, path_type=Path), default=DEFAULT_PROFILES_DIR, show_default=True)
def profile_show(name: str, profiles_dir: Path) -> None:
    """Show one workflow profile."""

    try:
        profile = ProfileStore(profiles_dir).load(name)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    table = Table(title=f"Profile {name}")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    for field, value in profile.to_json_dict().items():
        table.add_row(field, str(value))
    console.print(table)


@cli.group()
def run() -> None:
    """Run product workflows."""


@run.command("pipeline")
@click.option("--provider", type=click.Choice(["mock", "local-llm"]), default="mock", show_default=True)
@click.option("--limit", type=int, default=2, show_default=True, help="Number of real corpus questions to run.")
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"), show_default=True)
@click.option("--base-url", default=None, help="OpenAI-compatible local endpoint for --provider local-llm.")
@click.option("--model", default=None, help="Local model id served by the endpoint.")
@click.option("--api-key", default=None, help="API key for the local endpoint; defaults to test/env.")
@click.option("--max-tokens", type=int, default=768, show_default=True)
@click.option("--no-report", is_flag=True, help="Skip static report.html generation.")
@click.option("--user", default=None, help="User or analyst attribution for this run.")
def run_pipeline_command(
    provider: str,
    limit: int,
    runs_dir: Path,
    base_url: str | None,
    model: str | None,
    api_key: str | None,
    max_tokens: int,
    no_report: bool,
    user: str | None,
) -> None:
    """Run forecast -> eval -> train/backtest over the real corpus."""

    _run_pipeline_command(
        PipelineOptions(
            provider=provider,
            limit=limit,
            runs_dir=runs_dir,
            base_url=base_url,
            model=model,
            api_key=api_key,
            max_tokens=max_tokens,
            write_report=not no_report,
            command="xrtm run pipeline",
            user=user,
        )
    )


@run.command("profile")
@click.argument("name")
@click.option("--profiles-dir", type=click.Path(file_okay=False, path_type=Path), default=DEFAULT_PROFILES_DIR, show_default=True)
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=None, help="Override the profile runs directory.")
def run_profile_command(name: str, profiles_dir: Path, runs_dir: Path | None) -> None:
    """Run a saved workflow profile."""

    result = _run_product_action(lambda: launch_module.run_saved_profile(name, profiles_dir=profiles_dir, runs_dir=runs_dir))
    profile = ProfileStore(profiles_dir).load(name)
    options = profile.to_pipeline_options(runs_dir=runs_dir)
    print_pipeline_result(console, result, title=pipeline_result_title(options.command))
    print_post_run_summary(
        console,
        result,
        runs_dir=runs_dir or Path(profile.runs_dir),
        success_title="Run complete",
        success_label=f"{options.command} completed",
        what_succeeded=pipeline_success_details(write_report=profile.write_report),
        write_report=profile.write_report,
    )


@cli.group()
def artifacts() -> None:
    """Inspect product run artifacts."""


@artifacts.command("inspect")
@click.argument("run_dir", type=click.Path(exists=True, file_okay=False, path_type=Path), required=False)
@click.option(
    "--runs-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("runs"),
    show_default=True,
    help="Run history directory used with --latest.",
)
@click.option("--latest", "use_latest", is_flag=True, help="Inspect the newest canonical run under --runs-dir.")
def artifacts_inspect(run_dir: Path | None, runs_dir: Path, use_latest: bool) -> None:
    """Inspect a canonical run directory and its artifact inventory, or use --latest."""

    try:
        run_dir = _resolve_inspection_run_dir(run_dir=run_dir, runs_dir=runs_dir, use_latest=use_latest)
        run_payload = ArtifactStore.read_run(run_dir)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    table = Table(title=f"Run {run_payload.get('run_id', run_dir.name)}")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    for field in ("status", "provider", "command", "created_at", "updated_at"):
        table.add_row(field, str(run_payload.get(field, "")))
    table.add_row("run_dir", str(run_dir))
    artifacts_payload = run_payload.get("artifacts", {})
    table.add_row("artifacts", str(len(artifacts_payload)))
    summary = run_payload.get("summary", {})
    if summary:
        table.add_row("forecasts", str(summary.get("forecast_count", "")))
        table.add_row("warnings", str(summary.get("warning_count", "")))
        table.add_row("errors", str(summary.get("error_count", "")))
    console.print(table)
    artifact_table = Table(title="Canonical artifact inventory")
    artifact_table.add_column("Artifact", style="cyan")
    artifact_table.add_column("Status")
    artifact_table.add_column("Location", style="green")
    for name, status, location in canonical_artifact_inventory(run_dir):
        artifact_table.add_row(name, status, location)
    console.print(artifact_table)
    runs_dir_arg = runs_dir_command_arg(run_dir.parent)
    run_dir_arg = shell_quote(run_dir.as_posix())
    next_lines = [
        f"Inspect summary: xrtm runs show {run_payload.get('run_id', run_dir.name)} {runs_dir_arg}",
        f"Open/regenerate report: xrtm report html {run_dir_arg}",
        f"Browse the same workspace in WebUI: xrtm web {runs_dir_arg}",
        f"Browse the same workspace in TUI: xrtm tui {runs_dir_arg}",
    ]
    console.print(Panel("\n".join(next_lines), title="Common next steps", border_style="blue"))


@artifacts.command("cleanup")
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"), show_default=True)
@click.option("--keep", type=int, default=50, show_default=True, help="Number of newest run directories to keep.")
@click.option("--dry-run/--delete", default=True, show_default=True, help="Show candidates without deleting by default.")
def artifacts_cleanup(runs_dir: Path, keep: int, dry_run: bool) -> None:
    """Apply the local run artifact retention policy."""

    try:
        candidates = ArtifactStore.cleanup_runs(runs_dir=runs_dir, keep=keep, dry_run=dry_run)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    action = "would remove" if dry_run else "removed"
    console.print(f"[green]Retention {action} {len(candidates)} run directorie(s).[/green]")
    for path in candidates:
        console.print(str(path))


@cli.group("runs")
def runs_group() -> None:
    """Browse, compare, and export product run history."""


@runs_group.command("list")
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"), show_default=True)
@click.option("--status", default=None, help="Filter by run status.")
@click.option("--provider", default=None, help="Filter by provider.")
def runs_list(runs_dir: Path, status: str | None, provider: str | None) -> None:
    """List run history."""

    print_runs_table(console, list_run_history(runs_dir, status=status, provider=provider), title="XRTM Runs")


@runs_group.command("search")
@click.argument("query")
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"), show_default=True)
@click.option("--status", default=None, help="Filter by run status.")
@click.option("--provider", default=None, help="Filter by provider.")
def runs_search(query: str, runs_dir: Path, status: str | None, provider: str | None) -> None:
    """Search run history by id, user, command, provider, or status."""

    print_runs_table(console, list_run_history(runs_dir, status=status, provider=provider, query=query), title="XRTM Run Search")


@runs_group.command("show")
@click.argument("run_ref")
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"), show_default=True)
def runs_show(run_ref: str, runs_dir: Path) -> None:
    """Show run details by run id or ``latest``."""

    try:
        run_dir = resolve_run_dir(runs_dir, run_ref)
        detail = history_run_detail(run_dir)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    run = detail["run"]
    summary = detail.get("summary", {})
    table = Table(title=f"Run {run.get('run_id', run_dir.name)}")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    rows = {
        "status": run.get("status"),
        "provider": run.get("provider"),
        "user": run.get("user"),
        "command": run.get("command"),
        "forecasts": summary.get("forecast_count"),
        "warnings": summary.get("warning_count"),
        "errors": summary.get("error_count"),
        "events": len(detail.get("events", [])),
        "run_dir": str(run_dir),
    }
    for field, value in rows.items():
        table.add_row(field, str(value))
    console.print(table)


@runs_group.command("compare")
@click.argument("left")
@click.argument("right")
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"), show_default=True)
def runs_compare(left: str, right: str, runs_dir: Path) -> None:
    """Compare two runs by id or ``latest``."""

    try:
        rows = compare_runs(resolve_run_dir(runs_dir, left), resolve_run_dir(runs_dir, right))
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    print_run_compare(console, rows)


@runs_group.command("export")
@click.argument("run_ref")
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"), show_default=True)
@click.option("--output", type=click.Path(dir_okay=False, path_type=Path), required=True, help="Destination file.")
@click.option(
    "--format",
    type=click.Choice(["json", "csv"], case_sensitive=False),
    default="json",
    show_default=True,
    help="Export format: JSON (full detail) or CSV (flattened forecasts).",
)
def runs_export(run_ref: str, runs_dir: Path, output: Path, format: str) -> None:
    """Export one run by id or ``latest`` as a portable bundle.

    JSON format includes complete run detail with nested structures.
    CSV format flattens forecasts into spreadsheet-friendly rows.
    """

    try:
        path = export_run(resolve_run_dir(runs_dir, run_ref), output, format=format.lower())
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    console.print(f"[green]Run exported as {format.upper()}:[/green] {path}")


@cli.group("providers")
def providers_group() -> None:
    """Inspect and test inference providers."""


@providers_group.command("doctor")
@click.option("--base-url", default=None, help="OpenAI-compatible local endpoint to check.")
def providers_doctor(base_url: str | None) -> None:
    """Check configured provider availability."""

    _show_local_llm_status(base_url=base_url, fail_on_unhealthy=False)


@cli.group("perf")
def perf_group() -> None:
    """Run deterministic performance and scale checks."""


@perf_group.command("run")
@click.option(
    "--scenario",
    type=click.Choice(["provider-free-smoke", "provider-free-scale", "local-llm-smoke"]),
    default="provider-free-smoke",
    show_default=True,
)
@click.option("--iterations", type=int, default=3, show_default=True)
@click.option("--limit", type=int, default=1, show_default=True)
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs-perf"), show_default=True)
@click.option("--output", type=click.Path(dir_okay=False, path_type=Path), default=Path("performance.json"), show_default=True)
@click.option("--base-url", default=None, help="OpenAI-compatible local endpoint for local-llm scenarios.")
@click.option("--model", default=None, help="Local model id served by the endpoint.")
@click.option("--api-key", default=None, help="API key for the local endpoint; defaults to test/env.")
@click.option("--max-tokens", type=int, default=768, show_default=True)
@click.option("--max-mean-seconds", type=float, default=None, help="Warn or fail when mean iteration duration exceeds this.")
@click.option("--max-p95-seconds", type=float, default=None, help="Warn or fail when p95 iteration duration exceeds this.")
@click.option("--fail-on-budget", is_flag=True, help="Exit non-zero when a configured budget is exceeded.")
def perf_run(
    scenario: str,
    iterations: int,
    limit: int,
    runs_dir: Path,
    output: Path,
    base_url: str | None,
    model: str | None,
    api_key: str | None,
    max_tokens: int,
    max_mean_seconds: float | None,
    max_p95_seconds: float | None,
    fail_on_budget: bool,
) -> None:
    """Run a bounded product performance benchmark."""

    try:
        report = run_performance_benchmark(
            PerformanceOptions(
                scenario=scenario,
                iterations=iterations,
                limit=limit,
                runs_dir=runs_dir,
                output=output,
                base_url=base_url,
                model=model,
                api_key=api_key,
                max_tokens=max_tokens,
                max_mean_seconds=max_mean_seconds,
                max_p95_seconds=max_p95_seconds,
                fail_on_budget=fail_on_budget,
            )
        )
    except (PerformanceBudgetError, ValueError, RuntimeError) as exc:
        raise click.ClickException(str(exc)) from exc
    summary = report["summary"]
    table = Table(title="XRTM Performance")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Scenario", report["scenario"])
    table.add_row("Iterations", str(report["iterations"]))
    table.add_row("Forecasts", str(summary["forecast_records"]))
    table.add_row("Mean seconds", f"{summary['mean_seconds']:.3f}")
    table.add_row("P95 seconds", f"{summary['p95_seconds']:.3f}")
    table.add_row("Forecasts/sec", f"{summary['forecasts_per_second']:.3f}")
    table.add_row("Budget", str(report["budget"]["status"]))
    table.add_row("Report", str(output))
    console.print(table)


@cli.group("validate")
def validate_group() -> None:
    """Large-scale validation with corpus registry integration."""


@validate_group.command("run")
@click.option("--corpus-id", default="xrtm-real-binary-v1", show_default=True, help="Corpus ID from registry.")
@click.option("--split", type=click.Choice(["full", "train", "eval", "held-out", "dev"]), default=None, help="Corpus split to use.")
@click.option("--provider", type=click.Choice(["mock", "local-llm"]), default="mock", show_default=True)
@click.option("--limit", type=int, default=10, show_default=True, help="Questions per iteration.")
@click.option("--iterations", type=int, default=1, show_default=True, help="Number of validation iterations.")
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs-validation"), show_default=True)
@click.option("--output-dir", type=click.Path(file_okay=False, path_type=Path), default=Path(".cache/validation"), show_default=True)
@click.option("--base-url", default=None, help="OpenAI-compatible local endpoint for local-llm.")
@click.option("--model", default=None, help="Local model id.")
@click.option("--api-key", default=None, help="API key for local endpoint.")
@click.option("--max-tokens", type=int, default=768, show_default=True)
@click.option("--release-gate-mode", is_flag=True, help="Enforce Tier 1 corpus requirement.")
@click.option("--allow-unsafe-local-llm", is_flag=True, help="Allow unbounded local-llm runs (USE WITH CAUTION).")
@click.option("--no-artifacts", is_flag=True, help="Skip writing validation artifacts.")
def validate_run(
    corpus_id: str,
    split: str | None,
    provider: str,
    limit: int,
    iterations: int,
    runs_dir: Path,
    output_dir: Path,
    base_url: str | None,
    model: str | None,
    api_key: str | None,
    max_tokens: int,
    release_gate_mode: bool,
    allow_unsafe_local_llm: bool,
    no_artifacts: bool,
) -> None:
    """Run a corpus-based validation sweep with structured metrics."""
    _run_validation_command(
        corpus_id=corpus_id,
        command="xrtm validate",
        split=split,
        provider=provider,
        limit=limit,
        iterations=iterations,
        runs_dir=runs_dir,
        output_dir=output_dir,
        base_url=base_url,
        model=model,
        api_key=api_key,
        max_tokens=max_tokens,
        release_gate_mode=release_gate_mode,
        allow_unsafe_local_llm=allow_unsafe_local_llm,
        no_artifacts=no_artifacts,
        report_title="XRTM Validation",
    )


@validate_group.command("list-corpora")
@click.option("--tier", type=click.Choice(["tier-1", "tier-2", "tier-3"]), default=None, help="Filter by tier.")
@click.option("--release-gate-only", is_flag=True, help="Show only release-gate approved corpora.")
def validate_list_corpora(tier: str | None, release_gate_only: bool) -> None:
    """List available validation corpora from the registry."""
    _list_registered_corpora(
        tier=tier,
        release_gate_only=release_gate_only,
        title="Available Validation Corpora",
    )


@validate_group.command("prepare-corpus")
@click.option("--corpus-id", default="forecast-v1", show_default=True, help="Corpus ID from registry.")
@click.option("--cache-root", type=click.Path(file_okay=False, path_type=Path), default=None, help="Override external corpus cache root.")
@click.option("--refresh", is_flag=True, help="Re-import even if the corpus is already cached.")
@click.option("--fixture-preview", is_flag=True, help="Cache the deterministic preview instead of downloading the external dataset.")
def validate_prepare_corpus(
    corpus_id: str,
    cache_root: Path | None,
    refresh: bool,
    fixture_preview: bool,
) -> None:
    """Prepare an external corpus cache for large validation runs."""
    _prepare_registered_corpus(
        corpus_id=corpus_id,
        cache_root=cache_root,
        refresh=refresh,
        fixture_preview=fixture_preview,
        title="Prepared Validation Corpus",
    )


@cli.group("benchmark")
def benchmark_group() -> None:
    """Thin benchmark-facing workflows over the corpus registry and evaluation stack."""


@benchmark_group.command("run")
@click.option("--corpus-id", default="xrtm-real-binary-v1", show_default=True, help="Corpus ID from registry.")
@click.option("--split", type=click.Choice(["full", "train", "eval", "held-out", "dev"]), default=None, help="Corpus split to use.")
@click.option("--provider", type=click.Choice(["mock", "local-llm"]), default="mock", show_default=True)
@click.option("--limit", type=int, default=10, show_default=True, help="Questions per iteration.")
@click.option("--iterations", type=int, default=1, show_default=True, help="Number of benchmark iterations.")
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs-benchmark"), show_default=True)
@click.option("--output-dir", type=click.Path(file_okay=False, path_type=Path), default=Path(".cache/benchmark"), show_default=True)
@click.option("--base-url", default=None, help="OpenAI-compatible local endpoint for local-llm.")
@click.option("--model", default=None, help="Local model id.")
@click.option("--api-key", default=None, help="API key for local endpoint.")
@click.option("--max-tokens", type=int, default=768, show_default=True)
@click.option("--release-gate-mode", is_flag=True, help="Enforce Tier 1 corpus requirement.")
@click.option("--allow-unsafe-local-llm", is_flag=True, help="Allow unbounded local-llm runs (USE WITH CAUTION).")
@click.option("--no-artifacts", is_flag=True, help="Skip writing benchmark artifacts.")
def benchmark_run(
    corpus_id: str,
    split: str | None,
    provider: str,
    limit: int,
    iterations: int,
    runs_dir: Path,
    output_dir: Path,
    base_url: str | None,
    model: str | None,
    api_key: str | None,
    max_tokens: int,
    release_gate_mode: bool,
    allow_unsafe_local_llm: bool,
    no_artifacts: bool,
) -> None:
    """Run a benchmark sweep over a registered corpus without owning the engine."""
    _run_validation_command(
        corpus_id=corpus_id,
        command="xrtm benchmark run",
        split=split,
        provider=provider,
        limit=limit,
        iterations=iterations,
        runs_dir=runs_dir,
        output_dir=output_dir,
        base_url=base_url,
        model=model,
        api_key=api_key,
        max_tokens=max_tokens,
        release_gate_mode=release_gate_mode,
        allow_unsafe_local_llm=allow_unsafe_local_llm,
        no_artifacts=no_artifacts,
        report_title="XRTM Benchmark",
    )


@benchmark_group.command("list-corpora")
@click.option("--tier", type=click.Choice(["tier-1", "tier-2", "tier-3"]), default=None, help="Filter by tier.")
@click.option("--release-gate-only", is_flag=True, help="Show only release-gate approved corpora.")
def benchmark_list_corpora(tier: str | None, release_gate_only: bool) -> None:
    """List benchmark-ready corpora from the registry."""
    _list_registered_corpora(
        tier=tier,
        release_gate_only=release_gate_only,
        title="Available Benchmark Corpora",
    )


@benchmark_group.command("cache-corpus")
@click.option("--corpus-id", default="forecast-v1", show_default=True, help="Corpus ID from registry.")
@click.option("--cache-root", type=click.Path(file_okay=False, path_type=Path), default=None, help="Override external corpus cache root.")
@click.option("--refresh", is_flag=True, help="Re-import even if the corpus is already cached.")
@click.option("--fixture-preview", is_flag=True, help="Cache the deterministic preview instead of downloading the external dataset.")
def benchmark_cache_corpus(
    corpus_id: str,
    cache_root: Path | None,
    refresh: bool,
    fixture_preview: bool,
) -> None:
    """Cache an external benchmark corpus for offline benchmark runs."""
    _prepare_registered_corpus(
        corpus_id=corpus_id,
        cache_root=cache_root,
        refresh=refresh,
        fixture_preview=fixture_preview,
        title="Prepared Benchmark Corpus",
    )


@benchmark_group.command("compare")
@click.option("--corpus-id", default="xrtm-real-binary-v1", show_default=True, help="Corpus ID from registry.")
@click.option("--split", type=click.Choice(["full", "train", "eval", "held-out", "dev"]), default=None, help="Corpus split to use.")
@click.option("--limit", type=int, default=10, show_default=True, help="Questions in the frozen compare slice.")
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs-benchmark"), show_default=True)
@click.option("--output-dir", type=click.Path(file_okay=False, path_type=Path), default=Path(".cache/benchmark"), show_default=True)
@click.option("--release-gate-mode", is_flag=True, help="Enforce Tier 1 corpus requirement.")
@click.option("--allow-unsafe-local-llm", is_flag=True, help="Allow large local-llm runs (USE WITH CAUTION).")
@click.option("--no-artifact", is_flag=True, help="Skip writing the compare artifact.")
@click.option("--baseline-label", default="baseline", show_default=True, help="Human-readable baseline arm label.")
@click.option("--baseline-provider", type=click.Choice(["mock", "local-llm"]), default="mock", show_default=True)
@click.option("--baseline-base-url", default=None, help="Baseline local-LLM endpoint.")
@click.option("--baseline-model", default=None, help="Baseline model id.")
@click.option("--baseline-api-key", default=None, help="Baseline API key.")
@click.option("--baseline-max-tokens", type=int, default=768, show_default=True)
@click.option("--candidate-label", default="candidate", show_default=True, help="Human-readable candidate arm label.")
@click.option("--candidate-provider", type=click.Choice(["mock", "local-llm"]), default="mock", show_default=True)
@click.option("--candidate-base-url", default=None, help="Candidate local-LLM endpoint.")
@click.option("--candidate-model", default=None, help="Candidate model id.")
@click.option("--candidate-api-key", default=None, help="Candidate API key.")
@click.option("--candidate-max-tokens", type=int, default=768, show_default=True)
def benchmark_compare(
    corpus_id: str,
    split: str | None,
    limit: int,
    runs_dir: Path,
    output_dir: Path,
    release_gate_mode: bool,
    allow_unsafe_local_llm: bool,
    no_artifact: bool,
    baseline_label: str,
    baseline_provider: str,
    baseline_base_url: str | None,
    baseline_model: str | None,
    baseline_api_key: str | None,
    baseline_max_tokens: int,
    candidate_label: str,
    candidate_provider: str,
    candidate_base_url: str | None,
    candidate_model: str | None,
    candidate_api_key: str | None,
    candidate_max_tokens: int,
) -> None:
    """Compare a baseline arm against a candidate arm on one frozen benchmark slice."""
    baseline_arm, candidate_arm = _default_benchmark_arms(
        baseline_label=baseline_label,
        baseline_provider=baseline_provider,
        baseline_base_url=baseline_base_url,
        baseline_model=baseline_model,
        baseline_api_key=baseline_api_key,
        baseline_max_tokens=baseline_max_tokens,
        candidate_label=candidate_label,
        candidate_provider=candidate_provider,
        candidate_base_url=candidate_base_url,
        candidate_model=candidate_model,
        candidate_api_key=candidate_api_key,
        candidate_max_tokens=candidate_max_tokens,
    )
    try:
        report = run_benchmark_compare(
            BenchmarkCompareOptions(
                corpus_id=corpus_id,
                split=split,
                limit=limit,
                runs_dir=runs_dir,
                output_dir=output_dir,
                release_gate_mode=release_gate_mode,
                allow_unsafe_local_llm=allow_unsafe_local_llm,
                write_artifact=not no_artifact,
                baseline=baseline_arm,
                candidate=candidate_arm,
            )
        )
    except (ValidationTierError, ValidationSafetyError, ValueError, RuntimeError) as exc:
        raise click.ClickException(str(exc)) from exc

    print_benchmark_compare_report(console, report)


@benchmark_group.command("stress")
@click.option("--corpus-id", default="xrtm-real-binary-v1", show_default=True, help="Corpus ID from registry.")
@click.option("--split", type=click.Choice(["full", "train", "eval", "held-out", "dev"]), default=None, help="Corpus split to use.")
@click.option("--limit", type=int, default=10, show_default=True, help="Questions in the frozen stress slice.")
@click.option("--repeats", type=int, default=3, show_default=True, help="How many times to rerun each arm.")
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs-benchmark"), show_default=True)
@click.option("--output-dir", type=click.Path(file_okay=False, path_type=Path), default=Path(".cache/benchmark"), show_default=True)
@click.option("--release-gate-mode", is_flag=True, help="Enforce Tier 1 corpus requirement.")
@click.option("--allow-unsafe-local-llm", is_flag=True, help="Allow large local-llm runs (USE WITH CAUTION).")
@click.option("--no-artifact", is_flag=True, help="Skip writing the stress artifact.")
@click.option("--baseline-label", default="baseline", show_default=True, help="Human-readable baseline arm label.")
@click.option("--baseline-provider", type=click.Choice(["mock", "local-llm"]), default="mock", show_default=True)
@click.option("--baseline-base-url", default=None, help="Baseline local-LLM endpoint.")
@click.option("--baseline-model", default=None, help="Baseline model id.")
@click.option("--baseline-api-key", default=None, help="Baseline API key.")
@click.option("--baseline-max-tokens", type=int, default=768, show_default=True)
@click.option("--candidate-label", default="candidate", show_default=True, help="Human-readable candidate arm label.")
@click.option("--candidate-provider", type=click.Choice(["mock", "local-llm"]), default="mock", show_default=True)
@click.option("--candidate-base-url", default=None, help="Candidate local-LLM endpoint.")
@click.option("--candidate-model", default=None, help="Candidate model id.")
@click.option("--candidate-api-key", default=None, help="Candidate API key.")
@click.option("--candidate-max-tokens", type=int, default=768, show_default=True)
def benchmark_stress(
    corpus_id: str,
    split: str | None,
    limit: int,
    repeats: int,
    runs_dir: Path,
    output_dir: Path,
    release_gate_mode: bool,
    allow_unsafe_local_llm: bool,
    no_artifact: bool,
    baseline_label: str,
    baseline_provider: str,
    baseline_base_url: str | None,
    baseline_model: str | None,
    baseline_api_key: str | None,
    baseline_max_tokens: int,
    candidate_label: str,
    candidate_provider: str,
    candidate_base_url: str | None,
    candidate_model: str | None,
    candidate_api_key: str | None,
    candidate_max_tokens: int,
) -> None:
    """Run a repeated baseline-vs-candidate stress suite on one frozen slice."""
    baseline_arm, candidate_arm = _default_benchmark_arms(
        baseline_label=baseline_label,
        baseline_provider=baseline_provider,
        baseline_base_url=baseline_base_url,
        baseline_model=baseline_model,
        baseline_api_key=baseline_api_key,
        baseline_max_tokens=baseline_max_tokens,
        candidate_label=candidate_label,
        candidate_provider=candidate_provider,
        candidate_base_url=candidate_base_url,
        candidate_model=candidate_model,
        candidate_api_key=candidate_api_key,
        candidate_max_tokens=candidate_max_tokens,
    )
    try:
        report = run_benchmark_stress_suite(
            BenchmarkStressOptions(
                corpus_id=corpus_id,
                split=split,
                limit=limit,
                repeat_count=repeats,
                runs_dir=runs_dir,
                output_dir=output_dir,
                release_gate_mode=release_gate_mode,
                allow_unsafe_local_llm=allow_unsafe_local_llm,
                write_artifact=not no_artifact,
                arms=(baseline_arm, candidate_arm),
            )
        )
    except (ValidationTierError, ValidationSafetyError, ValueError, RuntimeError) as exc:
        raise click.ClickException(str(exc)) from exc

    print_benchmark_stress_report(console, report)


@cli.group("monitor")
def monitor_group() -> None:
    """Monitor forecast questions with local artifact-backed state."""


@monitor_group.command("start")
@click.option("--provider", type=click.Choice(["mock", "local-llm"]), default="mock", show_default=True)
@click.option("--limit", type=int, default=2, show_default=True, help="Number of corpus questions to monitor.")
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"), show_default=True)
@click.option("--base-url", default=None, help="OpenAI-compatible local endpoint for --provider local-llm.")
@click.option("--model", default=None, help="Local model id served by the endpoint.")
@click.option("--api-key", default=None, help="API key for the local endpoint; defaults to test/env.")
@click.option("--probability-delta", type=float, default=0.10, show_default=True, help="Warn when a watch moves by this much.")
@click.option("--confidence-shift", type=float, default=0.20, show_default=True, help="Warn when forecast confidence shifts by this much.")
def monitor_start(
    provider: str,
    limit: int,
    runs_dir: Path,
    base_url: str | None,
    model: str | None,
    api_key: str | None,
    probability_delta: float,
    confidence_shift: float,
) -> None:
    """Create a local monitor run and watch list."""

    try:
        run = start_monitor(
            runs_dir=runs_dir,
            limit=limit,
            provider=provider,
            base_url=base_url,
            model=model,
            api_key=api_key,
            thresholds=MonitorThresholds(probability_delta=probability_delta, confidence_shift=confidence_shift),
        )
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    runs_dir_arg = runs_dir_command_arg(runs_dir)
    run_dir_arg = shell_quote(run.run_dir.as_posix())
    lines = [
        f"Monitor started: {run.run_id}",
        f"Directory: {run.run_dir}",
        f"List active monitors: xrtm monitor list {runs_dir_arg}",
        f"Inspect this monitor: xrtm monitor show {run_dir_arg}",
        f"Run one update cycle: xrtm monitor run-once {run_dir_arg}",
        f"Plain forecast runs still live under: xrtm runs list {runs_dir_arg}",
    ]
    console.print(Panel("\n".join(lines), title="Monitor ready", border_style="green"))


@monitor_group.command("list")
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"), show_default=True)
def monitor_list(runs_dir: Path) -> None:
    """List monitor runs."""

    monitors = list_monitors(runs_dir)
    if not monitors:
        runs_dir_arg = runs_dir_command_arg(runs_dir)
        console.print(
            Panel(
                "\n".join(
                    [
                        "No monitor runs found in this workspace.",
                        f"Start one with: xrtm monitor start --provider mock --limit 2 {runs_dir_arg}",
                        f"Review regular forecast runs with: xrtm runs list {runs_dir_arg}",
                    ]
                ),
                title="XRTM Monitors",
                border_style="yellow",
            )
        )
        return

    table = Table(title="XRTM Monitors")
    table.add_column("Run", style="cyan", no_wrap=True)
    table.add_column("Status", style="green")
    table.add_column("Provider")
    table.add_column("Watches", justify="right")
    table.add_column("Updates", justify="right")
    table.add_column("Warnings", justify="right")
    table.add_column("Monitor dir")
    table.add_column("Updated", style="dim")
    for monitor in monitors:
        table.add_row(
            str(monitor["run_id"]),
            str(monitor["status"]),
            str(monitor.get("provider") or ""),
            str(monitor["watches"]),
            str(monitor.get("updates") or 0),
            str(monitor.get("warning_count") or 0),
            str(monitor["run_dir"]),
            str(monitor["updated_at"]),
        )
    console.print(table)


@monitor_group.command("show")
@click.argument("run_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
def monitor_show(run_dir: Path) -> None:
    """Show one monitor run."""

    try:
        monitor = load_monitor(run_dir)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    table = Table(title=f"Monitor {run_dir.name}")
    table.add_column("Watch", style="cyan")
    table.add_column("Question")
    table.add_column("Status", style="green")
    table.add_column("Updates", justify="right")
    table.add_column("Latest probability", justify="right")
    for watch in monitor.get("watches", []):
        trajectory = watch.get("trajectory", [])
        latest = trajectory[-1]["probability"] if trajectory else "N/A"
        table.add_row(
            str(watch.get("watch_id")),
            str(watch.get("title") or watch.get("question_id")),
            str(watch.get("status")),
            str(len(trajectory)),
            str(latest),
        )
    console.print(Panel(f"Status: {monitor.get('status')}", title="Monitor State"))
    console.print(table)
    run_dir_arg = shell_quote(run_dir.as_posix())
    console.print(
        Panel(
            "\n".join(
                [
                    f"Run one update cycle: xrtm monitor run-once {run_dir_arg}",
                    f"Pause or halt: xrtm monitor pause {run_dir_arg} | xrtm monitor halt {run_dir_arg}",
                ]
            ),
            title="Monitor commands",
            border_style="blue",
        )
    )


@monitor_group.command("run-once")
@click.argument("run_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--provider", type=click.Choice(["mock", "local-llm"]), default=None)
@click.option("--base-url", default=None, help="OpenAI-compatible local endpoint for --provider local-llm.")
@click.option("--model", default=None, help="Local model id served by the endpoint.")
@click.option("--api-key", default=None, help="API key for the local endpoint; defaults to test/env.")
@click.option("--max-tokens", type=int, default=768, show_default=True)
def monitor_run_once(
    run_dir: Path,
    provider: str | None,
    base_url: str | None,
    model: str | None,
    api_key: str | None,
    max_tokens: int,
) -> None:
    """Run one monitor update cycle."""

    try:
        monitor = run_monitor_once(
            run_dir=run_dir,
            provider=provider,
            base_url=base_url,
            model=model,
            api_key=api_key,
            max_tokens=max_tokens,
        )
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    console.print(f"[green]Monitor cycle complete:[/green] {len(monitor.get('watches', []))} watch(es)")


@monitor_group.command("daemon")
@click.argument("run_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--cycles", type=int, default=1, show_default=True, help="Bounded number of monitor cycles to run.")
@click.option("--interval-seconds", type=float, default=60.0, show_default=True, help="Seconds between cycles.")
@click.option("--provider", type=click.Choice(["mock", "local-llm"]), default=None)
@click.option("--base-url", default=None, help="OpenAI-compatible local endpoint for --provider local-llm.")
@click.option("--model", default=None, help="Local model id served by the endpoint.")
@click.option("--api-key", default=None, help="API key for the local endpoint; defaults to test/env.")
@click.option("--max-tokens", type=int, default=768, show_default=True)
def monitor_daemon(
    run_dir: Path,
    cycles: int,
    interval_seconds: float,
    provider: str | None,
    base_url: str | None,
    model: str | None,
    api_key: str | None,
    max_tokens: int,
) -> None:
    """Run a bounded local monitor loop."""

    try:
        monitor = run_monitor_daemon(
            run_dir=run_dir,
            cycles=cycles,
            interval_seconds=interval_seconds,
            provider=provider,
            base_url=base_url,
            model=model,
            api_key=api_key,
            max_tokens=max_tokens,
        )
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    console.print(
        f"[green]Monitor daemon complete:[/green] {monitor.get('cycles', 0)} cycle(s), status={monitor.get('status')}"
    )


@monitor_group.command("pause")
@click.argument("run_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
def monitor_pause(run_dir: Path) -> None:
    """Pause a monitor run."""

    _set_monitor_status_command(run_dir, "paused")


@monitor_group.command("resume")
@click.argument("run_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
def monitor_resume(run_dir: Path) -> None:
    """Resume a monitor run."""

    _set_monitor_status_command(run_dir, "running")


@monitor_group.command("halt")
@click.argument("run_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
def monitor_halt(run_dir: Path) -> None:
    """Halt a monitor run."""

    _set_monitor_status_command(run_dir, "halted")


@cli.group("local-llm")
def local_llm_group() -> None:
    """Inspect local OpenAI-compatible LLM backends."""


@local_llm_group.command("status")
@click.option("--base-url", default=None, help="OpenAI-compatible local endpoint to check.")
def local_llm_status_command(base_url: str | None) -> None:
    """Show local llama.cpp/OpenAI-compatible endpoint status."""

    _show_local_llm_status(base_url=base_url, fail_on_unhealthy=True)


@cli.group("report")
def report_group() -> None:
    """Generate reports from product artifacts."""


@report_group.command("html")
@click.argument("run_dir", type=click.Path(exists=True, file_okay=False, path_type=Path), required=False)
@click.option(
    "--runs-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("runs"),
    show_default=True,
    help="Run history directory used with --latest.",
)
@click.option("--latest", "use_latest", is_flag=True, help="Generate a report for the newest canonical run.")
def report_html(run_dir: Path | None, runs_dir: Path, use_latest: bool) -> None:
    """Generate a static HTML report for a run directory or use --latest."""

    try:
        run_dir = _resolve_inspection_run_dir(run_dir=run_dir, runs_dir=runs_dir, use_latest=use_latest)
        report_path = render_html_report(run_dir)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    console.print(f"[green]Report written:[/green] {report_path}")
    console.print(
        Panel(
            "\n".join(
                [
                    f"Run dir: {run_dir}",
                    f"Inspect artifacts: xrtm artifacts inspect {shell_quote(run_dir.as_posix())}",
                    f"Browse the same workspace: xrtm web {runs_dir_command_arg(run_dir.parent)}",
                ]
            ),
            title="Report follow-through",
            border_style="blue",
        )
    )


@cli.command()
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"), show_default=True)
@click.option("--watch", is_flag=True, help="Keep refreshing until interrupted.")
@click.option("--refresh-interval", type=float, default=2.0, show_default=True)
@click.option("--iterations", type=int, default=None, help="Bounded refresh count for smoke tests.")
def tui(runs_dir: Path, watch: bool, refresh_interval: float, iterations: int | None) -> None:
    """Open the terminal cockpit over runs, monitors, and local LLM status."""

    if watch or iterations:
        run_tui(console, runs_dir=runs_dir, refresh_interval=refresh_interval, iterations=iterations)
    else:
        render_tui_once(console, runs_dir=runs_dir)


@cli.command()
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"), show_default=True)
@click.option(
    "--workflows-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_LOCAL_WORKFLOWS_DIR,
    show_default=True,
)
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", type=int, default=8765, show_default=True)
@click.option("--smoke", is_flag=True, help="Validate routes without blocking.")
def web(runs_dir: Path, workflows_dir: Path, host: str, port: int, smoke: bool) -> None:
    """Serve the local XRTM WebUI/dashboard and editable workflow workbench."""

    if smoke:
        snapshot = web_snapshot(runs_dir)
        workbench = workflow_workbench_snapshot(runs_dir, workflows_dir)
        console.print(
            f"[green]WebUI smoke ok:[/green] {len(snapshot['runs'])} run(s), "
            f"{len(workbench['workflows'])} workflow(s), workbench ready"
        )
        return
    server = create_web_server(runs_dir=runs_dir, workflows_dir=workflows_dir, host=host, port=port)
    address, active_port = server.server_address
    console.print(f"[green]XRTM WebUI:[/green] http://{address}:{active_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping XRTM WebUI[/yellow]")
    finally:
        server.server_close()


def _run_pipeline_command(options: PipelineOptions) -> None:
    result = _execute_pipeline(options)
    print_pipeline_result(console, result, title=pipeline_result_title(options.command))
    print_post_run_summary(
        console,
        result,
        runs_dir=options.runs_dir,
        success_title="Run complete",
        success_label=f"{options.command} completed",
        what_succeeded=pipeline_success_details(write_report=options.write_report),
        write_report=options.write_report,
    )


def _execute_pipeline(options: PipelineOptions) -> PipelineResult:
    try:
        return run_pipeline(options)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


def _run_product_action(action: Callable[[], PipelineResult]) -> PipelineResult:
    try:
        return action()
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


def _resolve_inspection_run_dir(*, run_dir: Path | None, runs_dir: Path, use_latest: bool) -> Path:
    if use_latest:
        if run_dir is not None:
            raise ValueError("pass either RUN_DIR or --latest, not both")
        return resolve_run_dir(runs_dir, "latest")
    if run_dir is None:
        raise ValueError("missing RUN_DIR; pass a run directory path or use --latest with --runs-dir")
    return run_dir


def _set_monitor_status_command(run_dir: Path, status: str) -> None:
    try:
        set_monitor_status(run_dir, status)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    console.print(f"[green]Monitor {status}:[/green] {run_dir}")


if __name__ == "__main__":
    cli()


__all__ = ["cli"]
