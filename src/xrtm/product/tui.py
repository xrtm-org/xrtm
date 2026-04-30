"""Terminal UI rendering over canonical XRTM run artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from xrtm.product.artifacts import ArtifactStore
from xrtm.product.monitoring import list_monitors, load_monitor
from xrtm.product.providers import local_llm_status


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
    table.add_column("Status", style="green")
    table.add_column("Provider")
    table.add_column("Command")
    table.add_column("Updated", style="dim")
    for run in _list_runs(runs_dir):
        table.add_row(
            str(run.get("run_id")),
            str(run.get("status")),
            str(run.get("provider")),
            _run_command_summary(run),
            str(run.get("updated_at")),
        )
    return Panel(table, title=str(runs_dir))


def _run_command_summary(run: dict[str, Any]) -> str:
    summary = run.get("summary", {})
    if isinstance(summary, dict) and summary:
        return f"{run.get('command')} ({summary.get('forecast_count', 0)} forecasts)"
    return str(run.get("command"))


def _side_panel(runs_dir: Path) -> Panel:
    local_status = local_llm_status()
    monitors = list_monitors(runs_dir)
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
    )
    return Panel(body, title="Status")


def _latest_monitor_summary(runs_dir: Path, monitors: list[dict[str, Any]]) -> str:
    if not monitors:
        return "No monitor runs"
    latest = monitors[-1]
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
        ]
    )


def _list_runs(runs_dir: Path) -> list[dict[str, Any]]:
    if not runs_dir.exists():
        return []
    runs: list[dict[str, Any]] = []
    for run_dir in sorted(path for path in runs_dir.iterdir() if path.is_dir()):
        try:
            run = ArtifactStore.read_run(run_dir)
        except FileNotFoundError:
            continue
        runs.append(run)
    return runs


__all__ = ["build_tui_view", "render_tui_once", "run_tui"]
