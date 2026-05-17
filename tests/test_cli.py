import csv
import json
import re
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch
from urllib.request import urlopen

import pytest
from click.testing import CliRunner
from rich.console import Console

from xrtm.cli import main as cli_main
from xrtm.cli.main import cli
from xrtm.product.history import compare_runs, resolve_run_dir
from xrtm.product.monitoring import run_monitor_once
from xrtm.product.profiles import STARTER_PROFILE_LIMIT, WorkflowProfile
from xrtm.product.tui import render_tui_once
from xrtm.product.web import create_web_server, web_snapshot

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_PACKAGE_VERSIONS = {
    "xrtm": "0.3.1",
    "xrtm-data": "0.2.6",
    "xrtm-eval": "0.2.5",
    "xrtm-forecast": "0.6.7",
    "xrtm-train": "0.2.6",
}


def _write_canonical_run_fixture(
    runs_dir: Path,
    run_id: str,
    *,
    user: str | None = None,
    probability: float = 0.6,
    outcome: bool = True,
    eval_brier: float = 0.16,
    eval_ece: float = 0.05,
    train_brier: float = 0.16,
    training_samples: int = 1,
) -> Path:
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
        json.dumps(
            {
                "forecast_count": 1,
                "warning_count": 0,
                "error_count": 0,
                "duration_seconds": 1.5,
                "token_counts": {"total_tokens": 42},
                "eval": {"brier_score": eval_brier, "ece": eval_ece},
                "train": {"brier_score": train_brier, "training_samples": training_samples},
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "events.jsonl").write_text("", encoding="utf-8")
    (run_dir / "forecasts.jsonl").write_text(
        json.dumps({"question_id": "q1", "probability": probability, "reasoning": "fixture"}) + "\n",
        encoding="utf-8",
    )
    (run_dir / "questions.jsonl").write_text(
        json.dumps(
            {
                "id": "q1",
                "title": "Fixture question title",
                "description": "Fixture question description",
                "resolution_time": "2026-05-02T00:00:00Z",
                "metadata": {
                    "raw_data": {
                        "resolved_outcome": outcome,
                        "resolution_criteria": "Fixture criteria",
                        "resolution_notes": "Fixture notes",
                        "source_metadata": {"source_url": "https://example.com/fixture"},
                        "tags": ["fixture", "demo"],
                    }
                },
            }
        )
        + "\n",
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
    assert "playground" in result.output
    assert "artifacts" in result.output
    assert "benchmark" in result.output
    assert "profile" in result.output
    assert "workflow" in result.output
    assert "runs" in result.output
    assert "perf" in result.output
    assert "validate" in result.output
    assert "local-llm" in result.output
    assert "monitor" in result.output
    assert "tui" in result.output
    assert "web" in result.output


def test_playground_runs_seeded_workflow_question_and_writes_sandbox_artifact() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            [
                "playground",
                "--workflow",
                "demo-provider-free",
                "--question",
                "Will the playground stay exploratory?",
                "--runs-dir",
                "runs",
            ],
        )

        output = _strip_ansi(result.output)
        assert result.exit_code == 0, output
        run_dir = next(Path("runs").iterdir())
        session_payload = json.loads((run_dir / "sandbox_session.json").read_text(encoding="utf-8"))
        assert session_payload["context"]["workflow_name"] == "demo-provider-free"
        assert session_payload["labeling"]["classification"] == "exploratory"
        assert "Exploratory playground session" in output
        assert "Sandbox output is inspectable" in output
        assert "Step inspection" in output
        assert "load_questions" in output
        assert "Workflow save-back: ready (demo-provider-free)" in output


def test_playground_supports_interactive_rerun_loop_with_template_context() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            ["playground", "--runs-dir", "runs"],
            input=(
                "template:provider-free-demo\n"
                "Will the first exploratory loop run?\n"
                "r\n"
                "Will the rerun keep the same template context?\n"
                "q\n"
            ),
        )

        output = _strip_ansi(result.output)
        assert result.exit_code == 0, output
        run_dirs = sorted(Path("runs").iterdir())
        assert len(run_dirs) == 2
        payloads = [
            json.loads((run_dir / "sandbox_session.json").read_text(encoding="utf-8"))
            for run_dir in run_dirs
        ]
        assert all(payload["context"]["template_id"] == "provider-free-demo" for payload in payloads)
        assert all(payload["labeling"]["classification"] == "exploratory" for payload in payloads)
        assert "Workflow contexts" in output
        assert "Starter template contexts" in output
        assert "Next action [r=rerun, c=change context, q=quit]" in output
        assert "Profile save-back: requires_workflow_save" in output
        assert output.count("Exploratory playground session") >= 2


