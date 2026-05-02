import csv
import json
import re
from pathlib import Path
from threading import Thread
from unittest.mock import patch
from urllib.request import urlopen

from click.testing import CliRunner

from xrtm.cli.main import cli
from xrtm.product.history import resolve_run_dir
from xrtm.product.monitoring import run_monitor_once
from xrtm.product.profiles import STARTER_PROFILE_LIMIT, WorkflowProfile
from xrtm.product.web import create_web_server, web_snapshot

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_PACKAGE_VERSIONS = {
    "xrtm": "0.3.0",
    "xrtm-data": "0.2.5",
    "xrtm-eval": "0.2.5",
    "xrtm-forecast": "0.6.6",
    "xrtm-train": "0.2.6",
}


def _write_canonical_run_fixture(runs_dir: Path, run_id: str, *, user: str | None = None) -> Path:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True)
    run_payload = {
        "run_id": run_id,
        "status": "completed",
        "provider": "mock",
        "command": "xrtm demo --provider mock --limit 1",
        "created_at": "2026-05-01T10:00:00+00:00",
        "updated_at": "2026-05-01T10:00:30+00:00",
        "user": user,
        "artifacts": {"run.json": str(run_dir / "run.json")},
        "summary": {"forecast_count": 1, "warning_count": 0, "error_count": 0},
    }
    (run_dir / "run.json").write_text(json.dumps(run_payload), encoding="utf-8")
    (run_dir / "run_summary.json").write_text(
        json.dumps({"forecast_count": 1, "warning_count": 0, "error_count": 0}),
        encoding="utf-8",
    )
    (run_dir / "events.jsonl").write_text("", encoding="utf-8")
    (run_dir / "forecasts.jsonl").write_text(
        json.dumps({"question_id": "q1", "probability": 0.6, "reasoning": "fixture"}) + "\n",
        encoding="utf-8",
    )
    return run_dir


def test_help_exposes_product_commands() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "start" in result.output
    assert "doctor" in result.output
    assert "demo" in result.output
    assert "artifacts" in result.output
    assert "profile" in result.output
    assert "runs" in result.output
    assert "perf" in result.output
    assert "validate" in result.output
    assert "local-llm" in result.output
    assert "monitor" in result.output
    assert "tui" in result.output
    assert "web" in result.output


def test_provider_free_demo_writes_canonical_artifacts() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["demo", "--provider", "mock", "--limit", "1", "--runs-dir", "runs"])

        assert result.exit_code == 0, result.output
        run_dirs = list(Path("runs").iterdir())
        assert len(run_dirs) == 1
        run_dir = run_dirs[0]
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
            assert (run_dir / name).exists(), name
        summary = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
        events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
        assert summary["schema_version"] == "xrtm.run-summary.v1"
        assert summary["forecast_count"] == 1
        assert summary["token_counts"]["total_tokens"] > 0
        assert {event["event_type"] for event in events} >= {
            "run_started",
            "provider_request_started",
            "provider_request_completed",
            "forecast_written",
            "eval_completed",
            "train_completed",
            "run_completed",
        }


