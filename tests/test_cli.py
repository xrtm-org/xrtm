import json
from pathlib import Path
from threading import Thread
from unittest.mock import patch
from urllib.request import urlopen

from click.testing import CliRunner

from xrtm.cli.main import cli
from xrtm.product.history import resolve_run_dir
from xrtm.product.monitoring import run_monitor_once
from xrtm.product.profiles import WorkflowProfile
from xrtm.product.web import create_web_server, web_snapshot


def test_help_exposes_product_commands() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "doctor" in result.output
    assert "demo" in result.output
    assert "artifacts" in result.output
    assert "profile" in result.output
    assert "runs" in result.output
    assert "perf" in result.output
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


def test_artifacts_inspect_requires_run_json() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        Path("not-a-run").mkdir()
        result = runner.invoke(cli, ["artifacts", "inspect", "not-a-run"])

        assert result.exit_code != 0
        assert "run.json" in result.output


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
        assert report["budget"]["max_mean_seconds"] == 60
        assert report["budget"]["max_p95_seconds"] is None
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
        runs_search = runner.invoke(cli, ["runs", "search", "mock", "--runs-dir", "runs"])
        runs_show = runner.invoke(cli, ["runs", "show", run_id, "--runs-dir", "runs"])
        runs_export = runner.invoke(cli, ["runs", "export", run_id, "--runs-dir", "runs", "--output", "export.json"])

        assert create.exit_code == 0, create.output
        assert profile_list.exit_code == 0, profile_list.output
        assert "local-mock" in profile_list.output
        assert profile_show.exit_code == 0, profile_show.output
        assert run.exit_code == 0, run.output
        assert runs_list.exit_code == 0, runs_list.output
        assert run_id in runs_list.output
        assert runs_search.exit_code == 0, runs_search.output
        assert runs_show.exit_code == 0, runs_show.output
        assert "forecasts" in runs_show.output
        assert runs_export.exit_code == 0, runs_export.output
        exported = json.loads(Path("export.json").read_text(encoding="utf-8"))
        assert exported["run"]["run_id"] == run_id


def test_runs_compare_and_web_filters() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        first = runner.invoke(cli, ["demo", "--provider", "mock", "--limit", "1", "--runs-dir", "runs"])
        second = runner.invoke(cli, ["demo", "--provider", "mock", "--limit", "1", "--runs-dir", "runs"])
        run_ids = sorted(path.name for path in Path("runs").iterdir())
        compare = runner.invoke(cli, ["runs", "compare", run_ids[0], run_ids[1], "--runs-dir", "runs"])
        snapshot = web_snapshot(Path("runs"), provider="mock", query=run_ids[0])

        assert first.exit_code == 0, first.output
        assert second.exit_code == 0, second.output
        assert compare.exit_code == 0, compare.output
        assert "forecast_count" in compare.output
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