def test_playground_command_uses_shared_launch_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    context = cli_main.launch_module.resolve_sandbox_context(workflow_name="demo-provider-free")
    calls: list[tuple[str, Any]] = []

    def fake_run_sandbox_session(**kwargs: Any):
        calls.append(("run", kwargs))
        return cli_main.launch_module.SandboxSessionResult(
            run_id="sandbox-cli-shared",
            run_dir=Path("runs") / "sandbox-cli-shared",
            run={
                "run_id": "sandbox-cli-shared",
                "status": "completed",
                "provider": "mock",
                "artifacts": {},
            },
            workflow={"title": "Shared sandbox workflow"},
            run_summary={"summary": "Shared contract response"},
            context=context,
            labeling={
                "classification": "exploratory",
                "surface": "sandbox",
                "display_label": "Exploratory playground session",
                "notes": ["Shared launch contract note."],
            },
            questions=({"title": "Shared contract question", "description": "Shared contract question"},),
            inspection_steps=(
                {"order": 7, "node_id": "forecast", "label": "Forecast", "node_type": "node", "status": "completed", "output_preview": "Shared step", "output": {}, "artifacts": [], "artifact_payloads": {}},
            ),
            save_back={
                "mode": "explicit",
                "workflow": {"status": "ready", "recommended_name": "demo-provider-free"},
                "profile": {"status": "ready"},
            },
            total_seconds=0.25,
        )

    monkeypatch.setattr(cli_main.launch_module, "run_sandbox_session", fake_run_sandbox_session)

    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            [
                "playground",
                "--workflow",
                "demo-provider-free",
                "--question",
                "Does the CLI use the shared launch contract?",
                "--runs-dir",
                "runs",
            ],
            input="q\n",
        )

    output = _strip_ansi(result.output)
    assert result.exit_code == 0, output
    assert "Shared launch contract note." in output
    assert "Step 7: forecast" in output
    assert "Workflow save-back: ready (demo-provider-free)" in output
    assert calls and calls[0][1]["command"] == "xrtm playground"


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
            "report.html",
            "blueprint.json",
            "graph_trace.jsonl",
        ]:
            assert (run_dir / name).exists(), name
        assert not (run_dir / "monitor.json").exists()
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
        blueprint = json.loads((run_dir / "blueprint.json").read_text(encoding="utf-8"))
        assert run_metadata["command"] == "xrtm start"
        assert "Readiness checks passed." in output
        assert "Running the released install/demo workflow now." in output
        assert "Use xrtm workflow list after this run to browse shipped workflows." in output
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
        assert "xrtm runs list --runs-dir runs" in output
        assert "xrtm runs show latest --runs-dir runs" in output
        assert "xrtm artifacts inspect --latest --runs-dir runs" in output
        assert "Open/regenerate the report: xrtm report html --latest --runs-dir runs" in output
        assert "xrtm web --runs-dir runs" in output
        assert "xrtm tui --runs-dir runs" in output
        assert "Official proof-point workflows" in output
        assert "Install/demo proof" in output
        assert "xrtm workflow list" in output
        assert "xrtm workflow show demo-provider-free" in output
        assert "xrtm workflow run demo-provider-free" in output
        assert "Benchmark and performance workflow" in output
        assert "Shipped benchmark workflow" in output
        assert "Monitoring, history, and report workflow" in output
        assert "OpenAI-compatible endpoint advanced workflow" in output
        for phrase in ["provider-free-smoke", "performance.json", "xrtm runs show", "xrtm artifacts inspect"]:
            assert phrase in output
        for phrase in ["xrtm profile starter my-local", "xrtm run profile my-local"]:
            assert phrase in output
        for phrase in ["xrtm monitor start --provider mock --limit 2", "xrtm monitor list --runs-dir runs"]:
            assert phrase in output
        for phrase in [
            "xrtm runs compare <run-id-a> <run-id-b> --runs-dir runs",
            "xrtm runs export latest",
            "--output export.json",
            "--output export.csv --format csv",
        ]:
            assert phrase in output
        assert "xrtm local-llm status" in output
        assert "docs/python-api-reference.md" in output
        assert blueprint["name"] == "demo-provider-free"


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
        assert "xrtm runs list --runs-dir runs" in output
        assert f"xrtm runs show {run_dir.name} --runs-dir runs" in output
        assert f"xrtm artifacts inspect {run_dir}" in output
        assert f"Open/regenerate the report: xrtm report html {run_dir}" in output
        assert "xrtm web --runs-dir runs" in output
        assert "xrtm tui --runs-dir runs" in output


