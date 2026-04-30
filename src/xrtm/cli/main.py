"""Top-level XRTM product command."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from xrtm.product.artifacts import ArtifactStore
from xrtm.product.monitoring import (
    list_monitors,
    load_monitor,
    run_monitor_daemon,
    run_monitor_once,
    set_monitor_status,
    start_monitor,
)
from xrtm.product.observability import MonitorThresholds
from xrtm.product.pipeline import PipelineOptions, package_versions, run_pipeline
from xrtm.product.providers import local_llm_status
from xrtm.product.reports import render_html_report
from xrtm.product.tui import render_tui_once, run_tui
from xrtm.product.web import create_web_server, web_snapshot
from xrtm.version import __version__

console = Console()


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """XRTM local-first product cockpit."""


@cli.command()
def doctor() -> None:
    """Check product-shell imports and package versions."""

    table = Table(title="XRTM Doctor")
    table.add_column("Package", style="cyan")
    table.add_column("Version", style="green")
    for package, package_version in package_versions().items():
        table.add_row(package, package_version)
    console.print(table)
    console.print("[green]Product shell imports are available.[/green]")


@cli.command()
@click.option("--provider", type=click.Choice(["mock", "local-llm"]), default="mock", show_default=True)
@click.option("--limit", type=int, default=2, show_default=True, help="Number of real corpus questions to run.")
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"), show_default=True)
@click.option("--base-url", default=None, help="OpenAI-compatible local endpoint for --provider local-llm.")
@click.option("--model", default=None, help="Local model id served by the endpoint.")
@click.option("--api-key", default=None, help="API key for the local endpoint; defaults to test/env.")
@click.option("--max-tokens", type=int, default=768, show_default=True)
@click.option("--no-report", is_flag=True, help="Skip static report.html generation.")
def demo(
    provider: str,
    limit: int,
    runs_dir: Path,
    base_url: str | None,
    model: str | None,
    api_key: str | None,
    max_tokens: int,
    no_report: bool,
) -> None:
    """Run a bounded local product demo over the real binary corpus."""

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
            command="xrtm demo",
        )
    )


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
def run_pipeline_command(
    provider: str,
    limit: int,
    runs_dir: Path,
    base_url: str | None,
    model: str | None,
    api_key: str | None,
    max_tokens: int,
    no_report: bool,
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
        )
    )


@cli.group()
def artifacts() -> None:
    """Inspect product run artifacts."""


@artifacts.command("inspect")
@click.argument("run_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
def artifacts_inspect(run_dir: Path) -> None:
    """Inspect a canonical run directory."""

    try:
        run_payload = ArtifactStore.read_run(run_dir)
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc
    table = Table(title=f"Run {run_payload.get('run_id', run_dir.name)}")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    for field in ("status", "provider", "command", "created_at", "updated_at"):
        table.add_row(field, str(run_payload.get(field, "")))
    artifacts_payload = run_payload.get("artifacts", {})
    table.add_row("artifacts", str(len(artifacts_payload)))
    summary = run_payload.get("summary", {})
    if summary:
        table.add_row("forecasts", str(summary.get("forecast_count", "")))
        table.add_row("warnings", str(summary.get("warning_count", "")))
        table.add_row("errors", str(summary.get("error_count", "")))
    console.print(table)


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


@cli.group("providers")
def providers_group() -> None:
    """Inspect and test inference providers."""


@providers_group.command("doctor")
@click.option("--base-url", default=None, help="OpenAI-compatible local endpoint to check.")
def providers_doctor(base_url: str | None) -> None:
    """Check configured provider availability."""

    status = local_llm_status(base_url=base_url)
    _print_local_llm_status(status)


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
    console.print(f"[green]Monitor started:[/green] {run.run_dir}")


@monitor_group.command("list")
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"), show_default=True)
def monitor_list(runs_dir: Path) -> None:
    """List monitor runs."""

    table = Table(title="XRTM Monitors")
    table.add_column("Run", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Watches", justify="right")
    table.add_column("Updated", style="dim")
    for monitor in list_monitors(runs_dir):
        table.add_row(monitor["run_dir"], str(monitor["status"]), str(monitor["watches"]), str(monitor["updated_at"]))
    console.print(table)


@monitor_group.command("show")
@click.argument("run_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
def monitor_show(run_dir: Path) -> None:
    """Show one monitor run."""

    try:
        monitor = load_monitor(run_dir)
    except FileNotFoundError as exc:
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
            str(watch.get("question_id")),
            str(watch.get("status")),
            str(len(trajectory)),
            str(latest),
        )
    console.print(Panel(f"Status: {monitor.get('status')}", title="Monitor State"))
    console.print(table)


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

    status = local_llm_status(base_url=base_url)
    _print_local_llm_status(status)
    if not status["healthy"]:
        raise click.ClickException(status["error"] or "Local LLM endpoint is not healthy")


@cli.group("report")
def report_group() -> None:
    """Generate reports from product artifacts."""


@report_group.command("html")
@click.argument("run_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
def report_html(run_dir: Path) -> None:
    """Generate a static HTML report for a run directory."""

    try:
        report_path = render_html_report(run_dir)
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc
    console.print(f"[green]Report written:[/green] {report_path}")


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
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", type=int, default=8765, show_default=True)
@click.option("--smoke", is_flag=True, help="Validate routes without blocking.")
def web(runs_dir: Path, host: str, port: int, smoke: bool) -> None:
    """Serve the local XRTM WebUI/dashboard."""

    if smoke:
        snapshot = web_snapshot(runs_dir)
        console.print(f"[green]WebUI smoke ok:[/green] {len(snapshot['runs'])} run(s)")
        return
    server = create_web_server(runs_dir=runs_dir, host=host, port=port)
    address, active_port = server.server_address
    console.print(f"[green]XRTM WebUI:[/green] http://{address}:{active_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping XRTM WebUI[/yellow]")
    finally:
        server.server_close()


def _run_pipeline_command(options: PipelineOptions) -> None:
    try:
        result = run_pipeline(options)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    table = Table(title="XRTM Pipeline")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Run", str(result.run.run_dir))
    table.add_row("Forecast records", str(result.forecast_records))
    table.add_row("Eval Brier", _format_optional_float(result.eval_brier_score))
    table.add_row("Train/backtest Brier", _format_optional_float(result.train_brier_score))
    table.add_row("Training samples", str(result.training_samples))
    table.add_row("Total seconds", f"{result.total_seconds:.3f}")
    console.print(table)
    console.print(f"[green]Artifacts:[/green] {result.run.run_dir}")


def _print_local_llm_status(status: dict) -> None:
    color = "green" if status["healthy"] else "red"
    lines = [
        f"Base URL: {status['base_url']}",
        f"Health URL: {status['health_url']}",
        f"Healthy: {status['healthy']}",
    ]
    if status["models"]:
        lines.append(f"Models: {', '.join(status['models'])}")
    if status["error"]:
        lines.append(f"Error: {status['error']}")
    console.print(Panel("\n".join(lines), title="Local LLM", border_style=color))


def _format_optional_float(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.6f}"


def _set_monitor_status_command(run_dir: Path, status: str) -> None:
    try:
        set_monitor_status(run_dir, status)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    console.print(f"[green]Monitor {status}:[/green] {run_dir}")


if __name__ == "__main__":
    cli()


__all__ = ["cli"]
