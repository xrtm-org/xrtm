"""Terminal UI rendering over canonical XRTM run artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from xrtm.product.monitoring import load_monitor
from xrtm.product.providers import local_llm_status
from xrtm.product.read_models import list_monitor_records, list_run_records


def render_tui_once(console: Console, *, runs_dir: Path) -> None:
    """Render a one-shot terminal cockpit view."""

    console.print(build_tui_view(runs_dir=runs_dir))


def run_tui(console: Console, *, runs_dir: Path, refresh_interval: float = 2.0, iterations: int | None = None) -> None:
    """Run a lightweight live terminal cockpit over run artifacts."""

    with Live(build_tui_view(runs_dir=runs_dir), console=console, refresh_per_second=1 / refresh_interval) as live:
        completed = 0
        while iterations is None or completed < iterations:
            live.update(build_tui_view(runs_dir=runs_dir))
            completed += 1


def build_tui_view(*, runs_dir: Path) -> Layout:
    """Build the terminal cockpit layout without owning product logic."""

    layout = Layout(name="xrtm")
    layout.split_column(
        Layout(Panel("XRTM local product cockpit", style="bold cyan"), name="header", size=3),
        Layout(name="body"),
    )
    layout["body"].split_row(
        Layout(_runs_panel(runs_dir), name="runs", ratio=2),
        Layout(_side_panel(runs_dir), name="side", ratio=1),
    )
    return layout


def _runs_panel(runs_dir: Path) -> Panel:
    table = Table(title="Runs")
    table.add_column("Run", style="cyan")
    table.add_column("Workflow", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Provider")
    table.add_column("Forecasts", justify="right")
    table.add_column("Warnings", justify="right")
    table.add_column("Command")
    table.add_column("Updated", style="dim")
    for run in list_run_records(runs_dir):
        summary = run.get("summary", {})
        table.add_row(
            str(run.get("run_id")),
            _workflow_summary(run),
            str(run.get("status")),
            str(run.get("provider")),
            str(summary.get("forecast_count", "")),
            str(summary.get("warning_count", "")),
            _run_command_summary(run),
            str(run.get("updated_at")),
        )
    return Panel(table, title=str(runs_dir))


def _run_command_summary(run: dict[str, Any]) -> str:
    summary = run.get("summary", {})
    if isinstance(summary, dict) and summary:
        return f"{run.get('command')} ({summary.get('forecast_count', 0)} forecasts)"
    return str(run.get("command"))


def _workflow_summary(run: dict[str, Any]) -> str:
    workflow = run.get("workflow", {})
    if not isinstance(workflow, dict) or not workflow:
        return "n/a"
    name = workflow.get("name") or workflow.get("title") or "workflow"
    kind = workflow.get("kind")
    steps = workflow.get("graph_step_count")
    if kind and steps:
        return f"{name} [{kind}, {steps} steps]"
    if kind:
        return f"{name} [{kind}]"
    return str(name)


def _side_panel(runs_dir: Path) -> Panel:
    local_status = local_llm_status()
    monitors = list_monitor_records(runs_dir)
    latest_monitor = _latest_monitor_summary(runs_dir, monitors)
    body = Group(
        Panel(
            "\n".join(
                [
                    f"Healthy: {local_status['healthy']}",
                    f"Base URL: {local_status['base_url']}",
                    f"Models: {', '.join(local_status['models']) if local_status['models'] else 'N/A'}",
                ]
            ),
            title="Local LLM",
            border_style="green" if local_status["healthy"] else "red",
        ),
        Panel(latest_monitor, title="Monitoring"),
        Panel(_latest_workflow_summary(runs_dir), title="Latest workflow"),
    )
    return Panel(body, title="Status")


def _latest_monitor_summary(runs_dir: Path, monitors: list[dict[str, Any]]) -> str:
    if not monitors:
        return "No monitor runs yet.\nStart one with xrtm monitor start.\nPlain forecast runs stay in the Runs table."
    latest = monitors[0]
    try:
        monitor = load_monitor(Path(latest["run_dir"]))
    except FileNotFoundError:
        return "Monitor metadata missing"
    updated = 0
    for watch in monitor.get("watches", []):
        updated += len(watch.get("trajectory", []))
    return "\n".join(
        [
            f"Run: {Path(latest['run_dir']).relative_to(runs_dir.parent) if runs_dir.parent in Path(latest['run_dir']).parents else latest['run_dir']}",
            f"Status: {monitor.get('status')}",
            f"Watches: {len(monitor.get('watches', []))}",
            f"Updates: {updated}",
            f"Warnings: {latest.get('warning_count', 0) or 0}",
        ]
    )


def _latest_workflow_summary(runs_dir: Path) -> str:
    runs = list_run_records(runs_dir)
    if not runs:
        return "No workflow runs yet."
    latest = runs[0]
    workflow = latest.get("workflow", {})
    if not isinstance(workflow, dict) or not workflow:
        return "Latest run has no blueprint metadata."
    return "\n".join(
        [
            f"Name: {workflow.get('name')}",
            f"Kind: {workflow.get('kind')}",
            f"Entry: {workflow.get('entry')}",
            f"Nodes: {workflow.get('node_count')}",
            f"Graph steps: {workflow.get('graph_step_count')}",
        ]
    )


__all__ = ["build_tui_view", "render_tui_once", "run_tui"]