def test_start_guides_newcomers_through_provider_free_first_run() -> None:
    runner = CliRunner()
    local_status = {
        "base_url": "http://127.0.0.1:8000/v1",
        "health_url": "http://127.0.0.1:8000/health",
        "models_url": "http://127.0.0.1:8000/v1/models",
        "healthy": False,
        "models": [],
        "gpu": {"available": False},
        "error": "connection refused",
    }

    with runner.isolated_filesystem():
        with patch("xrtm.product.doctor.package_versions", return_value=_PACKAGE_VERSIONS), patch(
            "xrtm.product.doctor.local_llm_status", return_value=local_status
        ):
            result = runner.invoke(cli, ["start", "--runs-dir", "runs"])

        output = _strip_ansi(result.output)
        assert result.exit_code == 0, output
        run_dir = next(Path("runs").iterdir())
        run_metadata = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        assert run_metadata["command"] == "xrtm start"
        assert "Readiness checks passed." in output
        assert "Running the deterministic mock-provider demo now." in output
        assert "Succeeded: guided provider-free quickstart completed." in output
        assert "What just succeeded:" in output
        for phrase in ["readiness checks", "deterministic forecasts", "scoring", "backtest", "HTML report write"]:
            assert phrase in output
        for phrase in ["Proof cue:", "provider-free XRTM path"]:
            assert phrase in output
        assert f"Run id: {run_dir.name}" in output
        assert f"Artifact location: {run_dir}" in output
        assert f"Report location: {run_dir / 'report.html'}" in output
        assert "Verified on disk:" in output
        for artifact_name in ["run.json", "forecasts.jsonl", "eval.json", "train.json", "run_summary.json", "report.html"]:
            assert artifact_name in output
        assert "xrtm runs show latest --runs-dir runs" in output
        assert "xrtm artifacts inspect --latest --runs-dir runs" in output
        assert "Open/regenerate the report: xrtm report html --latest --runs-dir runs" in output
        assert "xrtm web --runs-dir runs" in output
        assert "xrtm tui --runs-dir runs" in output
        assert "Official proof-point workflows" in output
        assert "Provider-free first success" in output
        assert "Benchmark and validation workflow" in output
        assert "Monitoring, history, and report workflow" in output
        assert "Local-LLM advanced workflow" in output
        for phrase in ["provider-free-smoke", "performance.json", "runs-validation"]:
            assert phrase in output
        assert "xrtm validate run --provider mock --limit 10 --iterations 2" in output
        for phrase in ["xrtm profile starter my-local", "my-local", "--runs-dir runs"]:
            assert phrase in output
        for phrase in ["xrtm monitor start", "latest-run.json", "xrtm runs export latest"]:
            assert phrase in output
        assert "xrtm local-llm status" in output
        assert f"limit={STARTER_PROFILE_LIMIT}" in output
        assert "docs/python-api-reference.md" in output


def test_demo_prints_run_success_proof_and_next_commands() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["demo", "--provider", "mock", "--limit", "1", "--runs-dir", "runs"])

        output = _strip_ansi(result.output)
        assert result.exit_code == 0, output
        run_dir = next(Path("runs").iterdir())
        assert "XRTM Demo" in output
        assert f"Run id: {run_dir.name}" in output
        assert f"Artifact location: {run_dir}" in output
        assert f"Report location: {run_dir / 'report.html'}" in output
        assert "Succeeded: xrtm demo completed." in output
        assert "What just succeeded:" in output
        for phrase in ["forecast generation", "scoring", "backtest", "HTML report", "completed for this run"]:
            assert phrase in output
        assert "Verified on disk:" in output
        for artifact_name in ["run.json", "forecasts.jsonl", "eval.json", "train.json", "run_summary.json", "report.html"]:
            assert artifact_name in output
        assert "xrtm runs show latest --runs-dir runs" in output
        assert "xrtm artifacts inspect --latest --runs-dir runs" in output
        assert "Open/regenerate the report: xrtm report html --latest --runs-dir runs" in output
        assert "xrtm web --runs-dir runs" in output
        assert "xrtm tui --runs-dir runs" in output


def test_profile_starter_scaffolds_repeatable_local_workspace() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            [
                "profile",
                "starter",
                "my-local",
                "--profiles-dir",
                "profiles",
                "--runs-dir",
                "starter-runs",
                "--user",
                "team-alpha",
            ],
        )
        run = runner.invoke(cli, ["run", "profile", "my-local", "--profiles-dir", "profiles"])

        assert result.exit_code == 0, result.output
        assert Path("starter-runs").is_dir()
        profile_payload = json.loads(Path("profiles/my-local.json").read_text(encoding="utf-8"))
        assert profile_payload["provider"] == "mock"
        assert profile_payload["limit"] == STARTER_PROFILE_LIMIT
        assert profile_payload["runs_dir"] == "starter-runs"
        assert profile_payload["user"] == "team-alpha"
        cleaned = _ANSI_RE.sub("", result.output)
        assert "xrtm run profile my-local" in cleaned
        assert "--profiles-dir profiles" in cleaned
        assert "xrtm runs show latest --runs-dir starter-runs" in cleaned
        assert run.exit_code == 0, run.output
        assert next(Path("starter-runs").iterdir()).is_dir()