def test_workflow_list_show_and_run_demo_provider_free() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        listed = runner.invoke(cli, ["workflow", "list"])
        shown = runner.invoke(cli, ["workflow", "show", "demo-provider-free"])
        validated = runner.invoke(cli, ["workflow", "validate", "demo-provider-free"])
        run = runner.invoke(cli, ["workflow", "run", "demo-provider-free", "--runs-dir", "runs"])

        assert listed.exit_code == 0, listed.output
        assert "demo-provider-free" in _strip_ansi(listed.output)
        assert "flagship-benchmark" in _strip_ansi(listed.output)

        shown_output = _strip_ansi(shown.output)
        assert shown.exit_code == 0, shown_output
        assert "Workflow: demo-provider-free" in shown_output
        assert "Workflow graph nodes" in shown_output
        assert "forecast" in shown_output

        assert validated.exit_code == 0, validated.output
        assert "Workflow valid: demo-provider-free (xrtm.workflow.v1)" in _strip_ansi(validated.output)

        run_output = _strip_ansi(run.output)
        assert run.exit_code == 0, run_output
        run_dir = next(Path("runs").iterdir())
        assert "Workflow: XRTM install and provider-free demo" in run_output
        assert "Succeeded: xrtm workflow run demo-provider-free completed." in run_output
        assert (run_dir / "blueprint.json").exists()
        assert (run_dir / "graph_trace.jsonl").exists()
        blueprint = json.loads((run_dir / "blueprint.json").read_text(encoding="utf-8"))
        trace_lines = (run_dir / "graph_trace.jsonl").read_text(encoding="utf-8").splitlines()
        assert blueprint["name"] == "demo-provider-free"
        assert any('"node": "forecast"' in line for line in trace_lines)


