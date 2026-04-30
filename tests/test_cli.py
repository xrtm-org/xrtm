import json
from pathlib import Path
from threading import Thread
from unittest.mock import patch
from urllib.request import urlopen

from click.testing import CliRunner

from xrtm.cli.main import cli
from xrtm.product.monitoring import run_monitor_once
from xrtm.product.web import create_web_server, web_snapshot


def test_help_exposes_product_commands() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "doctor" in result.output
    assert "demo" in result.output
    assert "artifacts" in result.output
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