def test_user_attribution_appears_in_run_artifact_and_csv_export() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["demo", "--provider", "mock", "--limit", "1", "--runs-dir", "runs", "--user", "alice"])

        assert result.exit_code == 0, result.output
        run_dirs = list(Path("runs").iterdir())
        assert len(run_dirs) == 1
        run_dir = run_dirs[0]
        run_id = run_dir.name

        # Check run.json contains user
        run_metadata = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        assert run_metadata["user"] == "alice"

        # Check CSV export includes user column
        export_result = runner.invoke(cli, ["runs", "export", run_id, "--runs-dir", "runs", "--output", "export.csv", "--format", "csv"])
        assert export_result.exit_code == 0, export_result.output
        csv_content = Path("export.csv").read_text(encoding="utf-8")
        assert "user" in csv_content
        assert "alice" in csv_content

        # Check JSON export includes user
        json_export_result = runner.invoke(cli, ["runs", "export", run_id, "--runs-dir", "runs", "--output", "export.json"])
        assert json_export_result.exit_code == 0, json_export_result.output
        exported_json = json.loads(Path("export.json").read_text(encoding="utf-8"))
        assert exported_json["run"]["user"] == "alice"


def test_csv_export_flattens_nested_forecast_fields_and_run_timestamps() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["demo", "--provider", "mock", "--limit", "1", "--runs-dir", "runs", "--user", "alice"])

        assert result.exit_code == 0, result.output
        run_dir = next(Path("runs").iterdir())
        run_metadata = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))

        export_result = runner.invoke(cli, ["runs", "export", "latest", "--runs-dir", "runs", "--output", "export.csv", "--format", "csv"])
        assert export_result.exit_code == 0, export_result.output

        with Path("export.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))

        assert rows
        row = rows[0]
        assert row["user"] == "alice"
        assert row["started_at"] == run_metadata["created_at"]
        assert row["completed_at"] == run_metadata["updated_at"]
        assert row["forecast_probability"]
        assert row["forecast_reasoning"]
        assert row["tokens_used"]


def test_user_attribution_is_optional_and_backward_compatible() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        # Run without user attribution
        result = runner.invoke(cli, ["demo", "--provider", "mock", "--limit", "1", "--runs-dir", "runs"])

        assert result.exit_code == 0, result.output
        run_dirs = list(Path("runs").iterdir())
        assert len(run_dirs) == 1
        run_dir = run_dirs[0]

        # Check run.json has user as null
        run_metadata = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        assert run_metadata.get("user") is None


def test_artifacts_inspect_requires_run_json() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        Path("not-a-run").mkdir()
        result = runner.invoke(cli, ["artifacts", "inspect", "not-a-run"])

        assert result.exit_code != 0
        assert "run.json" in result.output


def test_artifacts_inspect_lists_canonical_inventory_for_first_run_review() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["demo", "--provider", "mock", "--limit", "1", "--runs-dir", "runs"])
        assert result.exit_code == 0, result.output

        inspect = runner.invoke(cli, ["artifacts", "inspect", "--latest", "--runs-dir", "runs"])

        cleaned = _ANSI_RE.sub("", inspect.output)
        latest = next(Path("runs").iterdir())
        assert inspect.exit_code == 0, inspect.output
        assert "Canonical artifact inventory" in cleaned
        assert str(latest) in cleaned
        for artifact_name in ["run.json", "questions.jsonl", "provider.json", "report.html", "logs/"]:
            assert artifact_name in cleaned
            assert "present" in cleaned