def test_workflow_validate_and_explain_use_launch_services(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    calls: list[tuple[str, Any, ...]] = []

    def fake_validate(name: str, *, workflows_dir: Path) -> SimpleNamespace:
        calls.append(("validate", name, workflows_dir))
        return SimpleNamespace(name=name, schema_version="xrtm.workflow.v1")

    def fake_explain(name: str, *, workflows_dir: Path) -> dict[str, Any]:
        calls.append(("explain", name, workflows_dir))
        return {
            "summary": f"{name} summary",
            "runtime_requirements": ["Provider-free mode works out of the box."],
            "expected_artifacts": ["run.json"],
            "nodes": [],
        }

    monkeypatch.setattr(cli_main.launch_module, "validate_registered_workflow", fake_validate)
    monkeypatch.setattr(cli_main.launch_module, "explain_registered_workflow", fake_explain)

    validate = runner.invoke(cli, ["workflow", "validate", "demo-provider-free", "--workflows-dir", "workflows"])
    explain = runner.invoke(cli, ["workflow", "explain", "demo-provider-free", "--workflows-dir", "workflows"])

    assert validate.exit_code == 0, validate.output
    assert explain.exit_code == 0, explain.output
    assert "Workflow valid: demo-provider-free (xrtm.workflow.v1)" in _strip_ansi(validate.output)
    explain_output = _strip_ansi(explain.output)
    assert "Workflow explanation: demo-provider-free" in explain_output
    assert "Runtime requirements" in explain_output
    assert calls == [
        ("validate", "demo-provider-free", Path("workflows")),
        ("explain", "demo-provider-free", Path("workflows")),
    ]


def test_flagship_benchmark_workflow_runs_in_provider_free_fallback_mode() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        shown = runner.invoke(cli, ["workflow", "show", "flagship-benchmark"])
        run = runner.invoke(cli, ["workflow", "run", "flagship-benchmark", "--runs-dir", "runs-benchmark", "--provider", "mock"])

        shown_output = _strip_ansi(shown.output)
        assert shown.exit_code == 0, shown_output
        assert "Workflow: flagship-benchmark" in shown_output
        assert "aggregate_candidates" in shown_output
        assert "runtime_router" in shown_output

        run_output = _strip_ansi(run.output)
        assert run.exit_code == 0, run_output
        assert "Workflow: XRTM flagship offline benchmark workflow" in run_output
        run_dir = next(Path("runs-benchmark").iterdir())
        blueprint = json.loads((run_dir / "blueprint.json").read_text(encoding="utf-8"))
        trace_lines = (run_dir / "graph_trace.jsonl").read_text(encoding="utf-8").splitlines()
        assert blueprint["name"] == "flagship-benchmark"
        assert "fallback_fanout" in json.dumps(blueprint["graph"])
        assert any('"node": "aggregate_candidates"' in line for line in trace_lines)
        assert any('"node": "provider_free_control"' in line for line in trace_lines)
        assert any('"node": "time_series_baseline"' in line for line in trace_lines)


def test_workflow_authoring_commands_create_and_edit_safe_local_workflows() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        workflow_help = runner.invoke(cli, ["workflow", "--help"])
        assert workflow_help.exit_code == 0, workflow_help.output
        workflow_help_output = _strip_ansi(workflow_help.output)
        assert "create" in workflow_help_output
        assert "edit" in workflow_help_output

        scratch = runner.invoke(
            cli,
            [
                "workflow",
                "create",
                "scratch",
                "authored-scratch",
                "--title",
                "Authored Scratch Workflow",
                "--description",
                "Scratch workflow authored through the CLI.",
                "--workflow-kind",
                "workflow",
                "--question-limit",
                "3",
                "--max-tokens",
                "640",
                "--workflows-dir",
                "workflows",
            ],
        )
        scratch_output = _strip_ansi(scratch.output)
        assert scratch.exit_code == 0, scratch_output
        assert "Workflow created:" in scratch_output
        assert "xrtm workflow show authored-scratch" in scratch_output

        template = runner.invoke(
            cli,
            [
                "workflow",
                "create",
                "template",
                "ensemble-starter",
                "authored-template",
                "--workflows-dir",
                "workflows",
            ],
        )
        assert template.exit_code == 0, template.output

        cloned = runner.invoke(
            cli,
            [
                "workflow",
                "create",
                "clone",
                "demo-provider-free",
                "authored-clone",
                "--title",
                "Authored Clone Workflow",
                "--workflows-dir",
                "workflows",
            ],
        )
        assert cloned.exit_code == 0, cloned.output

        metadata = runner.invoke(
            cli,
            [
                "workflow",
                "edit",
                "metadata",
                "authored-scratch",
                "--title",
                "Customized Scratch Workflow",
                "--description",
                "Customized through the CLI authoring flow.",
                "--workflow-kind",
                "benchmark",
                "--tag",
                "authoring",
                "--tag",
                "cli",
                "--workflows-dir",
                "workflows",
            ],
        )
        assert metadata.exit_code == 0, metadata.output

        questions = runner.invoke(
            cli,
            [
                "workflow",
                "edit",
                "questions",
                "authored-scratch",
                "--corpus-id",
                "xrtm-real-binary-v1",
                "--limit",
                "4",
                "--workflows-dir",
                "workflows",
            ],
        )
        assert questions.exit_code == 0, questions.output

        runtime = runner.invoke(
            cli,
            [
                "workflow",
                "edit",
                "runtime",
                "authored-scratch",
                "--provider",
                "local-llm",
                "--base-url",
                "http://127.0.0.1:11434/v1",
                "--model",
                "phi-4-mini",
                "--api-key",
                "placeholder",
                "--max-tokens",
                "512",
                "--workflows-dir",
                "workflows",
            ],
        )
        assert runtime.exit_code == 0, runtime.output

        artifacts = runner.invoke(
            cli,
            [
                "workflow",
                "edit",
                "artifacts",
                "authored-scratch",
                "--no-write-report",
                "--no-write-blueprint-copy",
                "--workflows-dir",
                "workflows",
            ],
        )
        assert artifacts.exit_code == 0, artifacts.output

        scoring = runner.invoke(
            cli,
            [
                "workflow",
                "edit",
                "scoring",
                "authored-scratch",
                "--no-write-train-backtest",
                "--workflows-dir",
                "workflows",
            ],
        )
        assert scoring.exit_code == 0, scoring.output

        add_context = runner.invoke(
            cli,
            [
                "workflow",
                "edit",
                "node",
                "add",
                "authored-scratch",
                "question_context",
                "--builtin",
                "question-context",
                "--from-node",
                "load_questions",
                "--to-node",
                "forecast",
                "--description",
                "Insert question context before forecasting.",
                "--workflows-dir",
                "workflows",
            ],
        )
        assert add_context.exit_code == 0, add_context.output

        remove_default_edge = runner.invoke(
            cli,
            [
                "workflow",
                "edit",
                "edge",
                "remove",
                "authored-scratch",
                "load_questions",
                "forecast",
                "--workflows-dir",
                "workflows",
            ],
        )
        assert remove_default_edge.exit_code == 0, remove_default_edge.output

        add_bootstrap = runner.invoke(
            cli,
            [
                "workflow",
                "edit",
                "node",
                "add",
                "authored-scratch",
                "bootstrap",
                "--builtin",
                "load-questions",
                "--to-node",
                "load_questions",
                "--entry",
                "--workflows-dir",
                "workflows",
            ],
        )
        assert add_bootstrap.exit_code == 0, add_bootstrap.output

        entry = runner.invoke(
            cli,
            [
                "workflow",
                "edit",
                "entry",
                "set",
                "authored-scratch",
                "bootstrap",
                "--workflows-dir",
                "workflows",
            ],
        )
        assert entry.exit_code == 0, entry.output

        update_context = runner.invoke(
            cli,
            [
                "workflow",
                "edit",
                "node",
                "update",
                "authored-scratch",
                "question_context",
                "--description",
                "Updated question context node.",
                "--optional",
                "--workflows-dir",
                "workflows",
            ],
        )
        assert update_context.exit_code == 0, update_context.output

        validate = runner.invoke(cli, ["workflow", "validate", "authored-scratch", "--workflows-dir", "workflows"])
        assert validate.exit_code == 0, validate.output

        show = runner.invoke(cli, ["workflow", "show", "authored-scratch", "--workflows-dir", "workflows"])
        show_output = _strip_ansi(show.output)
        assert show.exit_code == 0, show_output
        assert "Workflow: authored-scratch" in show_output
        assert "question_context" in show_output

        authored_payload = json.loads(Path("workflows/authored-scratch.json").read_text(encoding="utf-8"))
        assert authored_payload["title"] == "Customized Scratch Workflow"
        assert authored_payload["workflow_kind"] == "benchmark"
        assert authored_payload["questions"]["limit"] == 4
        assert authored_payload["runtime"]["provider"] == "local-llm"
        assert authored_payload["runtime"]["model"] == "phi-4-mini"
        assert authored_payload["runtime"]["max_tokens"] == 512
        assert authored_payload["artifacts"]["write_report"] is False
        assert authored_payload["artifacts"]["write_blueprint_copy"] is False
        assert authored_payload["scoring"]["write_train_backtest"] is False
        assert authored_payload["tags"] == ["authoring", "cli"]
        assert authored_payload["graph"]["entry"] == "bootstrap"
        assert authored_payload["graph"]["nodes"]["question_context"]["description"] == "Updated question context node."
        assert authored_payload["graph"]["nodes"]["question_context"]["optional"] is True

        template_payload = json.loads(Path("workflows/authored-template.json").read_text(encoding="utf-8"))
        assert template_payload["name"] == "authored-template"
        assert "candidate_fanout" in template_payload["graph"]["parallel_groups"]

        cloned_payload = json.loads(Path("workflows/authored-clone.json").read_text(encoding="utf-8"))
        assert cloned_payload["name"] == "authored-clone"
        assert cloned_payload["title"] == "Authored Clone Workflow"


def test_workflow_clone_explain_validate_and_compare_customized_runs() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        cloned = runner.invoke(
            cli,
            ["workflow", "create", "clone", "flagship-benchmark", "my-workflow", "--workflows-dir", "workflows"],
        )
        assert cloned.exit_code == 0, cloned.output

        explain = runner.invoke(cli, ["workflow", "explain", "my-workflow", "--workflows-dir", "workflows"])
        explain_output = _strip_ansi(explain.output)
        assert explain.exit_code == 0, explain_output
        assert "Runtime requirements" in explain_output
        assert "Expected artifacts" in explain_output

        question_limit = runner.invoke(
            cli,
            ["workflow", "edit", "questions", "my-workflow", "--limit", "1", "--workflows-dir", "workflows"],
        )
        assert question_limit.exit_code == 0, question_limit.output
        first_weights = runner.invoke(
            cli,
            [
                "workflow",
                "edit",
                "node",
                "update",
                "my-workflow",
                "aggregate_candidates",
                "--config-json",
                json.dumps({"weights": {"provider_free_control": 1.0, "time_series_baseline": 0.0}}),
                "--replace-config",
                "--workflows-dir",
                "workflows",
            ],
        )
        assert first_weights.exit_code == 0, first_weights.output

        first_validate = runner.invoke(cli, ["workflow", "validate", "my-workflow", "--workflows-dir", "workflows"])
        assert first_validate.exit_code == 0, first_validate.output
        first_run = runner.invoke(
            cli,
            ["workflow", "run", "my-workflow", "--workflows-dir", "workflows", "--runs-dir", "runs", "--provider", "mock"],
        )
        assert first_run.exit_code == 0, first_run.output

        second_weights = runner.invoke(
            cli,
            [
                "workflow",
                "edit",
                "node",
                "update",
                "my-workflow",
                "aggregate_candidates",
                "--config-json",
                json.dumps({"weights": {"provider_free_control": 0.0, "time_series_baseline": 1.0}}),
                "--replace-config",
                "--workflows-dir",
                "workflows",
            ],
        )
        assert second_weights.exit_code == 0, second_weights.output

        second_validate = runner.invoke(cli, ["workflow", "validate", "my-workflow", "--workflows-dir", "workflows"])
        assert second_validate.exit_code == 0, second_validate.output
        second_run = runner.invoke(
            cli,
            ["workflow", "run", "my-workflow", "--workflows-dir", "workflows", "--runs-dir", "runs", "--provider", "mock"],
        )
        assert second_run.exit_code == 0, second_run.output

        run_ids = sorted(path.name for path in Path("runs").iterdir())
        compare = runner.invoke(cli, ["runs", "compare", run_ids[0], run_ids[1], "--runs-dir", "runs"])
        compare_output = _strip_ansi(compare.output)
        assert compare.exit_code == 0, compare_output
        assert "XRTM Run Compare" in compare_output


def test_workflow_validate_rejects_unsafe_custom_implementation() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        cloned = runner.invoke(
            cli,
            ["workflow", "clone", "flagship-benchmark", "unsafe-workflow", "--workflows-dir", "workflows"],
        )
        assert cloned.exit_code == 0, cloned.output

        workflow_path = Path("workflows/unsafe-workflow.json")
        payload = json.loads(workflow_path.read_text(encoding="utf-8"))
        payload["graph"]["nodes"]["question_context"]["implementation"] = "unsafe.custom.search_node"
        workflow_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        invalid = runner.invoke(cli, ["workflow", "validate", "unsafe-workflow", "--workflows-dir", "workflows"])
        invalid_output = _strip_ansi(invalid.output)
        assert invalid.exit_code != 0
        assert "safe product node library" in invalid_output


def test_competition_dry_run_lists_packs_and_writes_bundle() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        listed = runner.invoke(cli, ["competition", "list"])
        listed_output = _strip_ansi(listed.output)
        assert listed.exit_code == 0, listed_output
        assert "metaculus-cup" in listed_output

        dry_run = runner.invoke(
            cli,
            ["competition", "dry-run", "metaculus-cup", "--runs-dir", "runs", "--provider", "mock", "--limit", "1"],
        )
        dry_run_output = _strip_ansi(dry_run.output)
        assert dry_run.exit_code == 0, dry_run_output
        assert "Competition dry-run bundle" in dry_run_output

        run_dirs = list(Path("runs").iterdir())
        assert len(run_dirs) == 1
        bundle = json.loads((run_dirs[0] / "competition_submission.json").read_text(encoding="utf-8"))
        assert bundle["competition"]["name"] == "metaculus-cup"
        assert bundle["submission"]["transport"]["auth_env_var"] == "METACULUS_TOKEN"
        assert bundle["submission"]["transport"]["token"] == "[redacted]"


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
        assert "xrtm runs list --runs-dir starter-runs" in cleaned
        assert run.exit_code == 0, run.output
        assert next(Path("starter-runs").iterdir()).is_dir()


@pytest.mark.parametrize(
    "command",
    [
        ["profile", "create", "local-mock"],
        ["profile", "starter", "my-local"],
    ],
)
def test_profile_commands_suggest_writable_workspace_on_permission_error(command: list[str]) -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        with patch("xrtm.cli.main.ProfileStore.create", side_effect=PermissionError("permission denied")):
            result = runner.invoke(cli, command)

    cleaned = _ANSI_RE.sub("", result.output)
    assert result.exit_code != 0
    assert "Cannot write profiles under" in cleaned
    assert "permission denied" in cleaned
    assert "writable workspace" in cleaned
    assert "--profiles-dir /writable/path" in cleaned


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
        question_payload = json.loads((run_dir / "questions.jsonl").read_text(encoding="utf-8").splitlines()[0])

        export_result = runner.invoke(cli, ["runs", "export", "latest", "--runs-dir", "runs", "--output", "export.csv", "--format", "csv"])
        assert export_result.exit_code == 0, export_result.output

        with Path("export.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))

        assert rows
        row = rows[0]
        assert row["user"] == "alice"
        assert row["started_at"] == run_metadata["created_at"]
        assert row["completed_at"] == run_metadata["updated_at"]
        assert row["question_id"] == question_payload["id"]
        assert row["question_title"] == question_payload["title"]
        assert row["question_text"] == question_payload["title"]
        assert row["question_description"] == question_payload["description"]
        assert row["resolution_date"] == question_payload["metadata"]["raw_data"]["resolution_time"]
        assert row["resolution_criteria"] == question_payload["resolution_criteria"]
        assert row["resolution_notes"] == question_payload["metadata"]["raw_data"]["resolution_notes"]
        assert row["source_url"] == question_payload["metadata"]["raw_data"]["source_metadata"]["source_url"]
        assert row["tags"] == ",".join(question_payload["metadata"]["raw_data"]["tags"])
        assert row["recorded_at"]
        assert row["forecast_probability"]
        assert row["forecast_reasoning"]
        assert row["resolved"] == "True"
        assert row["outcome"] == str(question_payload["metadata"]["raw_data"]["resolved_outcome"])
        assert float(row["brier_score"]) == pytest.approx((float(row["forecast_probability"]) - 1.0) ** 2)
        assert row["eval_ece"]
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


def test_benchmark_commands_delegate_to_validation_stack() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        listed = runner.invoke(cli, ["benchmark", "list-corpora"])
        cached = runner.invoke(
            cli,
            [
                "benchmark",
                "cache-corpus",
                "--corpus-id",
                "forecast-v1",
                "--fixture-preview",
                "--cache-root",
                "benchmark-cache",
            ],
        )
        run = runner.invoke(
            cli,
            [
                "benchmark",
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
                "runs-benchmark",
                "--output-dir",
                ".cache/benchmark",
            ],
        )

        listed_output = _ANSI_RE.sub("", listed.output)
        run_output = _ANSI_RE.sub("", run.output)

        assert listed.exit_code == 0, listed.output
        assert "Available Benchmark Corpora" in listed_output
        assert "forecast-v1" in listed_output
        assert cached.exit_code == 0, cached.output
        assert "Prepared Benchmark Corpus" in _ANSI_RE.sub("", cached.output)
        assert Path("benchmark-cache/forecast-v1/1.0/manifest.json").exists()
        assert run.exit_code == 0, run.output
        assert "XRTM Benchmark" in run_output
        assert "held-out" in run_output
        artifacts = list(Path(".cache/benchmark").glob("validation-xrtm-real-binary-v1-*.json"))
        assert len(artifacts) == 1
        report = json.loads(artifacts[0].read_text(encoding="utf-8"))
        assert report["configuration"]["runs_dir"] == "runs-benchmark"
        run_dir = next(Path("runs-benchmark").iterdir())
        run_metadata = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        assert run_metadata["command"] == "xrtm benchmark run xrtm-real-binary-v1"


def test_benchmark_compare_writes_machine_readable_artifact() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            [
                "benchmark",
                "compare",
                "--corpus-id",
                "xrtm-real-binary-v1",
                "--split",
                "held-out",
                "--limit",
                "5",
                "--runs-dir",
                "runs-benchmark",
                "--output-dir",
                ".cache/benchmark",
            ],
        )

        cleaned = _ANSI_RE.sub("", result.output)
        assert result.exit_code == 0, result.output
        assert "XRTM Benchmark Compare" in cleaned
        assert "Frozen split signature:" in cleaned
        assert "Candidate beats baseline:" in cleaned
        artifacts = list(Path(".cache/benchmark").glob("benchmark-compare-xrtm-real-binary-v1-*.json"))
        assert len(artifacts) == 1
        payload = json.loads(artifacts[0].read_text(encoding="utf-8"))
        assert payload["schema_version"] == "xrtm.benchmark-compare.v1"
        assert payload["benchmark"]["split"] == "held-out"
        assert payload["baseline"]["run_ids"]
        assert payload["candidate"]["run_ids"]


def test_benchmark_stress_writes_suite_artifact() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            [
                "benchmark",
                "stress",
                "--corpus-id",
                "xrtm-real-binary-v1",
                "--split",
                "held-out",
                "--limit",
                "4",
                "--repeats",
                "2",
                "--runs-dir",
                "runs-benchmark",
                "--output-dir",
                ".cache/benchmark",
            ],
        )

        cleaned = _ANSI_RE.sub("", result.output)
        assert result.exit_code == 0, result.output
        assert "XRTM Benchmark Stress Suite" in cleaned
        assert "Stress review loop" in cleaned
        artifacts = list(Path(".cache/benchmark").glob("benchmark-stress-xrtm-real-binary-v1-*.json"))
        assert len(artifacts) == 1
        payload = json.loads(artifacts[0].read_text(encoding="utf-8"))
        assert payload["schema_version"] == "xrtm.benchmark-suite-result.v1"
        assert payload["spec"]["repeat_count"] == 2
        assert len(payload["arm_results"]) == 2


