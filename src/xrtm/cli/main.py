"""XRTM product CLI."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

from xrtm.product import launch as launch_module
from xrtm.product.artifacts import ArtifactStore
from xrtm.product.doctor import run_doctor
from xrtm.product.history import latest_run_dir, list_runs, run_detail
from xrtm.product.providers import DETERMINISTIC_PROVIDER_NAME
from xrtm.product.workflows import DEFAULT_LOCAL_WORKFLOWS_DIR, WorkflowRegistry
from xrtm.version import __version__

console = Console()


@click.group()
@click.version_option(version=__version__)
def cli():
    """XRTM — AI for event forecasting."""


# --- start ---
@cli.command()
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"))
@click.option("--limit", type=int, default=5, show_default=True)
@click.option("--provider", default=None, help="LLM provider (default: deterministic, no API key needed)")
@click.option("--model", default=None, help="Model ID (e.g. gpt-4o, deepseek-v4-pro)")
@click.option("--base-url", default=None, help="API base URL for OpenAI-compatible endpoints")
@click.option("--api-key", default=None, help="API key for the provider")
def start(runs_dir: Path, limit: int, provider: str | None, model: str | None, base_url: str | None, api_key: str | None):
    """Run a guided quickstart forecast with the deterministic provider.

    Add --provider to use a real LLM:
    xrtm start --provider openai --model deepseek-v4-pro --base-url https://api.deepseek.com
    """
    if provider:
        # Real LLM path
        result = launch_module.run_demo_workflow(
            provider=provider,
            limit=limit,
            runs_dir=runs_dir,
            base_url=base_url,
            model=model,
            api_key=api_key,
        )
    else:
        result = launch_module.run_start_quickstart(limit=limit, runs_dir=runs_dir)
    console.print(f"[bold green]Forecast complete: {result.run.run_id}[/bold green]")
    console.print(f"  Forecasts: {result.forecast_records}")
    if result.eval_brier_score is not None:
        console.print(f"  Brier:     {result.eval_brier_score:.4f}")
    console.print(f"  Artifacts: {result.run.run_dir}")


# --- demo ---
@cli.command()
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"))
@click.option("--limit", type=int, default=2, show_default=True)
def demo(runs_dir: Path, limit: int):
    """Run a quick 2-question deterministic demo."""
    result = launch_module.run_demo_workflow(limit=limit, runs_dir=runs_dir)
    console.print(f"[bold green]Demo complete: {result.run.run_id}[/bold green]")


# --- doctor ---
@cli.command()
def doctor():
    """Run readiness checks."""
    run_doctor(console=console, show_next_steps=False)


# --- workflow ---
@cli.group()
def workflow():
    """Workflow inspection and execution."""


@workflow.command("list")
@click.option("--workflows-dir", type=click.Path(file_okay=False, path_type=Path), default=DEFAULT_LOCAL_WORKFLOWS_DIR)
def workflow_list(workflows_dir: Path):
    """List available workflows."""
    registry = WorkflowRegistry(local_roots=(workflows_dir,))
    for summary in registry.list_workflows():
        console.print(f"  {summary.name}")


@workflow.command("show")
@click.argument("name")
@click.option("--workflows-dir", type=click.Path(file_okay=False, path_type=Path), default=DEFAULT_LOCAL_WORKFLOWS_DIR)
def workflow_show(name: str, workflows_dir: Path):
    """Show workflow details."""
    blueprint = WorkflowRegistry(local_roots=(workflows_dir,)).load(name)
    console.print(f"Name: {blueprint.name}")
    console.print(f"Title: {blueprint.title}")
    console.print(f"Kind: {blueprint.workflow_kind}")
    for node_id, node_spec in blueprint.graph.nodes.items():
        console.print(f"  Node: {node_id} ({node_spec.kind})")


# --- runs ---
@cli.group()
def runs():
    """Run history inspection."""


@runs.command("list")
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"))
def runs_list(runs_dir: Path):
    """List recent runs."""
    for run in list_runs(runs_dir):
        console.print(f"  {run.get('run_id', '?')[:12]}...")


@runs.command("show")
@click.argument("run_id", required=False)
@click.option("--latest", is_flag=True, help="Show the most recent run")
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"))
def runs_show(run_id: str | None, latest: bool, runs_dir: Path):
    """Show run detail. Use --latest for the most recent run."""
    if latest:
        run_dir = latest_run_dir(runs_dir)
    elif run_id:
        run_dir = runs_dir / run_id
    else:
        console.print("[red]Provide a run ID or use --latest[/red]")
        return

    if run_dir.is_dir():
        import json
        detail = run_detail(run_dir)
        console.print_json(json.dumps(detail))
    else:
        console.print(f"[red]Run not found: {run_dir}[/red]")


# --- artifacts ---
@cli.group()
def artifacts():
    """Run artifact inspection."""


@artifacts.command("inspect")
@click.argument("run_id")
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"))
def artifacts_inspect(run_id: str, runs_dir: Path):
    """Inspect artifacts for a run."""
    store = ArtifactStore(runs_dir=runs_dir)
    for name in store.list_artifacts(run_id):
        console.print(f"  {name}")


# --- providers ---
@cli.group()
def providers():
    """Provider management."""


@providers.command("doctor")
def providers_doctor():
    """Check provider health."""
    console.print(f"[green]Deterministic provider: {DETERMINISTIC_PROVIDER_NAME}[/green]")


if __name__ == "__main__":
    cli()
__all__ = ["cli"]