def test_performance_harness_writes_structured_report_and_budget_failures() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            [
                "perf",
                "run",
                "--scenario",
                "provider-free-smoke",
                "--iterations",
                "2",
                "--limit",
                "1",
                "--runs-dir",
                "runs-perf",
                "--output",
                "perf.json",
                "--max-mean-seconds",
                "60",
            ],
        )
        report = json.loads(Path("perf.json").read_text(encoding="utf-8"))
        failure = runner.invoke(
            cli,
            [
                "perf",
                "run",
                "--iterations",
                "1",
                "--limit",
                "1",
                "--runs-dir",
                "runs-perf-fail",
                "--output",
                "perf-fail.json",
                "--max-mean-seconds",
                "0.000001",
                "--fail-on-budget",
            ],
        )

        assert result.exit_code == 0, result.output
        assert report["schema_version"] == "xrtm.performance.v1"
        assert report["scenario"] == "provider-free-smoke"
        assert report["provider"] == "mock"
        assert report["iterations"] == 2
        assert report["limit"] == 1
        assert report["runs_dir"] == "runs-perf"
        assert len(report["samples"]) == 2
        assert {
            "iteration",
            "run_id",
            "run_dir",
            "duration_seconds",
            "forecast_records",
            "training_samples",
            "eval_brier_score",
            "train_brier_score",
        } <= set(report["samples"][0])
        assert report["samples"][0]["iteration"] == 1
        assert report["samples"][0]["forecast_records"] == 1
        assert report["summary"]["total_seconds"] > 0
        assert report["summary"]["mean_seconds"] > 0
        assert report["summary"]["max_seconds"] > 0
        assert report["summary"]["p95_seconds"] > 0
        assert report["summary"]["forecast_records"] == 2
        assert report["summary"]["forecasts_per_second"] > 0
        assert report["budget"]["status"] == "passed"
        assert report["budget"]["max_mean_seconds"] == 60  # explicit override
        assert report["budget"]["max_p95_seconds"] == 0.1  # default budget applied
        assert report["budget"]["budgets_applied"] is True
        assert report["budget"]["violations"] == []
        assert failure.exit_code != 0
        assert "exceeded budget" in failure.output


def test_performance_harness_p95_scale_and_safety_gates() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        scale = runner.invoke(
            cli,
            [
                "perf",
                "run",
                "--scenario",
                "provider-free-scale",
                "--iterations",
                "1",
                "--limit",
                "1",
                "--runs-dir",
                "runs-scale",
                "--output",
                "scale.json",
            ],
        )
        p95_failure = runner.invoke(
            cli,
            [
                "perf",
                "run",
                "--iterations",
                "1",
                "--limit",
                "1",
                "--runs-dir",
                "runs-p95",
                "--output",
                "p95.json",
                "--max-p95-seconds",
                "0.000001",
                "--fail-on-budget",
            ],
        )
        absolute_output = runner.invoke(
            cli,
            [
                "perf",
                "run",
                "--iterations",
                "1",
                "--limit",
                "1",
                "--runs-dir",
                "runs",
                "--output",
                str(Path.cwd() / "absolute.json"),
            ],
        )
        traversal_runs = runner.invoke(
            cli,
            [
                "perf",
                "run",
                "--iterations",
                "1",
                "--limit",
                "1",
                "--runs-dir",
                "../runs",
                "--output",
                "perf.json",
            ],
        )
        too_many_iterations = runner.invoke(
            cli,
            ["perf", "run", "--iterations", "101", "--limit", "1", "--runs-dir", "runs", "--output", "perf.json"],
        )

        assert scale.exit_code == 0, scale.output
        scale_report = json.loads(Path("scale.json").read_text(encoding="utf-8"))
        assert scale_report["scenario"] == "provider-free-scale"
        assert scale_report["provider"] == "mock"
        assert p95_failure.exit_code != 0
        assert "p95_seconds" in p95_failure.output
        assert "exceeded budget" in p95_failure.output
        assert absolute_output.exit_code != 0
        assert "output must be a relative path" in absolute_output.output
        assert traversal_runs.exit_code != 0
        assert "runs_dir may not contain '..'" in traversal_runs.output
        assert too_many_iterations.exit_code != 0
        assert "iterations must be at most 100" in too_many_iterations.output