def test_providers_doctor_reports_status_without_failing() -> None:
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

    with patch("xrtm.cli.main.local_llm_status", return_value=local_status):
        result = runner.invoke(cli, ["providers", "doctor", "--base-url", local_status["base_url"]])

    output = _strip_ansi(result.output)
    assert result.exit_code == 0, output
    assert "Local LLM" in output
    assert "Healthy: False" in output
    assert "connection refused" in output


def test_local_llm_status_command_fails_with_guidance_when_unhealthy() -> None:
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

    with patch("xrtm.cli.main.local_llm_status", return_value=local_status):
        result = runner.invoke(cli, ["local-llm", "status", "--base-url", local_status["base_url"]])

    output = _strip_ansi(result.output)
    assert result.exit_code != 0
    assert "Troubleshooting steps:" in output
    assert f"curl {local_status['health_url']}" in output
    assert local_status["base_url"] in output


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
        assert snapshot["runs"][0]["workflow"]["name"] == "demo-provider-free"


def test_runs_compare_surfaces_shared_question_quality_rows() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        runs_dir = Path("runs")
        _write_canonical_run_fixture(
            runs_dir,
            "20260501T101710Z-d8967e54",
            user="alice",
            probability=0.60,
            outcome=True,
            eval_brier=0.1600,
            eval_ece=0.0800,
        )
        _write_canonical_run_fixture(
            runs_dir,
            "20260501T101711Z-e50ac5f1",
            user="bob",
            probability=0.80,
            outcome=True,
            eval_brier=0.0400,
            eval_ece=0.0200,
        )

        rows = compare_runs(runs_dir / "20260501T101710Z-d8967e54", runs_dir / "20260501T101711Z-e50ac5f1")
        metrics = {row["metric"]: row for row in rows}

        assert metrics["eval_ece"]["interpretation"] == "lower is better; right improved"
        assert metrics["shared_question_brier"]["left"] == pytest.approx(0.16)
        assert metrics["shared_question_brier"]["right"] == pytest.approx(0.04)
        assert metrics["shared_question_brier"]["interpretation"] == "lower is better; right improved"
        assert metrics["shared_questions_improved"]["right"] == 1
        assert metrics["avg_abs_probability_shift"]["right"] == pytest.approx(0.2)


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
        cleaned_start = _ANSI_RE.sub("", start.output)
        assert "xrtm monitor list --runs-dir runs" in cleaned_start
        assert f"xrtm monitor show {run_dir}" in cleaned_start
        assert f"xrtm monitor run-once {run_dir}" in cleaned_start

        run_once = runner.invoke(cli, ["monitor", "run-once", str(run_dir)])
        show = runner.invoke(cli, ["monitor", "show", str(run_dir)])
        listed = runner.invoke(cli, ["monitor", "list", "--runs-dir", "runs"])
        pause = runner.invoke(cli, ["monitor", "pause", str(run_dir)])
        daemon = runner.invoke(cli, ["monitor", "daemon", str(run_dir), "--cycles", "2", "--interval-seconds", "0"])

        assert run_once.exit_code == 0, run_once.output
        assert show.exit_code == 0, show.output
        assert listed.exit_code == 0, listed.output
        assert run_dir.name in listed.output
        assert "1" in show.output
        assert "Monitor commands" in show.output
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


