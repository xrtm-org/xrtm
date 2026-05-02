"""CLI presentation helpers for the XRTM product shell."""

from __future__ import annotations

from pathlib import Path
from shlex import quote as shell_quote
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from xrtm.product.pipeline import PipelineResult
from xrtm.product.profiles import DEFAULT_PROFILES_DIR, STARTER_PROFILE_LIMIT


def print_pipeline_result(console: Console, result: PipelineResult, *, title: str = "XRTM Pipeline") -> None:
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


def print_quickstart_summary(console: Console, result: PipelineResult, *, runs_dir: Path) -> None:
    print_post_run_summary(
        console,
        result,
        runs_dir=runs_dir,
        success_title="Quickstart complete",
        success_label="guided provider-free quickstart completed",
        what_succeeded="readiness checks, deterministic forecasts, scoring, backtest, and HTML report write",
        proof_line="Proof cue: the default provider-free XRTM path worked end-to-end on this machine.",
    )

    runs_dir_arg = runs_dir_command_arg(runs_dir)
    proof_point_lines = [
        "1. Provider-free first success: xrtm start (already proved above).",
        (
            "2. Benchmark and validation workflow: "
            "xrtm perf run --scenario provider-free-smoke --iterations 3 --limit 1 "
            "--runs-dir runs-perf --output performance.json"
        ),
        "   Follow with: xrtm validate run --provider mock --limit 10 --iterations 2 --runs-dir runs-validation",
        f"3. Monitoring, history, and report workflow: xrtm profile starter my-local {runs_dir_arg}",
        f"   Then: xrtm monitor start --provider mock --limit 2 {runs_dir_arg}",
        f"   Review/export: xrtm runs export latest {runs_dir_arg} --output latest-run.json",
        "4. Local-LLM advanced workflow: xrtm local-llm status",
        "   Then: xrtm demo --provider local-llm --limit 1 --max-tokens 768 --runs-dir runs-local",
        f"Starter profile uses provider=mock, limit={STARTER_PROFILE_LIMIT}, and saves to {DEFAULT_PROFILES_DIR}.",
        "Developer / integrator path: docs/python-api-reference.md and examples/integration/.",
    ]
    console.print(Panel("\n".join(proof_point_lines), title="Official proof-point workflows", border_style="magenta"))


def print_post_run_summary(
    console: Console,
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

    runs_dir_arg = runs_dir_command_arg(runs_dir)
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


def pipeline_result_title(command: str) -> str:
    if command == "xrtm demo":
        return "XRTM Demo"
    if command.startswith("xrtm run profile "):
        return "XRTM Profile Run"
    return "XRTM Pipeline"


def pipeline_success_details(*, write_report: bool) -> str:
    if write_report:
        return "forecast generation, scoring, backtest, and HTML report write completed for this run"
    return "forecast generation, scoring, and backtest completed for this run"


def print_runs_table(console: Console, runs: list[dict[str, Any]], *, title: str) -> None:
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


def print_local_llm_status(console: Console, status: dict[str, Any]) -> None:
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


def print_validation_report(console: Console, report: dict[str, Any]) -> None:
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

    eval_metrics = report.get("evaluation", {})
    if eval_metrics.get("mean_eval_brier") is not None:
        console.print(f"\n[cyan]Eval Brier Score:[/cyan] {eval_metrics['mean_eval_brier']:.4f}")
    if eval_metrics.get("mean_train_brier") is not None:
        console.print(f"[cyan]Train Brier Score:[/cyan] {eval_metrics['mean_train_brier']:.4f}")


def print_prepared_corpus_report(console: Console, report: dict[str, Any]) -> None:
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


def profiles_dir_command_arg(profiles_dir: Path) -> str:
    if profiles_dir == DEFAULT_PROFILES_DIR:
        return ""
    return f" --profiles-dir {shell_quote(str(profiles_dir))}"


def runs_dir_command_arg(runs_dir: Path) -> str:
    return f"--runs-dir {shell_quote(runs_dir.as_posix())}"


def canonical_artifact_inventory(run_dir: Path) -> list[tuple[str, str, str]]:
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


def _format_optional_float(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.6f}"


def _artifact_path(artifacts: list[tuple[str, Path]], name: str) -> Path | None:
    for artifact_name, path in artifacts:
        if artifact_name == name:
            return path
    return None


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


__all__ = [
    "canonical_artifact_inventory",
    "pipeline_result_title",
    "pipeline_success_details",
    "print_local_llm_status",
    "print_pipeline_result",
    "print_post_run_summary",
    "print_prepared_corpus_report",
    "print_quickstart_summary",
    "print_runs_table",
    "print_validation_report",
    "profiles_dir_command_arg",
    "runs_dir_command_arg",
]