def test_validation_commands_use_corpus_registry_and_split_selection() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        listed = runner.invoke(cli, ["validate", "list-corpora", "--release-gate-only"])
        run = runner.invoke(
            cli,
            [
                "validate",
                "run",
                "--corpus-id",
                "xrtm-real-binary-v1",
                "--split",
                "held-out",
                "--provider",
                "mock",
                "--limit",
                "10",
                "--iterations",
                "1",
                "--runs-dir",
                "runs-validation",
                "--output-dir",
                ".cache/validation",
            ],
        )
        listed_output = _ANSI_RE.sub("", listed.output)

        assert listed.exit_code == 0, listed.output
        assert "Available Validation Corpora" in listed_output
        assert "tier-1" in listed_output
        assert "apache-2.0" in listed_output
        assert run.exit_code == 0, run.output
        assert "held-out" in run.output
        artifacts = list(Path(".cache/validation").glob("validation-xrtm-real-binary-v1-*.json"))
        assert len(artifacts) == 1
        report = json.loads(artifacts[0].read_text(encoding="utf-8"))
        assert report["configuration"]["split"] == "held-out"
        assert report["configuration"]["selected_questions"] >= 1
        assert report["summary"]["total_forecasts"] == report["configuration"]["selected_questions"]


def test_validate_prepare_corpus_supports_preview_cache() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            [
                "validate",
                "prepare-corpus",
                "--corpus-id",
                "forecast-v1",
                "--fixture-preview",
                "--cache-root",
                "corpora",
            ],
        )

        assert result.exit_code == 0, result.output
        cleaned = _ANSI_RE.sub("", result.output)
        assert "Prepared Validation Corpus" in cleaned
        assert "preview" in cleaned.lower()
        assert Path("corpora/forecast-v1/1.0/manifest.json").exists()


def test_profiles_and_run_history_commands_support_repeatable_workflows() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        create = runner.invoke(
            cli,
            [
                "profile",
                "create",
                "local-mock",
                "--provider",
                "mock",
                "--limit",
                "1",
                "--runs-dir",
                "runs",
                "--user",
                "team-alpha",
                "--profiles-dir",
                "profiles",
            ],
        )
        profile_list = runner.invoke(cli, ["profile", "list", "--profiles-dir", "profiles"])
        profile_show = runner.invoke(cli, ["profile", "show", "local-mock", "--profiles-dir", "profiles"])
        run = runner.invoke(cli, ["run", "profile", "local-mock", "--profiles-dir", "profiles"])
        run_dir = next(Path("runs").iterdir())
        run_id = run_dir.name
        runs_list = runner.invoke(cli, ["runs", "list", "--runs-dir", "runs"])
        runs_search = runner.invoke(cli, ["runs", "search", "team-alpha", "--runs-dir", "runs"])
        runs_show = runner.invoke(cli, ["runs", "show", run_id, "--runs-dir", "runs"])
        runs_export_json = runner.invoke(cli, ["runs", "export", run_id, "--runs-dir", "runs", "--output", "export.json"])
        runs_export_csv = runner.invoke(
            cli, ["runs", "export", run_id, "--runs-dir", "runs", "--output", "export.csv", "--format", "csv"]
        )

        assert create.exit_code == 0, create.output
        assert profile_list.exit_code == 0, profile_list.output
        assert "local-mock" in profile_list.output
        assert profile_show.exit_code == 0, profile_show.output
        assert "team-alpha" in profile_show.output
        assert run.exit_code == 0, run.output
        assert runs_list.exit_code == 0, runs_list.output
        assert run_id in runs_list.output
        assert runs_search.exit_code == 0, runs_search.output
        assert run_id in runs_search.output
        assert runs_show.exit_code == 0, runs_show.output
        assert "forecasts" in runs_show.output
        assert "team-alpha" in runs_show.output
        assert runs_export_json.exit_code == 0, runs_export_json.output
        exported_json = json.loads(Path("export.json").read_text(encoding="utf-8"))
        assert exported_json["run"]["run_id"] == run_id
        assert exported_json["run"]["user"] == "team-alpha"
        assert runs_export_csv.exit_code == 0, runs_export_csv.output
        csv_content = Path("export.csv").read_text(encoding="utf-8")
        assert "run_id" in csv_content
        assert "user" in csv_content
        assert "forecast_probability" in csv_content
        assert run_id in csv_content
        assert "team-alpha" in csv_content


