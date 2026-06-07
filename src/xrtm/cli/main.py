"""XRTM product CLI."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

from xrtm.product import launch as launch_module
from xrtm.product.doctor import run_doctor
from xrtm.product.history import latest_run_dir, run_detail
from xrtm.version import __version__

console = Console()


@click.group()
@click.version_option(version=__version__)
def cli():
    """XRTM — AI for event forecasting."""


@cli.command()
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"))
@click.option("--limit", type=int, default=5, show_default=True)
@click.option("--model", default=None, help="Model ID (default: $OPENAI_MODEL or gpt-4o-mini)")
@click.option("--base-url", default=None, help="API base URL (default: $OPENAI_BASE_URL or openai.com)")
@click.option("--provider", default="openai", hidden=True)
def start(runs_dir: Path, limit: int, model: str | None, base_url: str | None, provider: str):
    """Run forecasts. Requires OPENAI_API_KEY in env or .env file.

    \b
    Examples:
      xrtm start
      xrtm start --model deepseek-v4-pro --base-url https://api.deepseek.com
      xrtm start --limit 10
    """
    result = launch_module.run_forecasts(
        limit=limit, runs_dir=runs_dir,
        model=model, base_url=base_url, provider=provider,
    )
    console.print(f"[bold green]Forecast complete: {result.run.run_id}[/bold green]")
    console.print(f"  Forecasts: {result.forecast_records}")
    if result.eval_brier_score is not None:
        console.print(f"  Brier:     {result.eval_brier_score:.4f}")
    console.print(f"  Artifacts: {result.run.run_dir}")


@cli.command()
def doctor():
    """Run readiness checks."""
    run_doctor(console=console, show_next_steps=False)


@cli.group()
def runs():
    """Run history inspection."""


@runs.command("show")
@click.option("--latest", is_flag=True, help="Show the most recent run")
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"))
@click.argument("run_id", required=False)
def runs_show(latest: bool, runs_dir: Path, run_id: str | None):
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
        console.print_json(json.dumps(run_detail(run_dir)))
    else:
        console.print(f"[red]Run not found: {run_dir}[/red]")


if __name__ == "__main__":
    cli()
__all__ = ["cli"]