def test_monitor_views_ignore_legacy_placeholder_monitor_files_on_regular_runs() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        run_dir = _write_canonical_run_fixture(Path("runs"), "20260501T101710Z-d8967e54")
        (run_dir / "monitor.json").write_text(json.dumps({"status": "idle", "watches": []}), encoding="utf-8")

        listed = runner.invoke(cli, ["monitor", "list", "--runs-dir", "runs"])
        shown = runner.invoke(cli, ["monitor", "show", str(run_dir)])
        snapshot = web_snapshot(Path("runs"))
        console = Console(record=True, width=120)
        render_tui_once(console, runs_dir=Path("runs"))
        tui_output = console.export_text()

        assert listed.exit_code == 0, listed.output
        assert "No monitor runs found in this workspace." in _strip_ansi(listed.output)
        assert shown.exit_code != 0
        assert "is not a monitor run" in _strip_ansi(shown.output)
        assert "No monitor runs yet." in tui_output
        assert snapshot["monitors"] == []
        assert "monitor" not in snapshot["runs"][0]


def test_tui_and_web_smoke_over_run_artifacts() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        demo = runner.invoke(cli, ["demo", "--provider", "mock", "--limit", "1", "--runs-dir", "runs"])
        assert demo.exit_code == 0, demo.output

        tui = runner.invoke(cli, ["tui", "--runs-dir", "runs"])
        web = runner.invoke(cli, ["web", "--runs-dir", "runs", "--smoke"])
        snapshot = web_snapshot(Path("runs"))
        tui_output = _strip_ansi(tui.output)

        assert tui.exit_code == 0, tui.output
        assert "XRTM local product cockpit" in tui_output
        assert "demo-provider-free" in tui_output
        assert "No monitor runs" in tui_output
        assert web.exit_code == 0, web.output
        assert len(snapshot["runs"]) == 1
        assert snapshot["monitors"] == []
        assert snapshot["runs"][0]["workflow"]["name"] == "demo-provider-free"


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
            with urlopen(f"http://127.0.0.1:{port}/api/app-shell", timeout=5) as response:
                shell_body = response.read().decode("utf-8")
            with urlopen(f"http://127.0.0.1:{port}/api/runs", timeout=5) as response:
                runs_body = response.read().decode("utf-8")
            with urlopen(f"http://127.0.0.1:{port}/", timeout=5) as response:
                html = response.read().decode("utf-8")
            assert '"resume_target"' in shell_body
            assert '"demo-provider-free"' in runs_body
            assert "Hub · Studio · Playground · Observatory · Operations · Advanced" in html
            assert "version-pill" in html
            assert "/static/app.js" in html
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def _strip_ansi(output: str) -> str:
    return _ANSI_RE.sub("", output)