def test_runs_compare_and_web_filters() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        first = runner.invoke(cli, ["demo", "--provider", "mock", "--limit", "1", "--runs-dir", "runs", "--user", "alice"])
        second = runner.invoke(cli, ["demo", "--provider", "mock", "--limit", "1", "--runs-dir", "runs", "--user", "bob"])
        run_ids = sorted(path.name for path in Path("runs").iterdir())
        compare = runner.invoke(cli, ["runs", "compare", run_ids[0], run_ids[1], "--runs-dir", "runs"])
        snapshot = web_snapshot(Path("runs"), provider="mock", query=run_ids[0])

        assert first.exit_code == 0, first.output
        assert second.exit_code == 0, second.output
        assert compare.exit_code == 0, compare.output
        assert "forecast_count" in compare.output
        assert "user" in compare.output
        assert "alice" in compare.output
        assert "bob" in compare.output
        assert len(snapshot["runs"]) == 1
        assert snapshot["runs"][0]["run_id"] == run_ids[0]


def test_run_history_rejects_paths_outside_runs_dir() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        outside = Path("outside")
        outside.mkdir()
        Path("runs").mkdir()
        result = runner.invoke(cli, ["runs", "show", str(outside.resolve()), "--runs-dir", "runs"])

        assert result.exit_code != 0
        assert "invalid run reference" in result.output
        try:
            resolve_run_dir(Path("runs"), str(outside.resolve()))
        except ValueError as exc:
            assert "invalid run reference" in str(exc)
        else:
            raise AssertionError("absolute path should be rejected")


def test_latest_run_shortcuts_cover_common_inspection_flows() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        runs_dir = Path("runs")
        _write_canonical_run_fixture(runs_dir, "20260501T101710Z-d8967e54", user="alice")
        latest = _write_canonical_run_fixture(runs_dir, "20260501T101711Z-e50ac5f1", user="bob")

        runs_show = runner.invoke(cli, ["runs", "show", "latest", "--runs-dir", "runs"])
        artifacts_inspect = runner.invoke(cli, ["artifacts", "inspect", "--latest", "--runs-dir", "runs"])
        report = runner.invoke(cli, ["report", "html", "--latest", "--runs-dir", "runs"])

        assert resolve_run_dir(runs_dir, "latest") == latest
        assert runs_show.exit_code == 0, runs_show.output
        assert latest.name in runs_show.output
        assert "bob" in runs_show.output
        assert artifacts_inspect.exit_code == 0, artifacts_inspect.output
        assert latest.name in artifacts_inspect.output
        assert "Canonical artifact inventory" in artifacts_inspect.output
        assert "run.json" in artifacts_inspect.output
        assert report.exit_code == 0, report.output
        assert str(latest / "report.html") in report.output


def test_latest_run_shortcuts_surface_help_and_errors() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        _write_canonical_run_fixture(Path("runs"), "20260501T101710Z-d8967e54")
        help_result = runner.invoke(cli, ["artifacts", "inspect", "--help"])
        missing_latest = runner.invoke(cli, ["runs", "show", "latest", "--runs-dir", "empty-runs"])
        conflict = runner.invoke(
            cli,
            ["report", "html", "runs/20260501T101710Z-d8967e54", "--latest", "--runs-dir", "runs"],
        )

        assert help_result.exit_code == 0, help_result.output
        assert "--latest" in help_result.output
        assert "used with --latest" in help_result.output
        assert missing_latest.exit_code != 0
        assert "no canonical runs found under empty-runs" in missing_latest.output
        assert conflict.exit_code != 0
        assert "pass either RUN_DIR or --latest, not both" in conflict.output


def test_invalid_profile_names_are_rejected() -> None:
    for name in [".", "..", "bad/name", "bad\\name", "bad name"]:
        try:
            WorkflowProfile(name=name)
        except ValueError:
            continue
        raise AssertionError(f"profile name should be rejected: {name}")


