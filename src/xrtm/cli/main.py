"""Minimal XRTM product CLI."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

from xrtm.product.artifacts import ArtifactStore
from xrtm.product.doctor import run_doctor
from xrtm.product.history import list_runs, run_detail
from xrtm.product.providers import DETERMINISTIC_PROVIDER_NAME
from xrtm.product.workflows import DEFAULT_LOCAL_WORKFLOWS_DIR, WorkflowRegistry
from xrtm.version import __version__

console = Console()


@click.group()
@click.version_option(version=__version__)
def cli():
    """XRTM — AI for event forecasting."""


@cli.command()
def doctor():
    """Run readiness checks."""
    run_doctor(console=console, show_next_steps=False)


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
@click.argument("run_id")
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"))
def runs_show(run_id: str, runs_dir: Path):
    """Show run detail."""
    run_dir = runs_dir / run_id
    if run_dir.is_dir():
        detail = run_detail(run_dir)
        import json
        console.print_json(json.dumps(detail))
    else:
        console.print("[red]Run not found.[/red]")


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
