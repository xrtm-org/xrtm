"""XRTM product CLI."""

from __future__ import annotations

import os
import time
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

# Load .env file if present
_env_path = Path(".env")
if _env_path.is_file():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line.startswith("export "):
                _line = _line[7:]
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

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
    with console.status(f"[bold]Generating {limit} forecasts...", spinner="dots"):
        start_time = time.perf_counter()
        try:
            result = launch_module.run_forecasts(
                limit=limit, runs_dir=runs_dir,
                model=model, base_url=base_url, provider=provider,
            )
        except (ValueError, OSError) as exc:
            console.print(f"\n[red]Error: {exc}[/red]")
            console.print("\n[yellow]Set your API key:[/yellow]")
            console.print("  export OPENAI_API_KEY=sk-...")
            console.print("  or create a .env file with OPENAI_API_KEY=sk-...")
            return
        elapsed = time.perf_counter() - start_time

    # Color-code Brier
    brier = result.eval_brier_score
    if brier is not None:
        brier_color = "green" if brier < 0.10 else "yellow" if brier < 0.20 else "red"
        brier_text = f"[{brier_color}]Brier {brier:.4f}[/{brier_color}]"
    else:
        brier_text = "Brier N/A"

    lines = [
        f"{result.forecast_records} forecasts  ·  {brier_text}",
        f"Duration {elapsed:.1f}s  ·  [dim]{result.run.run_id}[/dim]",
        f"Artifacts → [underline]{result.run.run_dir}[/underline]",
    ]
    console.print(Panel("\n".join(lines), title="[bold]Forecast Complete", border_style="green"))


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