def test_monitor_start_and_run_once_use_artifact_state() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        start = runner.invoke(
            cli,
            [
                "monitor",
                "start",
                "--provider",
                "mock",
                "--limit",
                "1",
                "--runs-dir",
                "runs",
                "--probability-delta",
                "0",
            ],
        )

        assert start.exit_code == 0, start.output
        run_dir = next(Path("runs").iterdir())
        assert (run_dir / "monitor.json").exists()

        run_once = runner.invoke(cli, ["monitor", "run-once", str(run_dir)])
        show = runner.invoke(cli, ["monitor", "show", str(run_dir)])
        pause = runner.invoke(cli, ["monitor", "pause", str(run_dir)])
        daemon = runner.invoke(cli, ["monitor", "daemon", str(run_dir), "--cycles", "2", "--interval-seconds", "0"])

        assert run_once.exit_code == 0, run_once.output
        assert show.exit_code == 0, show.output
        assert "1" in show.output
        assert pause.exit_code == 0, pause.output
        assert daemon.exit_code != 0

        resume = runner.invoke(cli, ["monitor", "resume", str(run_dir)])
        daemon = runner.invoke(cli, ["monitor", "daemon", str(run_dir), "--cycles", "2", "--interval-seconds", "0"])
        monitor_payload = json.loads((run_dir / "monitor.json").read_text(encoding="utf-8"))
        summary = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
        events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
        assert resume.exit_code == 0, resume.output
        assert daemon.exit_code == 0, daemon.output
        assert monitor_payload["schema_version"] == "xrtm.monitor.v1"
        assert monitor_payload["status"] == "degraded"
        assert monitor_payload["cycles"] == 3
        assert summary["schema_version"] == "xrtm.monitor-summary.v1"
        assert summary["warning_count"] >= 1
        assert "monitor_status_changed" in {event["event_type"] for event in events}
        assert "warning" in {event["event_type"] for event in events}


def test_artifacts_cleanup_applies_keep_policy() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        first = runner.invoke(cli, ["demo", "--provider", "mock", "--limit", "1", "--runs-dir", "runs"])
        second = runner.invoke(cli, ["demo", "--provider", "mock", "--limit", "1", "--runs-dir", "runs"])
        dry_run = runner.invoke(cli, ["artifacts", "cleanup", "--runs-dir", "runs", "--keep", "1"])
        delete = runner.invoke(cli, ["artifacts", "cleanup", "--runs-dir", "runs", "--keep", "1", "--delete"])

        assert first.exit_code == 0, first.output
        assert second.exit_code == 0, second.output
        assert dry_run.exit_code == 0, dry_run.output
        assert "would remove 1" in dry_run.output
        assert delete.exit_code == 0, delete.output
        assert len(list(Path("runs").iterdir())) == 1


def test_monitor_missing_output_transitions_watch_to_degraded() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        start = runner.invoke(cli, ["monitor", "start", "--provider", "mock", "--limit", "1", "--runs-dir", "runs"])
        assert start.exit_code == 0, start.output
        run_dir = next(Path("runs").iterdir())

        with patch("xrtm.product.monitoring.run_real_question_e2e", return_value=[]):
            monitor = run_monitor_once(run_dir=run_dir)

        summary = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
        watch = monitor["watches"][0]
        assert monitor["status"] == "degraded"
        assert watch["status"] == "degraded"
        assert watch["warnings"]
        assert summary["warning_count"] == 1


def test_tui_and_web_smoke_over_run_artifacts() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        demo = runner.invoke(cli, ["demo", "--provider", "mock", "--limit", "1", "--runs-dir", "runs"])
        assert demo.exit_code == 0, demo.output

        tui = runner.invoke(cli, ["tui", "--runs-dir", "runs"])
        web = runner.invoke(cli, ["web", "--runs-dir", "runs", "--smoke"])
        snapshot = web_snapshot(Path("runs"))

        assert tui.exit_code == 0, tui.output
        assert "XRTM local product cockpit" in tui.output
        assert web.exit_code == 0, web.output
        assert len(snapshot["runs"]) == 1


def test_webui_serves_api_routes() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        demo = runner.invoke(cli, ["demo", "--provider", "mock", "--limit", "1", "--runs-dir", "runs"])
        assert demo.exit_code == 0, demo.output

        server = create_web_server(runs_dir=Path("runs"), port=0)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            _, port = server.server_address
            with urlopen(f"http://127.0.0.1:{port}/api/runs", timeout=5) as response:
                body = response.read().decode("utf-8")
            assert "runs" in body
            assert "local_llm" in body
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def _strip_ansi(output: str) -> str:
    return _ANSI_RE.sub("", output)
