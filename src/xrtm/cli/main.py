"""Top-level XRTM product command."""

from __future__ import annotations

from pathlib import Path
from shlex import quote as shell_quote

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from xrtm.product.artifacts import ArtifactStore
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
    STARTER_PROFILE_LIMIT,
    ProfileStore,
    WorkflowProfile,
    starter_profile,
)
from xrtm.product.providers import local_llm_status
from xrtm.product.reports import render_html_report
from xrtm.product.tui import render_tui_once, run_tui
from xrtm.product.validation import (
    ValidationOptions,
    ValidationSafetyError,
    ValidationTierError,
    list_validation_corpora,
    prepare_validation_corpus,
    run_validation,
)
from xrtm.product.web import create_web_server, web_snapshot
from xrtm.version import __version__

console = Console()


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """XRTM local-first product cockpit."""


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
                    "Running the deterministic mock-provider demo now.",
                    "This first run stays fully local and offline by default.",
                ]
            ),
            title="Guided quickstart",
            border_style="blue",
        )
    )
    result = _execute_pipeline(
        PipelineOptions(
            provider="mock",
            limit=limit,
            runs_dir=runs_dir,
            write_report=True,
            command="xrtm start",
            user=user,
        )
    )
    _print_pipeline_result(result, title="XRTM Quickstart")
    _print_quickstart_summary(result, runs_dir=runs_dir)


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
            user=user,
        )
    )


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
    except (FileExistsError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    console.print(f"[green]Profile written:[/green] {path}")


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
    except (FileExistsError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    profiles_dir_arg = _profiles_dir_command_arg(profiles_dir)
    runs_dir_arg = _runs_dir_command_arg(runs_dir)
    lines = [
        f"Starter profile: {path}",
        f"Runs directory ready: {runs_dir}",
        f"Repeat this local workflow: xrtm run profile {name}{profiles_dir_arg}",
        f"Inspect the profile: xrtm profile show {name}{profiles_dir_arg}",
        f"Inspect the newest run later: xrtm runs show latest {runs_dir_arg}",
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

    try:
        profile = ProfileStore(profiles_dir).load(name)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    _run_pipeline_command(profile.to_pipeline_options(runs_dir=runs_dir))


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
    for name, status, location in _canonical_artifact_inventory(run_dir):
        artifact_table.add_row(name, status, location)
    console.print(artifact_table)


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

    _print_runs_table(list_run_history(runs_dir, status=status, provider=provider), title="XRTM Runs")


@runs_group.command("search")
@click.argument("query")
@click.option("--runs-dir", type=click.Path(file_okay=False, path_type=Path), default=Path("runs"), show_default=True)
@click.option("--status", default=None, help="Filter by run status.")
@click.option("--provider", default=None, help="Filter by provider.")
def runs_search(query: str, runs_dir: Path, status: str | None, provider: str | None) -> None:
    """Search run history by id, user, command, provider, or status."""

    _print_runs_table(list_run_history(runs_dir, status=status, provider=provider, query=query), title="XRTM Run Search")


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
    table = Table(title="XRTM Run Compare")
    table.add_column("Metric", style="cyan")
    table.add_column("Left", style="green")
    table.add_column("Right", style="yellow")
    for row in rows:
        table.add_row(str(row["metric"]), str(row["left"]), str(row["right"]))
    console.print(table)


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

    status = local_llm_status(base_url=base_url)
    _print_local_llm_status(status)


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
    
    try:
        report = run_validation(
            ValidationOptions(
                corpus_id=corpus_id,
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
        )
    except (ValidationTierError, ValidationSafetyError, ValueError, RuntimeError) as exc:
        raise click.ClickException(str(exc)) from exc
    
    # Display summary
    table = Table(title="XRTM Validation")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    corpus_info = report["corpus"]
    summary = report["summary"]
    
    table.add_row("Corpus", f"{corpus_info['name']} ({corpus_info['corpus_id']})")
    table.add_row("Tier", corpus_info["tier"])
    table.add_row("License", corpus_info["license"])
    table.add_row("Release-Gate", "✓" if corpus_info["release_gate_approved"] else "✗")
    table.add_row("Source Mode", corpus_info["source_mode"])
    table.add_row("Provider", report["configuration"]["provider"])
    table.add_row("Split", report["configuration"]["split"] or "full")
    table.add_row("Iterations", str(report["configuration"]["iterations"]))
    table.add_row("Total Forecasts", str(summary["total_forecasts"]))
    table.add_row("Duration", f"{summary['total_duration_seconds']:.2f}s")
    table.add_row("Throughput", f"{summary['forecasts_per_second']:.2f} forecasts/sec")
    
    if "artifact_path" in report:
        table.add_row("Artifact", str(report["artifact_path"]))
    
    console.print(table)
    
    # Display evaluation metrics if available
    eval_metrics = report.get("evaluation", {})
    if eval_metrics.get("mean_eval_brier") is not None:
        console.print(f"\n[cyan]Eval Brier Score:[/cyan] {eval_metrics['mean_eval_brier']:.4f}")
    if eval_metrics.get("mean_train_brier") is not None:
        console.print(f"[cyan]Train Brier Score:[/cyan] {eval_metrics['mean_train_brier']:.4f}")


@validate_group.command("list-corpora")
@click.option("--tier", type=click.Choice(["tier-1", "tier-2", "tier-3"]), default=None, help="Filter by tier.")
@click.option("--release-gate-only", is_flag=True, help="Show only release-gate approved corpora.")
def validate_list_corpora(tier: str | None, release_gate_only: bool) -> None:
    """List available validation corpora from the registry."""
    
    from xrtm.data.corpora import CorpusTier
    
    tier_enum = CorpusTier(tier) if tier else None
    corpora = list_validation_corpora(tier=tier_enum, release_gate_only=release_gate_only)
    
    if not corpora:
        console.print("[yellow]No corpora found matching the filter criteria.[/yellow]")
        return
    
    table = Table(title="Available Validation Corpora")
    table.add_column("Corpus ID", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Tier", style="yellow")
    table.add_column("License", style="green")
    table.add_column("Release-Gate", style="magenta")
    table.add_column("Bundled", style="blue")
    
    for corpus in corpora:
        table.add_row(
            corpus["corpus_id"],
            corpus["name"],
            corpus["tier"],
            corpus["license_type"],
            "✓" if corpus["release_gate_approved"] else "✗",
            "✓" if corpus["bundled"] else "✗",
        )
    
    console.print(table)


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

    try:
        report = prepare_validation_corpus(
            corpus_id,
            cache_root=cache_root,
            refresh=refresh,
            use_hf_datasets=not fixture_preview,
        )
    except (ImportError, ValueError, RuntimeError) as exc:
        raise click.ClickException(str(exc)) from exc

    corpus_info = report["corpus"]
    availability = report["availability"]

    table = Table(title="Prepared Validation Corpus")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Corpus", f"{corpus_info['name']} ({corpus_info['corpus_id']})")
    table.add_row("Tier", corpus_info["tier"])
    table.add_row("License", corpus_info["license"])
    table.add_row("Release-Gate", "✓" if corpus_info["release_gate_approved"] else "✗")
    table.add_row("Source Mode", availability["source_mode"])
    table.add_row("Cached", "✓" if availability["already_cached"] else "✗")
    if availability["record_count"] is not None:
        table.add_row("Records", str(availability["record_count"]))
    if availability["cache_root"] is not None:
        table.add_row("Cache Root", availability["cache_root"])
    if availability["manifest_path"] is not None:
        table.add_row("Manifest", availability["manifest_path"])
    console.print(table)

    if availability["source_mode"] == "preview":
        console.print(
            "[yellow]Preview cache active:[/yellow] this corpus is using the deterministic 3-record fixture. "
            "Re-run without --fixture-preview (and with --refresh if needed) to cache the full external dataset."
        )


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
    result = _execute_pipeline(options)
    _print_pipeline_result(result, title=_pipeline_result_title(options.command))
    _print_post_run_summary(
        result,
        runs_dir=options.runs_dir,
        success_title="Run complete",
        success_label=f"{options.command} completed",
        what_succeeded=_pipeline_success_details(write_report=options.write_report),
        write_report=options.write_report,
    )


def _execute_pipeline(options: PipelineOptions) -> PipelineResult:
    try:
        return run_pipeline(options)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


def _print_pipeline_result(result: PipelineResult, *, title: str = "XRTM Pipeline") -> None:
    table = Table(title=title)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Run id", result.run.run_id)
    table.add_row("Artifact dir", str(result.run.run_dir))
    report_path = result.run.artifacts.get("report.html")
    if report_path:
        table.add_row("Report", report_path)
    table.add_row("Forecast records", str(result.forecast_records))
    table.add_row("Eval Brier", _format_optional_float(result.eval_brier_score))
    table.add_row("Train/backtest Brier", _format_optional_float(result.train_brier_score))
    table.add_row("Training samples", str(result.training_samples))
    table.add_row("Total seconds", f"{result.total_seconds:.3f}")
    console.print(table)
    console.print(f"[green]Run artifacts ready:[/green] {result.run.run_dir}")


def _print_quickstart_summary(result: PipelineResult, *, runs_dir: Path) -> None:
    _print_post_run_summary(
        result,
        runs_dir=runs_dir,
        success_title="Quickstart complete",
        success_label="guided provider-free quickstart completed",
        what_succeeded="readiness checks, deterministic forecasts, scoring, backtest, and HTML report write",
        proof_line="Proof cue: the default provider-free XRTM path worked end-to-end on this machine.",
    )

    runs_dir_arg = _runs_dir_command_arg(runs_dir)
    role_lines = [
        f"Researcher / model-eval next command: xrtm demo --provider mock --limit 10 {runs_dir_arg}",
        f"Operator next command: xrtm profile starter my-local {runs_dir_arg}",
        f"Starter profile uses provider=mock, limit={STARTER_PROFILE_LIMIT}, and saves to {DEFAULT_PROFILES_DIR}.",
        f"Team export next command: xrtm runs export latest {runs_dir_arg} --output latest-run.json",
        "Developer / integrator next path: docs/python-api-reference.md and examples/integration/",
        "Optional later for local models: xrtm local-llm status",
    ]
    console.print(Panel("\n".join(role_lines), title="Role-based next paths", border_style="magenta"))


def _print_post_run_summary(
    result: PipelineResult,
    *,
    runs_dir: Path,
    success_title: str,
    success_label: str,
    what_succeeded: str,
    write_report: bool = True,
    proof_line: str | None = None,
) -> None:
    confirmed_artifacts = _confirm_post_run_artifacts(result.run.run_dir, require_report=write_report)
    summary = result.run.summary
    report_path = _artifact_path(confirmed_artifacts, "report.html")
    success_lines = [
        f"Succeeded: {success_label}.",
        f"What just succeeded: {what_succeeded}.",
    ]
    if proof_line:
        success_lines.append(proof_line)
    success_lines.extend(
        [
            f"Run id: {result.run.run_id}",
            f"Artifact location: {result.run.run_dir}",
            f"Report location: {report_path or 'not generated for this run'}",
            f"Forecasts: {summary.get('forecast_count', result.forecast_records)}",
            f"Warnings: {summary.get('warning_count', 0)} | Errors: {summary.get('error_count', 0)}",
            "Verified on disk: " + ", ".join(name for name, _ in confirmed_artifacts),
        ]
    )
    console.print(Panel("\n".join(success_lines), title=success_title, border_style="green"))

    runs_dir_arg = _runs_dir_command_arg(runs_dir)
    report_command = (
        f"Open/regenerate the report: xrtm report html --latest {runs_dir_arg}"
        if write_report
        else f"Generate the report now: xrtm report html --latest {runs_dir_arg}"
    )
    next_lines = [
        f"Inspect the newest run: xrtm runs show latest {runs_dir_arg}",
        f"Inspect artifacts: xrtm artifacts inspect --latest {runs_dir_arg}",
        report_command,
        f"Open the WebUI: xrtm web {runs_dir_arg}",
        f"Open the TUI: xrtm tui {runs_dir_arg}",
    ]
    console.print(Panel("\n".join(next_lines), title="Exact next commands", border_style="blue"))


def _pipeline_result_title(command: str) -> str:
    if command == "xrtm demo":
        return "XRTM Demo"
    if command.startswith("xrtm run profile "):
        return "XRTM Profile Run"
    return "XRTM Pipeline"


def _pipeline_success_details(*, write_report: bool) -> str:
    if write_report:
        return "forecast generation, scoring, backtest, and HTML report write completed for this run"
    return "forecast generation, scoring, and backtest completed for this run"


def _print_runs_table(runs: list[dict], *, title: str) -> None:
    table = Table(title=title)
    table.add_column("Run", style="cyan", width=26, no_wrap=True)
    table.add_column("Status", style="green")
    table.add_column("Provider")
    table.add_column("User")
    table.add_column("Forecasts", justify="right")
    table.add_column("Warnings", justify="right")
    table.add_column("Updated", style="dim", width=19)
    for run in runs:
        summary = run.get("summary", {})
        table.add_row(
            str(run.get("run_id")),
            str(run.get("status")),
            str(run.get("provider")),
            str(run.get("user") or ""),
            str(summary.get("forecast_count", "")),
            str(summary.get("warning_count", "")),
            str(run.get("updated_at")),
        )
    console.print(table)


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


def _profiles_dir_command_arg(profiles_dir: Path) -> str:
    if profiles_dir == DEFAULT_PROFILES_DIR:
        return ""
    return f" --profiles-dir {shell_quote(str(profiles_dir))}"


def _artifact_path(artifacts: list[tuple[str, Path]], name: str) -> Path | None:
    for artifact_name, path in artifacts:
        if artifact_name == name:
            return path
    return None


def _canonical_artifact_inventory(run_dir: Path) -> list[tuple[str, str, str]]:
    inventory: list[tuple[str, str, str]] = []
    for name in [
        "run.json",
        "questions.jsonl",
        "forecasts.jsonl",
        "eval.json",
        "train.json",
        "provider.json",
        "events.jsonl",
        "run_summary.json",
        "monitor.json",
        "report.html",
    ]:
        path = run_dir / name
        if path.exists():
            inventory.append((name, "present", str(path)))
        else:
            inventory.append((name, "missing", "not written for this run"))
    logs_dir = run_dir / "logs"
    if logs_dir.is_dir():
        inventory.append(("logs/", "present", str(logs_dir)))
    else:
        inventory.append(("logs/", "missing", "not created for this run"))
    return inventory


def _confirm_post_run_artifacts(run_dir: Path, *, require_report: bool) -> list[tuple[str, Path]]:
    required = [
        "run.json",
        "forecasts.jsonl",
        "eval.json",
        "train.json",
        "run_summary.json",
    ]
    if require_report:
        required.append("report.html")
    confirmed: list[tuple[str, Path]] = []
    missing: list[str] = []
    for name in required:
        path = run_dir / name
        if path.exists():
            confirmed.append((name, path))
        else:
            missing.append(name)
    if missing:
        raise click.ClickException(f"expected canonical run artifacts are missing: {', '.join(missing)}")
    return confirmed


def _runs_dir_command_arg(runs_dir: Path) -> str:
    return f"--runs-dir {shell_quote(runs_dir.as_posix())}"


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
