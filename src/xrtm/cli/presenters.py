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
from xrtm.product.profiles import DEFAULT_PROFILES_DIR


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
        prefer_latest_paths=True,
    )

    runs_dir_arg = runs_dir_command_arg(runs_dir)
    proof_point_lines = [
        "1. Provider-free first success: xrtm start (already proved above).",
        (
            "2. Benchmark and performance workflow: "
            "xrtm perf run --scenario provider-free-smoke --iterations 3 --limit 1 "
            "--runs-dir runs-perf --output performance.json"
        ),
        f"   Review the run above: xrtm runs show latest {runs_dir_arg}",
        f"   Inspect artifacts/report: xrtm artifacts inspect --latest {runs_dir_arg} && xrtm report html --latest {runs_dir_arg}",
        f"3. Monitoring, history, and report workflow: xrtm profile starter my-local {runs_dir_arg}",
        "   Then: xrtm run profile my-local",
        f"   Monitor/history: xrtm monitor start --provider mock --limit 2 {runs_dir_arg} && xrtm monitor list {runs_dir_arg}",
        (
            "   Compare/export: "
            f"xrtm runs compare <run-id-a> <run-id-b> {runs_dir_arg} && "
            f"xrtm runs export latest {runs_dir_arg} --output export.json && "
            f"xrtm runs export latest {runs_dir_arg} --output export.csv --format csv"
        ),
        "4. Local-LLM advanced workflow: xrtm local-llm status",
        "   Then: xrtm demo --provider local-llm --limit 1 --max-tokens 768 --runs-dir runs-local",
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
    prefer_latest_paths: bool = False,
) -> None:
    confirmed_artifacts = _confirm_post_run_artifacts(result.run.run_dir, require_report=write_report)
    summary = result.run.summary
    report_path = _artifact_path(confirmed_artifacts, "report.html")
    run_id = result.run.run_id
    run_dir_arg = shell_quote(result.run.run_dir.as_posix())
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
    if prefer_latest_paths:
        report_command = (
            f"Open/regenerate the report: xrtm report html --latest {runs_dir_arg}"
            if write_report
            else f"Generate the report now: xrtm report html --latest {runs_dir_arg}"
        )
        next_lines = [
            f"Review run history: xrtm runs list {runs_dir_arg}",
            f"Inspect the newest run: xrtm runs show latest {runs_dir_arg}",
            f"Inspect newest artifacts: xrtm artifacts inspect --latest {runs_dir_arg}",
            report_command,
            f"Open the WebUI: xrtm web {runs_dir_arg}",
            f"Open the TUI: xrtm tui {runs_dir_arg}",
        ]
    else:
        report_command = (
            f"Open/regenerate the report: xrtm report html {run_dir_arg}"
            if write_report
            else f"Generate the report now: xrtm report html {run_dir_arg}"
        )
        next_lines = [
            f"Review run history: xrtm runs list {runs_dir_arg}",
            f"Inspect this run: xrtm runs show {run_id} {runs_dir_arg}",
            f"Inspect artifacts: xrtm artifacts inspect {run_dir_arg}",
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


def print_run_compare(console: Console, rows: list[dict[str, Any]]) -> None:
    table = Table(title="XRTM Run Compare")
    table.add_column("Metric", style="cyan")
    table.add_column("Left", style="green")
    table.add_column("Right", style="yellow")
    table.add_column("Δ", justify="right")
    table.add_column("Interpretation", style="magenta")

    for row in rows:
        table.add_row(
            str(row["metric"]),
            _format_compare_value(row.get("left")),
            _format_compare_value(row.get("right")),
            _format_compare_value(row.get("delta")),
            str(row.get("interpretation") or ""),
        )
    console.print(table)
    console.print(
        Panel(
            "\n".join(
                [
                    "Compare best practice:",
                    "- Lower is better for Brier, ECE, runtime, warnings, and errors.",
                    "- Shared-question rows are the apples-to-apples quality check after a provider/model/prompt change.",
                    "- Export the winning run when you want notebook or spreadsheet follow-up.",
                ]
            ),
            title="Compare → learn loop",
            border_style="blue",
        )
    )


def print_available_corpora_table(console: Console, corpora: list[dict[str, Any]], *, title: str) -> None:
    table = Table(title=title)
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


def print_validation_report(console: Console, report: dict[str, Any], *, title: str = "XRTM Validation") -> None:
    table = Table(title=title)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    corpus_info = report["corpus"]
    configuration = report["configuration"]
    summary = report["summary"]

    table.add_row("Corpus", f"{corpus_info['name']} ({corpus_info['corpus_id']})")
    table.add_row("Tier", corpus_info["tier"])
    table.add_row("License", corpus_info["license"])
    table.add_row("Release-Gate", "✓" if corpus_info["release_gate_approved"] else "✗")
    table.add_row("Source Mode", corpus_info["source_mode"])
    table.add_row("Provider", configuration["provider"])
    table.add_row("Split", configuration["split"] or "full")
    table.add_row("Selected Questions", f"{configuration['selected_questions']} / {configuration['question_pool_size']}")
    table.add_row("Iterations", str(configuration["iterations"]))
    table.add_row("Total Forecasts", str(summary["total_forecasts"]))
    table.add_row("Duration", f"{summary['total_duration_seconds']:.2f}s")
    table.add_row("Throughput", f"{summary['forecasts_per_second']:.2f} forecasts/sec")

    if "artifact_path" in report:
        table.add_row("Artifact", str(report["artifact_path"]))

    console.print(table)

    eval_metrics = report.get("evaluation", {})
    if eval_metrics.get("mean_eval_brier") is not None:
        console.print(f"\n[cyan]Eval Brier Score:[/cyan] {eval_metrics['mean_eval_brier']:.4f}")
    if eval_metrics.get("mean_eval_ece") is not None:
        console.print(f"[cyan]Eval ECE:[/cyan] {eval_metrics['mean_eval_ece']:.4f}")
    if eval_metrics.get("mean_train_brier") is not None:
        console.print(f"[cyan]Train Brier Score:[/cyan] {eval_metrics['mean_train_brier']:.4f}")

    compare_pair = _validation_compare_pair(report.get("iterations", []))
    compare_hint = (
        f"xrtm runs compare {compare_pair[0]} {compare_pair[1]} --runs-dir {configuration['runs_dir']}"
        if compare_pair
        else "Re-run validation after a provider/model change, then compare the new run against this baseline."
    )
    best_run_id = eval_metrics.get("best_eval_run_id")
    export_hint = (
        f"xrtm runs export {best_run_id} --runs-dir {configuration['runs_dir']} --output export.json"
        if best_run_id
        else "xrtm runs export <run-id> --runs-dir runs-validation --output export.json"
    )
    assessment_lines = [
        "How to read this:",
        "- Brier lower is better; 0.000 is perfect and ~0.250 is the balanced 50/50 binary baseline.",
        "- ECE lower is better; values near 0 mean your confidence matches observed frequency.",
    ]
    if eval_metrics.get("eval_brier_spread") is not None:
        assessment_lines.append(
            f"- Iteration stability: Brier spread {eval_metrics['eval_brier_spread']:.4f} across {configuration['iterations']} run(s)."
        )
    if best_run_id:
        assessment_lines.append(f"- Current baseline run: {best_run_id}")
    assessment_lines.extend(
        [
            "",
            "Next concrete steps:",
            f"1. Compare runs: {compare_hint}",
            f"2. Export the current best run: {export_hint}",
            "3. Change provider/model/prompt settings, re-run validation, and use shared-question rows to judge improvement.",
        ]
    )
    console.print(Panel("\n".join(assessment_lines), title="Benchmark → compare → improve", border_style="magenta"))


def print_prepared_corpus_report(
    console: Console,
    report: dict[str, Any],
    *,
    title: str = "Prepared Validation Corpus",
) -> None:
    corpus_info = report["corpus"]
    availability = report["availability"]

    table = Table(title=title)
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


def print_benchmark_compare_report(console: Console, report: dict[str, Any]) -> None:
    benchmark = report["benchmark"]
    comparison = report["comparison"]
    table = Table(title="XRTM Benchmark Compare")
    table.add_column("Metric", style="cyan")
    table.add_column("Baseline", style="green")
    table.add_column("Candidate", style="yellow")
    table.add_column("Delta", justify="right")
    table.add_row("Corpus", benchmark["corpus_id"], benchmark["corpus_id"], "-")
    table.add_row("Split", benchmark["split"], benchmark["split"], "-")
    table.add_row(
        "Eval Brier",
        _format_optional_float(comparison["baseline_primary_score"]),
        _format_optional_float(comparison["candidate_primary_score"]),
        _format_optional_float(comparison["delta_primary_score"]),
    )
    table.add_row(
        "Eval ECE",
        _format_optional_float(comparison.get("baseline_eval_ece")),
        _format_optional_float(comparison.get("candidate_eval_ece")),
        _format_optional_float(comparison.get("delta_eval_ece")),
    )
    table.add_row(
        "Reliability",
        _format_optional_float(comparison.get("baseline_reliability")),
        _format_optional_float(comparison.get("candidate_reliability")),
        _format_optional_float(comparison.get("delta_reliability")),
    )
    table.add_row(
        "Resolution",
        _format_optional_float(comparison.get("baseline_resolution")),
        _format_optional_float(comparison.get("candidate_resolution")),
        _format_optional_float(comparison.get("delta_resolution")),
    )
    console.print(table)

    baseline_run_id = report["baseline"]["run_ids"][0] if report["baseline"]["run_ids"] else None
    candidate_run_id = report["candidate"]["run_ids"][0] if report["candidate"]["run_ids"] else None
    lines = [
        f"Frozen split signature: {benchmark['split_signature'] or 'none'}",
        f"Selected questions: {benchmark['selected_questions']} / {benchmark['question_pool_size']}",
        f"Candidate beats baseline: {comparison['candidate_beats_baseline']}",
        f"Cohorts compared: {len(comparison.get('cohort_deltas', {}))}",
    ]
    if "artifact_path" in report:
        lines.append(f"Compare artifact: {report['artifact_path']}")
    runs_dir = report["baseline"]["spec"].get("metadata", {}).get("runs_dir")
    if baseline_run_id and candidate_run_id and runs_dir:
        lines.append(f"Run-level diff: xrtm runs compare {baseline_run_id} {candidate_run_id} --runs-dir {runs_dir}")
    console.print(Panel("\n".join(lines), title="Rigorous compare loop", border_style="magenta"))


def print_benchmark_stress_report(console: Console, report: dict[str, Any]) -> None:
    spec = report["spec"]
    comparison = report.get("comparison") or {}
    arm_table = Table(title="XRTM Benchmark Stress Suite")
    arm_table.add_column("Arm", style="cyan")
    arm_table.add_column("Provider", style="green")
    arm_table.add_column("Repeats", justify="right")
    arm_table.add_column("Mean Eval Brier", justify="right")
    arm_table.add_column("Mean Eval ECE", justify="right")
    arm_table.add_column("Mean Duration (s)", justify="right")
    arm_table.add_column("Forecasts / sec", justify="right")
    arm_table.add_column("Mean Tokens", justify="right")
    for arm_result in report["arm_results"]:
        score_summary = arm_result["score_summary"]
        systems = arm_result.get("systems_summary", {})
        arm_table.add_row(
            arm_result["arm"]["display_name"],
            arm_result["arm"]["provider"],
            str(len(arm_result.get("runs", []))),
            _format_optional_float(score_summary.get("primary_score")),
            _format_optional_float(score_summary.get("calibration_error")),
            _format_optional_float(systems.get("mean_duration_seconds")),
            _format_optional_float(systems.get("mean_forecasts_per_second")),
            _format_optional_float(systems.get("mean_total_tokens")),
        )
    console.print(arm_table)

    rows = comparison.get("rows", [])
    if rows:
        compare_table = Table(title="Stress-suite deltas vs baseline")
        compare_table.add_column("Metric", style="cyan")
        compare_table.add_column("Candidate", style="yellow")
        compare_table.add_column("Baseline", style="green")
        compare_table.add_column("Delta", justify="right")
        compare_table.add_column("Interpretation", style="magenta")
        for row in rows:
            compare_table.add_row(
                row["metric_name"],
                f"{row['candidate_system_id']}={_format_optional_float(row.get('candidate_value'))}",
                f"{row['baseline_system_id']}={_format_optional_float(row.get('baseline_value'))}",
                _format_optional_float(row.get("delta")),
                row["interpretation"],
            )
        console.print(compare_table)

    lines = [
        f"Frozen split signature: {spec.get('split_signature') or 'none'}",
        f"Selected questions: {spec['run_limit']}",
        f"Repeat count: {spec['repeat_count']}",
        f"Baseline arm: {spec.get('baseline_arm_id') or 'none'}",
    ]
    if "artifact_path" in report:
        lines.append(f"Stress artifact: {report['artifact_path']}")
    console.print(Panel("\n".join(lines), title="Stress review loop", border_style="magenta"))


def profiles_dir_command_arg(profiles_dir: Path) -> str:
    if profiles_dir == DEFAULT_PROFILES_DIR:
        return ""
    return f" --profiles-dir {shell_quote(str(profiles_dir))}"


def runs_dir_command_arg(runs_dir: Path) -> str:
    return f"--runs-dir {shell_quote(runs_dir.as_posix())}"


def _validation_compare_pair(iterations: list[dict[str, Any]]) -> tuple[str, str] | None:
    run_ids = [str(item.get("run_id")) for item in iterations if item.get("run_id")]
    if len(run_ids) >= 2:
        return run_ids[0], run_ids[-1]
    return None


def _format_compare_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


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
    "print_available_corpora_table",
    "print_benchmark_compare_report",
    "print_benchmark_stress_report",
    "print_post_run_summary",
    "print_prepared_corpus_report",
    "print_quickstart_summary",
    "print_runs_table",
    "print_validation_report",
    "profiles_dir_command_arg",
    "runs_dir_command_arg",
]
