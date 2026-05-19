import json
import math
import re
import sqlite3
from http.client import RemoteDisconnected
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest
from click.testing import CliRunner

from xrtm.cli import main as cli_main
from xrtm.cli.main import cli
from xrtm.product import launch as launch_module
from xrtm.product import webui_state as webui_state_module
from xrtm.product import workbench as workbench_module
from xrtm.product.profiles import ProfileStore, WorkflowProfile
from xrtm.product.sandbox import MAX_SANDBOX_QUESTIONS
from xrtm.product.web import create_web_server, render_workbench_html
from xrtm.product.webui_state import WebUIStateStore
from xrtm.product.workbench import (
    WorkbenchInputError,
    apply_workbench_edit,
    clone_workflow_for_edit,
    run_workbench_workflow,
    validate_workbench_workflow,
    workbench_snapshot,
)
from xrtm.product.workflows import WorkflowRegistry

_BOOTSTRAP_PAYLOAD_RE = re.compile(r"window\.__XRTM_WEBUI_BOOTSTRAP__ = (?P<payload>\{.*?\});", re.S)


def _write_observatory_run_fixture(
    runs_dir: Path,
    run_id: str,
    *,
    probabilities: list[float],
    outcomes: list[bool | None],
) -> Path:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True)
    run_payload = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "status": "completed",
        "provider": "mock",
        "command": "xrtm test observatory",
        "created_at": "2026-05-01T10:00:00+00:00",
        "updated_at": "2026-05-01T10:00:30+00:00",
        "package_versions": {},
        "artifacts": {"run.json": str(run_dir / "run.json")},
        "summary": {},
    }
    (run_dir / "run.json").write_text(json.dumps(run_payload), encoding="utf-8")
    (run_dir / "run_summary.json").write_text(
        json.dumps({"forecast_count": len(probabilities), "eval": {"brier_score": 0.99, "ece": 0.99, "log_score": 0.99}}),
        encoding="utf-8",
    )

    questions = []
    forecasts = []
    for index, (probability, outcome) in enumerate(zip(probabilities, outcomes, strict=True)):
        question: dict[str, Any] = {"id": f"q-{index}", "title": f"Question {index}"}
        if outcome is not None:
            question["resolved_outcome"] = outcome
        questions.append(question)
        forecasts.append({"question_id": question["id"], "probability": probability})
    (run_dir / "questions.jsonl").write_text("\n".join(json.dumps(row) for row in questions) + "\n", encoding="utf-8")
    (run_dir / "forecasts.jsonl").write_text("\n".join(json.dumps(row) for row in forecasts) + "\n", encoding="utf-8")
    return run_dir


def test_workbench_clones_and_applies_only_safe_edits(tmp_path: Path) -> None:
    workflows_dir = tmp_path / "workflows"
    registry = WorkflowRegistry(local_roots=(workflows_dir,))

    path = clone_workflow_for_edit(
        registry,
        source_name="flagship-benchmark",
        target_name="my-benchmark",
    )
    assert path == workflows_dir / "my-benchmark.json"

    updated = apply_workbench_edit(
        registry,
        workflow_name="my-benchmark",
        values={
            "questions_limit": "3",
            "artifacts_write_report": "false",
            "weight:aggregate_candidates:primary_candidate": "70",
            "weight:aggregate_candidates:provider_free_control": "20",
            "weight:aggregate_candidates:time_series_baseline": "10",
        },
    )

    assert updated.questions.limit == 3
    assert updated.artifacts.write_report is False
    weights = updated.graph.nodes["aggregate_candidates"].config["weights"]
    assert set(weights) == {"primary_candidate", "provider_free_control", "time_series_baseline"}
    assert sum(weights.values()) == pytest.approx(1.0)
    assert weights["primary_candidate"] == pytest.approx(0.7)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["questions"]["limit"] == 3

    saved["graph"]["nodes"]["aggregate_candidates"]["config"]["weights"]["not_upstream"] = 0.1
    path.write_text(json.dumps(saved, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="non-upstream candidate"):
        registry.validate("my-benchmark")

    with pytest.raises(WorkbenchInputError, match="weight:aggregate_candidates:time_series_baseline is required"):
        apply_workbench_edit(
            registry,
            workflow_name="my-benchmark",
            values={
                "questions_limit": "3",
                "artifacts_write_report": "false",
                "weight:aggregate_candidates:primary_candidate": "70",
                "weight:aggregate_candidates:provider_free_control": "20",
            },
        )


def test_workbench_snapshot_loads_local_workflow_and_missing_model(tmp_path: Path) -> None:
    workflows_dir = tmp_path / "workflows"
    registry = WorkflowRegistry(local_roots=(workflows_dir,))
    clone_workflow_for_edit(registry, source_name="demo-provider-free", target_name="flagship-benchmark")

    snapshot = workbench_snapshot(Path("missing-runs"), workflows_dir, workflow_name="flagship-benchmark")

    assert snapshot["selected_workflow_name"] == "flagship-benchmark"
    assert snapshot["selected_workflow_source"]["source"] == "local"
    assert snapshot["selected_workflow"]["title"] == "XRTM install and provider-free demo"
    assert snapshot["validation"]["ok"] is True
    assert snapshot["canvas"]["nodes"]
    assert snapshot["safe_edit"]["questions_limit"]["max"] == 25
    assert snapshot["safe_edit"]["supported_edits"]
    assert snapshot["safe_edit"]["supported_edits"][0]["key"] == "questions_limit"

    missing = workbench_snapshot(Path("missing-runs"), workflows_dir, workflow_name="does-not-exist")
    assert missing["workflow_error"] == "workflow does not exist: does-not-exist"
    assert missing["canvas"] == {"nodes": [], "edges": [], "parallel_groups": {}, "conditional_routes": {}}


@pytest.mark.parametrize(
    ("source_name", "target_name"),
    [
        ("../flagship-benchmark", "safe"),
        ("flagship-benchmark", "../evil"),
        ("flagship/benchmark", "safe"),
        ("flagship-benchmark", "evil/name"),
        ("", "safe"),
    ],
)
def test_workbench_clone_rejects_unsafe_paths(tmp_path: Path, source_name: str, target_name: str) -> None:
    workflows_dir = tmp_path / "workflows"
    registry = WorkflowRegistry(local_roots=(workflows_dir,))

    with pytest.raises(WorkbenchInputError):
        clone_workflow_for_edit(registry, source_name=source_name, target_name=target_name)

    if workflows_dir.exists():
        assert list(workflows_dir.rglob("*.json")) == []


def test_workbench_edit_rejects_non_local_and_unexpected_fields(tmp_path: Path) -> None:
    registry = WorkflowRegistry(local_roots=(tmp_path / "workflows",))

    with pytest.raises(WorkbenchInputError, match="clone this workflow"):
        apply_workbench_edit(
            registry,
            workflow_name="demo-provider-free",
            values={"questions_limit": "1", "artifacts_write_report": "true"},
        )

    clone_workflow_for_edit(registry, source_name="demo-provider-free", target_name="my-demo")
    with pytest.raises(WorkbenchInputError, match="unsupported edit field"):
        apply_workbench_edit(
            registry,
            workflow_name="my-demo",
            values={"questions_limit": "1", "artifacts_write_report": "true", "runtime.provider": "local-llm"},
        )
    with pytest.raises(WorkbenchInputError, match="between 1 and"):
        apply_workbench_edit(
            registry,
            workflow_name="my-demo",
            values={"questions_limit": "999", "artifacts_write_report": "true"},
        )


def test_workbench_edit_rejects_bad_safe_edit_values(tmp_path: Path) -> None:
    registry = WorkflowRegistry(local_roots=(tmp_path / "workflows",))
    clone_workflow_for_edit(registry, source_name="flagship-benchmark", target_name="my-benchmark")

    base_values = {
        "questions_limit": "3",
        "artifacts_write_report": "false",
        "weight:aggregate_candidates:primary_candidate": "70",
        "weight:aggregate_candidates:provider_free_control": "20",
        "weight:aggregate_candidates:time_series_baseline": "10",
    }
    bad_cases = [
        ({"questions_limit": "0"}, "questions.limit must be between"),
        ({"questions_limit": "abc"}, "questions.limit must be an integer"),
        ({"artifacts_write_report": "maybe"}, "artifacts_write_report must be true or false"),
        ({"weight:aggregate_candidates:primary_candidate": "nan"}, "must be between 0 and 100"),
        ({"weight:aggregate_candidates:primary_candidate": "inf"}, "must be between 0 and 100"),
        ({"weight:aggregate_candidates:primary_candidate": "-1"}, "must be between 0 and 100"),
        ({"weight:aggregate_candidates:primary_candidate": "101"}, "must be between 0 and 100"),
        ({"weight:aggregate_candidates:not_upstream": "10"}, "unsupported edit field"),
    ]
    for overrides, match in bad_cases:
        values = dict(base_values)
        values.update(overrides)
        with pytest.raises(WorkbenchInputError, match=match):
            apply_workbench_edit(registry, workflow_name="my-benchmark", values=values)

    zero_values = dict(base_values)
    for key in list(zero_values):
        if key.startswith("weight:"):
            zero_values[key] = "0"
    with pytest.raises(WorkbenchInputError, match="at least one aggregate weight"):
        apply_workbench_edit(registry, workflow_name="my-benchmark", values=zero_values)


def test_workbench_validate_run_and_compare_paths_are_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = WorkflowRegistry(local_roots=(tmp_path / "workflows",))
    runs_dir = tmp_path / "runs"
    baseline_dir = runs_dir / "baseline-run"
    baseline_dir.mkdir(parents=True)
    observed: dict[str, object] = {}

    def fake_validation_report(
        *,
        workflow_name: str | None = None,
        blueprint: Any | None = None,
        registry: WorkflowRegistry | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        workflow = workflow_name or (blueprint.name if blueprint is not None else "")
        observed["validated_workflow"] = workflow
        observed["validated_registry"] = registry
        return {"ok": True, "errors": [], "workflow": workflow}

    def fake_run_authored_workflow(
        *,
        workflow_name: str | None = None,
        command: str,
        runs_dir: Path,
        user: str | None,
        registry: WorkflowRegistry | None = None,
        **_: Any,
    ) -> SimpleNamespace:
        run_dir = runs_dir / "edited-run"
        run_dir.mkdir(parents=True)
        observed["workflow"] = workflow_name
        observed["registry"] = registry
        observed["command"] = command
        observed["runs_dir"] = runs_dir
        observed["user"] = user
        return SimpleNamespace(run=SimpleNamespace(run_id="edited-run", run_dir=run_dir))

    def fake_compare_runs(left_dir: Path, right_dir: Path) -> list[dict[str, object]]:
        observed["compare"] = (left_dir, right_dir)
        return [{"metric": "status", "left": "succeeded", "right": "succeeded"}]

    monkeypatch.setattr(launch_module, "authored_workflow_validation_report", fake_validation_report)
    monkeypatch.setattr(launch_module, "run_authored_workflow", fake_run_authored_workflow)
    monkeypatch.setattr(workbench_module, "compare_runs", fake_compare_runs)

    validation = validate_workbench_workflow(registry, "demo-provider-free")
    result = run_workbench_workflow(
        registry,
        workflow_name="demo-provider-free",
        runs_dir=runs_dir,
        baseline_run_ref="baseline-run",
        user="analyst",
    )

    assert validation == {"ok": True, "errors": [], "workflow": "demo-provider-free"}
    assert result.run_id == "edited-run"
    assert result.baseline_run_id == "baseline-run"
    assert result.compare_rows == [{"metric": "status", "left": "succeeded", "right": "succeeded"}]
    assert observed["validated_workflow"] == "demo-provider-free"
    assert observed["validated_registry"] is registry
    assert observed["workflow"] == "demo-provider-free"
    assert observed["registry"] is registry
    assert observed["command"] == "xrtm web workflow run demo-provider-free"
    assert observed["runs_dir"] == runs_dir
    assert observed["user"] == "analyst"
    assert observed["compare"] == (baseline_dir, runs_dir / "edited-run")

    with pytest.raises(ValueError, match="invalid run reference"):
        run_workbench_workflow(
            registry,
            workflow_name="demo-provider-free",
            runs_dir=runs_dir,
            baseline_run_ref="../escape",
        )


def test_webui_draft_validate_and_run_use_shared_launch_helpers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workflows_dir = tmp_path / "workflows"
    runs_dir = tmp_path / "runs"
    registry = WorkflowRegistry(local_roots=(workflows_dir,))
    store = WebUIStateStore(tmp_path / "app-state.db")
    created = store.create_draft_session(
        registry=registry,
        runs_dir=runs_dir,
        creation_mode="scratch",
        draft_workflow_name="shared-draft",
    )
    calls: list[tuple[Any, ...]] = []

    def fake_validation_report(
        *,
        workflow_name: str | None = None,
        blueprint: Any | None = None,
        persist: bool = False,
        overwrite: bool = False,
        **_: Any,
    ) -> dict[str, Any]:
        workflow = workflow_name or (blueprint.name if blueprint is not None else "")
        calls.append(("validate", workflow_name, None if blueprint is None else blueprint.name, persist, overwrite))
        return {"ok": True, "errors": [], "workflow": workflow}

    def fake_run_authored_workflow(
        *,
        workflow_name: str | None = None,
        command: str,
        runs_dir: Path,
        user: str | None,
        **_: Any,
    ) -> SimpleNamespace:
        calls.append(("run", workflow_name, command, runs_dir, user))
        run_dir = runs_dir / "draft-run"
        run_dir.mkdir(parents=True, exist_ok=True)
        return SimpleNamespace(run=SimpleNamespace(run_id="draft-run", run_dir=run_dir))

    monkeypatch.setattr(launch_module, "authored_workflow_validation_report", fake_validation_report)
    monkeypatch.setattr(launch_module, "run_authored_workflow", fake_run_authored_workflow)

    validated = store.validate_draft_session(draft_id=created["id"], registry=registry, runs_dir=runs_dir)
    launched = store.run_draft_session(
        draft_id=created["id"],
        registry=registry,
        runs_dir=runs_dir,
        user="web-user",
    )

    assert validated["validation"]["ok"] is True
    assert launched["run_id"] == "draft-run"
    assert calls[0] == ("validate", None, "shared-draft", True, True)
    assert calls[1] == ("validate", None, "shared-draft", True, True)
    assert calls[2] == ("run", "shared-draft", "xrtm web draft run shared-draft", runs_dir, "web-user")


def test_workbench_snapshot_and_html_expose_gui_loop(tmp_path: Path) -> None:
    workflows_dir = tmp_path / "workflows"
    snapshot = workbench_snapshot(Path("missing-runs"), workflows_dir, workflow_name="flagship-benchmark")
    html = render_workbench_html(Path("missing-runs"), workflows_dir, query_string="workflow=flagship-benchmark")

    assert snapshot["canvas"]["nodes"]
    assert snapshot["canvas"]["schema_version"] == "xrtm.studio.canvas.v1"
    first_node = snapshot["canvas"]["nodes"][0]
    assert first_node["id"] == f"node:{first_node['name']}"
    assert first_node["position"]["source"] == "deterministic-dag"
    assert first_node["position_persisted"] is False
    assert snapshot["canvas"]["layout"]["positions_persisted"] is False
    assert snapshot["authoring_catalog"]["node_palette"]["drag_drop"]["default_action"] == "add-node"
    assert snapshot["authoring_catalog"]["node_catalog"][0]["id"].startswith("palette:")
    assert snapshot["safe_edit"]["aggregate_weight_editors"]
    assert "Hub · Studio · Playground · Observatory · Batch · Versions · Operations · Control · Advanced" in html
    assert "Forecasting workspace" in html
    assert "Shared local shell" not in html
    assert "version-pill" in html
    assert "xrtm.webui.themeMode" in html
    assert "/static/app.js" in html
    assert "Loading the local-first app shell" in html


def test_workbench_snapshot_centers_single_path_canvas(tmp_path: Path) -> None:
    workflows_dir = tmp_path / "workflows"

    snapshot = workbench_snapshot(Path("missing-runs"), workflows_dir, workflow_name="demo-provider-free")

    ys = [int(node["y"]) for node in snapshot["canvas"]["nodes"]]
    assert ys
    assert min(ys) >= 200
    assert len(set(ys)) == 1


def test_webui_visual_acceptance_routes_use_shell_contracts_and_layout_guards(tmp_path: Path) -> None:
    workflows_dir = tmp_path / "workflows"
    runs_dir = tmp_path / "runs"
    app_db_path = tmp_path / "state" / "app-state.db"
    registry = WorkflowRegistry(local_roots=(workflows_dir,))
    store = WebUIStateStore(app_db_path)
    store.ensure_schema()

    run_result = run_workbench_workflow(registry, workflow_name="demo-provider-free", runs_dir=runs_dir)
    version = store.create_workflow_version(
        registry=registry,
        values={
            "workflow_name": "demo-provider-free",
            "label": "Visual acceptance lineage snapshot with an intentionally verbose title",
        },
    )
    batch = store.create_batch_run(
        registry=registry,
        values={
            "version_id": version["id"],
            "label": "Visual acceptance batch with a deliberately long operator-facing label",
            "rows": [
                {
                    "question": (
                        "Will the redesigned Batch route keep long questions and provenance labels readable "
                        "during the final acceptance gate?"
                    )
                }
            ],
        },
    )
    store.create_webhook_endpoint(
        {
            "url": "https://example.com/visual-gate",
            "events": ["run.completed", "batch.completed"],
            "secret": "visual-gate-secret",
        }
    )
    store.update_playground_session(
        registry=registry,
        runs_dir=runs_dir,
        values={
            "context_type": "workflow",
            "workflow_name": "demo-provider-free",
            "question_prompt": (
                "Will the redesigned Playground keep long single-question prompts readable without a browser gate?"
            ),
            "question_title": "Visual gate playground prompt",
        },
    )

    server = create_web_server(runs_dir=runs_dir, workflows_dir=workflows_dir, app_db_path=app_db_path, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        _, port = server.server_address
        base_url = f"http://127.0.0.1:{port}"

        app_js, _ = _request_text(f"{base_url}/static/app.js")
        app_css, css_content_type = _request_text(f"{base_url}/static/app.css")

        assert "text/css" in css_content_type
        assert ":root[data-theme=\"light\"]" in app_css
        assert ".theme-icon-button" in app_css
        assert ".shell-status-button" in app_css
        assert ".shell-icon-button" in app_css
        assert ".product-route-line" in app_css
        assert "--workspace-ide-height: clamp(32rem, calc(100vh - 9.75rem), 52rem);" in app_css
        assert "--workspace-pane-left: minmax(13.5rem, 15rem);" in app_css
        assert "--workspace-pane-center: minmax(0, 1.16fr);" in app_css
        assert "--workspace-pane-right: minmax(16rem, 18rem);" in app_css
        assert ".theme-icon-button[data-theme-mode=\"system\"] .theme-icon" in app_css
        assert ":root[data-theme=\"dark\"] .operations-stat-card" in app_css
        assert ":root[data-theme=\"dark\"] .operations-subpanel" in app_css
        assert ":root[data-theme=\"light\"] .studio-workspace .node-palette" in app_css
        assert ".studio-live-workspace.studio-ide-panel" in app_css
        assert ".studio-live-meta" in app_css
        assert ".workspace-mode-bar" in app_css
        assert ".workspace-live-shell" in app_css
        assert ".workflow-canvas-content" in app_css
        assert ".workflow-canvas-stage.canvas-pannable" in app_css
        assert ".density-disclosure" in app_css
        assert re.search(r"\.product-main\s*\{[^}]*min-width:\s*0;", app_css, re.S)
        assert re.search(r"\.product-main\s*\{[^}]*grid-template-rows:\s*auto\s+minmax\(0,\s*1fr\);", app_css, re.S)
        assert re.search(r"\.product-shell\s*\{(?=[^}]*height:\s*100vh)(?=[^}]*overflow:\s*hidden)[^}]*\}", app_css, re.S)
        assert re.search(r"\.page-stack\s*\{(?=[^}]*grid-template-rows:\s*minmax\(0,\s*1fr\))(?=[^}]*height:\s*100%)(?=[^}]*overflow:\s*auto)(?=[^}]*min-height:\s*0)[^}]*\}", app_css, re.S)
        assert re.search(r"\.table-wrap\s*\{[^}]*overflow-x:\s*auto;", app_css, re.S)
        assert re.search(
            r"\.operations-keyline-list strong,\s*\.operations-detail-strip strong\s*\{(?=[^}]*overflow-wrap:\s*anywhere)(?=[^}]*word-break:\s*break-word)[^}]*\}",
            app_css,
            re.S,
        )
        assert re.search(
            r"\.observatory-trust-facts dd\s*\{(?=[^}]*overflow-wrap:\s*anywhere)(?=[^}]*word-break:\s*break-word)[^}]*\}",
            app_css,
            re.S,
        )
        assert re.search(
            r"\.operations-hero-grid\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1\.45fr\)\s*minmax\(320px,\s*0\.95fr\);",
            app_css,
            re.S,
        )
        assert re.search(
            r"@media \(max-width:\s*1280px\)\s*\{.*?\.operations-hero-grid,\s*\.operations-lead-grid,\s*\.operations-control-grid,\s*\.operations-card-grid,\s*\.operations-retention-grid\s*\{.*?grid-template-columns:\s*1fr;",
            app_css,
            re.S,
        )
        assert re.search(
            r"@media \(max-width:\s*720px\)\s*\{.*?\.operations-field-grid\s*\{.*?grid-template-columns:\s*1fr;",
            app_css,
            re.S,
        )

        route_specs = [
            {
                "route": "/hub",
                "api": "/api/app-shell",
                "js_tokens": ("hub-page", "Starter templates", "Indexed workflows"),
                "css_patterns": (
                    r"\.hub-hero\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1\.8fr\)\s*minmax\(280px,\s*0\.85fr\);",
                    r"\.hub-hero-metrics\s*\{[^}]*repeat\(auto-fit,\s*minmax\(150px,\s*1fr\)\);",
                    r"\.hub-workflow-scroll\s*\{(?=[^}]*max-height:\s*30rem)(?=[^}]*overflow:\s*auto)(?=[^}]*overscroll-behavior:\s*contain)[^}]*\}",
                    r"@media \(max-width:\s*1280px\)\s*\{.*?\.hub-hero,\s*\.hub-content-grid\s*\{.*?grid-template-columns:\s*1fr;",
                    r"@media \(max-width:\s*900px\)\s*\{.*?\.hub-door-grid,\s*\.hub-hero-metrics\s*\{.*?grid-template-columns:\s*1fr;",
                ),
            },
            {
                "route": "/studio",
                "api": "/api/studio",
                "js_tokens": ("studio-workspace", "studio-live-workspace", "studio-ide-panel", "workspace-mode-bar", "Studio authoring", "Playground execution", "Browse all", "Quick insert", "Create or resume a local Studio draft"),
                "css_patterns": (
                    r"\.workspace-live-shell\s*\{(?=[^}]*grid-template-rows:\s*auto\s+minmax\(0,\s*1fr\))(?=[^}]*overflow:\s*hidden)[^}]*\}",
                    r"\.workspace-mode-toggle\s*\{(?=[^}]*display:\s*grid)(?=[^}]*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\))[^}]*\}",
                    r"\.studio-live-workspace\.studio-ide-panel\s*\{(?=[^}]*min-height:\s*var\(--workspace-ide-height\))(?=[^}]*grid-template-rows:\s*minmax\(0,\s*1fr\))(?=[^}]*overflow:\s*hidden)[^}]*grid-template-columns:\s*var\(--workspace-pane-left\)\s+var\(--workspace-pane-center\)\s+var\(--workspace-pane-right\);",
                    r"\.studio-workspace\s*\{(?=[^}]*align-items:\s*stretch)(?=[^}]*min-height:\s*0)[^}]*\}",
                    r"\.studio-draft-mode\s*\{(?=[^}]*display:\s*flex)(?=[^}]*flex-direction:\s*column)(?=[^}]*height:\s*100%)[^}]*\}",
                    r"\.studio-live-workspace \.studio-palette-panel\s*\{(?=[^}]*min-height:\s*0)(?=[^}]*overflow:\s*auto)[^}]*\}",
                    r"\.studio-workspace \.node-palette-scroll\s*\{(?=[^}]*overflow:\s*auto)(?=[^}]*overscroll-behavior:\s*contain)[^}]*\}",
                    r"\.studio-draft-mode \.workbench-main\s*\{(?=[^}]*flex:\s*1\s+1\s+auto)(?=[^}]*height:\s*100%)(?=[^}]*grid-template-rows:\s*minmax\(0,\s*1fr\))(?=[^}]*overflow:\s*hidden)[^}]*\}",
                    r"\.studio-live-workspace \.studio-side-panel\s*\{(?=[^}]*grid-template-rows:\s*auto\s+auto\s+minmax\(0,\s*1fr\))(?=[^}]*overflow:\s*hidden)[^}]*\}",
                    r"\.studio-live-meta\s*\{(?=[^}]*display:\s*grid)(?=[^}]*border-bottom:\s*1px\s+solid)[^}]*\}",
                    r"\.studio-draft-mode \.studio-toolbar\s*\{(?=[^}]*pointer-events:\s*none)[^}]*\}",
                    r"\.studio-draft-mode \.studio-toolbar > \*\s*\{(?=[^}]*pointer-events:\s*auto)[^}]*\}",
                    r"\.workflow-canvas-shell\s*\{(?=[^}]*display:\s*flex)(?=[^}]*flex-direction:\s*column)(?=[^}]*overflow:\s*hidden)[^}]*\}",
                    r"\.workflow-canvas-stage\.canvas-pannable\s*,\s*\.workflow-canvas-stage\.canvas-pannable \.workflow-canvas-svg\s*\{[^}]*cursor:\s*grab;",
                    r"\.studio-live-workspace \.studio-canvas-panel \.workflow-canvas-shell\s*\{(?=[^}]*grid-column:\s*1)(?=[^}]*grid-row:\s*1)(?=[^}]*overflow:\s*hidden)[^}]*\}",
                    r"\.workflow-canvas-stage\s*\{(?=[^}]*flex:\s*1\s+1\s+auto)(?=[^}]*overflow:\s*auto)(?=[^}]*min-height:\s*0)[^}]*\}",
                    r"@media \(max-width:\s*1180px\)\s*\{.*?\.studio-live-workspace\.studio-ide-panel\s*\{.*?grid-template-columns:\s*minmax\(12rem,\s*13\.5rem\)\s*minmax\(0,\s*1fr\);",
                    r"@media \(max-width:\s*1024px\)\s*\{.*?\.studio-live-workspace\.studio-ide-panel\s*\{.*?grid-template-columns:\s*1fr;",
                ),
            },
            {
                "route": "/playground",
                "api": "/api/playground",
                "js_tokens": ("playground-shell", "playground-live-workspace", "workspace-live-shell", "workspace-mode-toggle", "Single question input"),
                "css_patterns": (
                    r"\.workspace-live-shell\s*\{(?=[^}]*grid-template-rows:\s*auto\s+minmax\(0,\s*1fr\))(?=[^}]*overflow:\s*hidden)[^}]*\}",
                    r"\.playground-shell\s*\{(?=[^}]*align-items:\s*stretch)(?=[^}]*height:\s*100%)(?=[^}]*min-height:\s*0)[^}]*\}",
                    r"\.playground-live-workspace\s*\{(?=[^}]*height:\s*100%)(?=[^}]*min-height:\s*0)[^}]*grid-template-columns:\s*var\(--workspace-pane-left\)\s+var\(--workspace-pane-center\)\s+var\(--workspace-pane-right\);",
                    r"\.playground-canvas-panel \.workflow-canvas-shell\s*\{(?=[^}]*height:\s*100%)(?=[^}]*overflow:\s*hidden)[^}]*\}",
                    r"\.playground-canvas-panel \.workflow-canvas-stage\s*\{[^}]*min-height:\s*100%;",
                    r"\.live-trace-stack\s*\{(?=[^}]*overflow:\s*auto)(?=[^}]*min-height:\s*0)[^}]*\}",
                    r"@media \(max-width:\s*1360px\)\s*\{.*?:root\s*\{.*?--workspace-pane-left:\s*12\.5rem;.*?--workspace-pane-center:\s*minmax\(0,\s*1\.12fr\);.*?--workspace-pane-right:\s*16rem;",
                    r"@media \(max-width:\s*1180px\)\s*\{.*?\.playground-live-workspace\s*\{.*?grid-template-columns:\s*minmax\(12rem,\s*13\.5rem\)\s*minmax\(0,\s*1fr\);",
                    r"@media \(max-width:\s*1024px\)\s*\{.*?\.playground-live-workspace\s*\{.*?grid-template-columns:\s*1fr;.*?min-height:\s*auto;",
                ),
            },
            {
                "route": "/observatory",
                "api": "/api/runs",
                "js_tokens": ("observatory-page", "Calibration Curve", "Run analysis", "Recent runs"),
                "css_patterns": (
                    r"\.observatory-lead-grid\s*\{[^}]*grid-template-columns:\s*minmax\(300px,\s*0\.86fr\)\s*minmax\(0,\s*1\.14fr\);",
                    r"\.observatory-control-stats\s*\{[^}]*grid-template-columns:\s*repeat\(auto-fit,\s*minmax\(120px,\s*1fr\)\);",
                    r"\.observatory-run-table-wrap\s*\{(?=[^}]*max-height:\s*clamp\(18rem,\s*36vh,\s*28rem\))(?=[^}]*overflow:\s*auto)(?=[^}]*overscroll-behavior:\s*contain)[^}]*\}",
                    r"\.observatory-filter-row\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1\.15fr\)\s*repeat\(2,\s*minmax\(0,\s*0\.85fr\)\)\s*auto;",
                    r"@media \(max-width:\s*1360px\)\s*\{.*?\.observatory-lead-grid,\s*\.observatory-primary-shell,\s*\.observatory-dashboard,\s*\.observatory-score-grid\s*\{.*?grid-template-columns:\s*1fr;",
                ),
            },
            {
                "route": "/batch",
                "api": "/api/batch",
                "js_tokens": ("batch-shell", "operations-route", "Stage a local batch"),
                "css_patterns": (r"\.operations-field-grid\s*\{[^}]*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\);",),
            },
            {
                "route": "/versions",
                "api": "/api/versions",
                "js_tokens": ("versions-shell", "operations-route", "Freeze a shared workflow blueprint"),
                "css_patterns": (r"\.operations-detail-strip\s*\{[^}]*repeat\(auto-fit,\s*minmax\(170px,\s*1fr\)\);",),
            },
            {
                "route": "/api",
                "api": "/api/api-control",
                "js_tokens": ("api-shell", "operations-route", "Route examples"),
                "css_patterns": (r"\.operations-card-grid\s*\{[^}]*repeat\(auto-fit,\s*minmax\(260px,\s*1fr\)\);",),
            },
            {
                "route": "/operations",
                "api": "/api/profiles",
                "js_tokens": ("operations-shell", "Contained cleanup workflow", "Save repeatable local presets"),
                "css_patterns": (r"\.operations-control-grid\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1\.05fr\)\s*minmax\(320px,\s*0\.95fr\);",),
            },
            {
                "route": "/advanced",
                "api": "/api/app-shell",
                "js_tokens": ("advanced-shell", "calm disclosure", "Advanced capabilities stay visible"),
                "css_patterns": (r"\.advanced-note-card\s*\{[^}]*border-radius:\s*1rem;",),
            },
        ]

        for spec in route_specs:
            html, html_content_type = _request_text(f"{base_url}{spec['route']}")
            bootstrap = _extract_bootstrap_payload(html)

            assert "text/html" in html_content_type
            assert bootstrap == {
                "api_root": "/api",
                "initial_path": spec["route"],
                "initial_query": "",
                "initial_error": None,
            }
            assert "boot-route-strip" in html
            assert "Forecasting workspace" in html
            assert "Shared local shell" not in html
            assert "Loading the local-first app shell" in html
            assert "xrtm.webui.themeMode" in html

            for token in spec["js_tokens"]:
                assert token in app_js
            for pattern in spec["css_patterns"]:
                assert re.search(pattern, app_css, re.S), spec["route"]

        assert "xrtm.webui.themeMode" in app_js
        assert "prefers-color-scheme: dark" in app_js
        assert "theme-icon-button" in app_js
        assert "shell-status-button" in app_js
        assert "shell-icon-button" in app_js
        assert "ResizeObserver" in app_js
        assert "workflow-canvas-content" in app_js
        assert "canvas-pannable" in app_js
        assert "stageOffset" in app_js
        assert "maxStageOffsetX" in app_js
        assert "activeNodePointerRef" in app_js
        assert "captureTarget" in app_js
        assert "handleActiveNodePointerMove" in app_js
        assert "finishNodePointer" in app_js
        assert "workspace-mode-toggle" in app_js
        assert "scrollLeft" in app_js
        assert "scrollTop" in app_js
        assert "Workflow inspector" not in app_js
        assert "Node inspector" not in app_js
        assert "Edge inspector" not in app_js
        assert "Opening Studio graph IDE" in app_js
        studio_bootstrap_effect = re.search(
            r"setBusy\(\"Opening Studio graph IDE\"\).*?\}, \[\s*(?P<deps>.*?)\s*\]\);",
            app_js,
            re.S,
        )
        assert studio_bootstrap_effect is not None
        assert "studioBootstrapState" not in studio_bootstrap_effect.group("deps")
        for token in (
            "Run first success, bounded demos, or a named workflow without leaving the WebUI.",
            "Validate, inspect, and run a reusable workflow from the shared shell.",
            "Manage repeatable profiles, monitors, and artifact cleanup locally.",
            "Review advanced capabilities with explicit readiness and safety labels.",
        ):
            assert token in app_js

        hub = _request_json(f"{base_url}/api/app-shell")
        assert hub["hub"]["hero"]["eyebrow"] == "Entry route"
        assert hub["hub"]["doors"][0]["primary_cta"]["href"].startswith("/playground")
        assert hub["hub"]["doors"][1]["primary_cta"]["href"].startswith("/studio")

        studio = _request_json(f"{base_url}/api/studio")
        assert studio["schema_version"] == "xrtm.studio.api.v1"
        assert studio["surface"] == "studio"
        assert studio["routes"]["mutate_graph"]["href"] == "/api/studio/drafts/{draft_id}/graph"

        playground = _request_json(f"{base_url}/api/playground")
        assert playground["session"]["ready_to_run"] is True
        assert playground["context_preview"]["reference_name"] == "demo-provider-free"
        assert playground["graph_preview"]["nodes"]

        observatory = _request_json(f"{base_url}/api/runs")
        assert observatory["surface"]["canonical_href"] == "/runs"
        assert observatory["surface"]["alias_href"] == "/observatory"
        assert observatory["items"][0]["run_id"] == run_result.run_id

        batch_payload = _request_json(f"{base_url}/api/batch")
        assert batch_payload["surface"]["canonical_href"] == "/batch"
        assert batch_payload["items"][0]["id"] == batch["id"]
        assert batch_payload["items"][0]["definition"]["version_id"] == version["id"]

        versions_payload = _request_json(f"{base_url}/api/versions")
        assert versions_payload["surface"]["canonical_href"] == "/versions"
        assert versions_payload["items"][0]["id"] == version["id"]

        api_control = _request_json(f"{base_url}/api/api-control")
        assert api_control["surface"]["canonical_href"] == "/api"
        assert api_control["snapshots"]["versions"]["items"][0]["id"] == version["id"]
        assert api_control["snapshots"]["batch"]["items"][0]["id"] == batch["id"]
        assert api_control["counts"]["webhook_endpoints"] == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_workbench_webui_creates_draft_and_rejects_unsafe_patch(tmp_path: Path) -> None:
    workflows_dir = tmp_path / "workflows"
    server = create_web_server(runs_dir=tmp_path / "runs", workflows_dir=workflows_dir, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        _, port = server.server_address
        base_url = f"http://127.0.0.1:{port}"

        created = _request_json(
            f"{base_url}/api/drafts",
            method="POST",
            payload={"source_workflow_name": "demo-provider-free"},
        )
        assert created["id"].startswith("draft-")
        assert created["draft_workflow_name"].startswith("demo-provider-free-draft")
        assert (workflows_dir / f"{created['draft_workflow_name']}.json").exists()
        assert created["guidance"]["limitations"]
        assert created["guidance"]["supported_edits"]
        assert created["guidance"]["next_step"]["key"] == "validate"
        assert "SQLite" in " ".join(created["guidance"]["source_of_truth"])

        loaded = _request_json(f"{base_url}/api/drafts/{created['id']}")
        assert loaded["workflow"]["source"] == "local"
        assert loaded["step_state"][4]["locked"] is True
        assert loaded["guidance"]["next_step"]["title"] == "Validate before you run"

        with pytest.raises(HTTPError) as exc_info:
            _request_json(
                f"{base_url}/api/drafts/{created['id']}",
                method="PATCH",
                payload={"values": {"graph.nodes.injected.implementation": "not.allowed"}},
            )
        assert exc_info.value.code == 400
        assert "unsupported edit field" in exc_info.value.read().decode("utf-8")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_webui_authoring_catalog_and_creation_modes(tmp_path: Path) -> None:
    workflows_dir = tmp_path / "workflows"
    server = create_web_server(runs_dir=tmp_path / "runs", workflows_dir=workflows_dir, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        _, port = server.server_address
        base_url = f"http://127.0.0.1:{port}"

        catalog = _request_json(f"{base_url}/api/authoring/catalog")
        assert {item["key"] for item in catalog["creation_modes"]} == {"scratch", "template", "clone"}
        assert {item["template_id"] for item in catalog["templates"]} >= {"provider-free-demo", "ensemble-starter"}
        assert any(item["implementation"].endswith("question_context_node") for item in catalog["node_catalog"])

        scratch = _request_json(
            f"{base_url}/api/drafts",
            method="POST",
            payload={
                "creation_mode": "scratch",
                "draft_workflow_name": "scratch-webui-authoring",
                "title": "Scratch WebUI Authoring",
                "description": "Created from the WebUI scratch flow.",
            },
        )
        assert scratch["creation_mode"] == "scratch"
        assert scratch["draft_workflow_name"] == "scratch-webui-authoring"
        assert scratch["authoring"]["graph"]["nodes"]
        assert (workflows_dir / "scratch-webui-authoring.json").exists()

        template = _request_json(
            f"{base_url}/api/drafts",
            method="POST",
            payload={
                "creation_mode": "template",
                "template_id": "ensemble-starter",
                "draft_workflow_name": "template-webui-authoring",
            },
        )
        assert template["creation_mode"] == "template"
        assert template["template_id"] == "ensemble-starter"
        assert template["authoring"]["graph"]["parallel_groups"]["candidate_fanout"] == [
            "provider_free_control",
            "time_series_baseline",
        ]
        assert (workflows_dir / "template-webui-authoring.json").exists()

        cloned = _request_json(
            f"{base_url}/api/drafts",
            method="POST",
            payload={
                "creation_mode": "clone",
                "source_workflow_name": "demo-provider-free",
                "draft_workflow_name": "clone-webui-authoring",
            },
        )
        assert cloned["creation_mode"] == "clone"
        assert cloned["source_workflow_name"] == "demo-provider-free"
        assert cloned["workflow"]["source"] == "local"
        assert (workflows_dir / "clone-webui-authoring.json").exists()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_webui_authoring_patch_updates_workflow_fields_and_graph(tmp_path: Path) -> None:
    workflows_dir = tmp_path / "workflows"
    server = create_web_server(runs_dir=tmp_path / "runs", workflows_dir=workflows_dir, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        _, port = server.server_address
        base_url = f"http://127.0.0.1:{port}"

        created = _request_json(
            f"{base_url}/api/drafts",
            method="POST",
            payload={
                "creation_mode": "scratch",
                "draft_workflow_name": "visual-authoring-draft",
            },
        )

        updated = _request_json(
            f"{base_url}/api/drafts/{created['id']}",
            method="PATCH",
            payload={
                "action": {
                    "type": "update-core",
                    "metadata": {
                        "title": "Visual Authoring Draft",
                        "description": "Workflow fields updated through the shared WebUI authoring surface.",
                        "workflow_kind": "workflow",
                        "tags": ["webui", "authoring"],
                    },
                    "questions": {"limit": 3},
                    "runtime": {"provider": "mock", "base_url": None, "model": None, "max_tokens": 512},
                    "artifacts": {
                        "write_report": True,
                        "write_blueprint_copy": True,
                        "write_graph_trace": True,
                    },
                    "scoring": {"write_eval": True, "write_train_backtest": True},
                }
            },
        )
        assert updated["authoring"]["core_form"]["title"] == "Visual Authoring Draft"
        assert updated["authoring"]["core_form"]["questions_limit"] == "3"
        assert updated["authoring"]["core_form"]["runtime_max_tokens"] == "512"

        updated = _request_json(
            f"{base_url}/api/drafts/{created['id']}",
            method="PATCH",
            payload={
                "action": {
                    "type": "add-node",
                    "node_name": "bootstrap",
                    "implementation": "xrtm.product.workflow_nodes.load_questions_node",
                    "description": "Bootstrap before the main load node.",
                    "outgoing_to": ["load_questions"],
                    "set_as_entry": True,
                }
            },
        )
        assert updated["authoring"]["graph"]["entry"] == "bootstrap"
        assert any(node["name"] == "bootstrap" for node in updated["authoring"]["graph"]["nodes"])

        updated = _request_json(
            f"{base_url}/api/drafts/{created['id']}",
            method="PATCH",
            payload={
                "action": {
                    "type": "update-node",
                    "node_name": "bootstrap",
                    "description": "Updated bootstrap node from the visual surface.",
                    "optional": False,
                }
            },
        )
        bootstrap = next(node for node in updated["authoring"]["graph"]["nodes"] if node["name"] == "bootstrap")
        assert bootstrap["description"] == "Updated bootstrap node from the visual surface."

        updated = _request_json(
            f"{base_url}/api/drafts/{created['id']}",
            method="PATCH",
            payload={
                "action": {
                    "type": "add-edge",
                    "from_node": "bootstrap",
                    "to_node": "forecast",
                }
            },
        )
        assert {"from": "bootstrap", "to": "forecast"} in updated["authoring"]["graph"]["edges"]

        updated = _request_json(
            f"{base_url}/api/drafts/{created['id']}",
            method="PATCH",
            payload={
                "action": {
                    "type": "remove-edge",
                    "from_node": "bootstrap",
                    "to_node": "forecast",
                }
            },
        )
        assert {"from": "bootstrap", "to": "forecast"} not in updated["authoring"]["graph"]["edges"]

        validated = _request_json(f"{base_url}/api/drafts/{created['id']}/validate", method="POST")
        assert validated["validation"]["ok"] is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_studio_api_alias_exposes_graph_contract_and_preview_validation(tmp_path: Path) -> None:
    workflows_dir = tmp_path / "workflows"
    server = create_web_server(runs_dir=tmp_path / "runs", workflows_dir=workflows_dir, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        _, port = server.server_address
        base_url = f"http://127.0.0.1:{port}"

        with urlopen(f"{base_url}/studio", timeout=5) as response:
            assert response.headers["Content-Type"].startswith("text/html")
            with urlopen(f"{base_url}/static/app.js", timeout=5) as response:
                app_js = response.read().decode("utf-8")
            assert "Drag nodes, drop safe palette items" in app_js
            assert "Node positions persist with the draft layout" in app_js
        assert "/studio/drafts" in app_js
        assert "Single question input" in app_js
        assert "Calibration Curve" in app_js
        assert "Batch Runner" in app_js

        studio = _request_json(f"{base_url}/api/studio")
        assert studio["schema_version"] == "xrtm.studio.api.v1"
        assert studio["routes"]["mutate_graph"]["href"] == "/api/studio/drafts/{draft_id}/graph"

        catalog = _request_json(f"{base_url}/api/studio/catalog")
        assert catalog["node_palette"]["items"]
        assert catalog["node_palette"]["items"][0]["draggable"] is True

        created = _request_json(
            f"{base_url}/api/studio/drafts",
            method="POST",
            payload={
                "creation_mode": "template",
                "template_id": "ensemble-starter",
                "draft_workflow_name": "studio-contract-draft",
            },
        )
        draft_id = created["draft"]["id"]
        assert created["studio"]["positions"]["persisted"] is False
        assert created["canvas"]["layout"]["strategy"] == "deterministic-dag"

        patched = _request_json(
            f"{base_url}/api/studio/drafts/{draft_id}/graph",
            method="PATCH",
            payload={
                "action": {
                    "type": "update-node",
                    "node_name": "aggregate_candidates",
                    "config": {"weights": {"provider_free_control": 70, "time_series_baseline": 30}},
                }
            },
        )
        assert patched["validation"]["ok"] is True
        assert patched["validation"]["persisted"] is False
        aggregate = next(node for node in patched["canvas"]["nodes"] if node["name"] == "aggregate_candidates")
        assert aggregate["description"]
        assert aggregate["config"]["weights"]["provider_free_control"] == pytest.approx(0.7)

        loaded = _request_json(f"{base_url}/api/studio/drafts/{draft_id}")
        assert loaded["studio"]["read_only_graph_sections"] == ["parallel_groups", "conditional_routes"]
        assert loaded["draft"]["validation"]["ok"] is True
        moved = _request_json(
            f"{base_url}/api/studio/drafts/{draft_id}/graph",
            method="PATCH",
            payload={
                "action": {
                    "type": "move-node",
                    "node_name": "aggregate_candidates",
                    "position": {"x": 432, "y": 188},
                }
            },
        )
        moved_node = next(node for node in moved["canvas"]["nodes"] if node["name"] == "aggregate_candidates")
        assert moved_node["position_persisted"] is True
        assert moved_node["position"] == {"x": 432, "y": 188, "source": "draft-canvas-layout", "persisted": True}
        assert moved["canvas"]["layout"]["positions_persisted"] is True

        version = _request_json(
            f"{base_url}/api/versions",
            method="POST",
            payload={"draft_id": draft_id, "label": "Studio draft snapshot", "set_default": True},
        )
        assert version["source"] == "draft"
        assert version["metadata"]["draft"]["draft_id"] == draft_id
        moved_version_node = next(node for node in version["canvas"]["nodes"] if node["name"] == "aggregate_candidates")
        assert moved_version_node["position"]["persisted"] is True
        assert moved_version_node["position"]["x"] == 432
        assert moved_version_node["position"]["y"] == 188
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_webui_authoring_clone_flow_runs_and_compares_candidate(tmp_path: Path) -> None:
    workflows_dir = tmp_path / "workflows"
    runs_dir = tmp_path / "runs"
    registry = WorkflowRegistry(local_roots=(workflows_dir,))
    baseline = run_workbench_workflow(registry, workflow_name="demo-provider-free", runs_dir=runs_dir)

    server = create_web_server(runs_dir=runs_dir, workflows_dir=workflows_dir, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        _, port = server.server_address
        base_url = f"http://127.0.0.1:{port}"

        created = _request_json(
            f"{base_url}/api/drafts",
            method="POST",
            payload={
                "creation_mode": "clone",
                "source_workflow_name": "demo-provider-free",
                "draft_workflow_name": "clone-authoring-compare",
                "baseline_run_id": baseline.run_id,
            },
        )
        assert created["baseline_run_id"] == baseline.run_id

        updated = _request_json(
            f"{base_url}/api/drafts/{created['id']}",
            method="PATCH",
            payload={
                "action": {
                    "type": "update-core",
                    "metadata": {
                        "title": "Clone Compare Draft",
                        "description": "Edited clone used for inline compare coverage.",
                        "workflow_kind": "demo",
                        "tags": ["compare"],
                    },
                    "questions": {"limit": 1},
                    "runtime": {"provider": "mock", "base_url": None, "model": None, "max_tokens": 768},
                    "artifacts": {
                        "write_report": True,
                        "write_blueprint_copy": True,
                        "write_graph_trace": True,
                    },
                    "scoring": {"write_eval": True, "write_train_backtest": True},
                }
            },
        )
        assert updated["authoring"]["core_form"]["questions_limit"] == "1"

        validated = _request_json(f"{base_url}/api/drafts/{created['id']}/validate", method="POST")
        assert validated["validation"]["ok"] is True

        launched = _request_json(f"{base_url}/api/drafts/{created['id']}/run", method="POST")
        assert launched["run_id"]
        assert launched["compare"]["baseline_run_id"] == baseline.run_id
        assert launched["draft"]["compare"]["candidate_run_id"] == launched["run_id"]
        assert launched["draft"]["last_run_id"] == launched["run_id"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_webui_p0_api_routes_use_product_services(tmp_path: Path) -> None:
    workflows_dir = tmp_path / "workflows"
    runs_dir = tmp_path / "runs"
    registry = WorkflowRegistry(local_roots=(workflows_dir,))
    result = run_workbench_workflow(registry, workflow_name="demo-provider-free", runs_dir=runs_dir)
    report_path = runs_dir / result.run_id / "report.html"
    report_path.unlink()

    server = create_web_server(runs_dir=runs_dir, workflows_dir=workflows_dir, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        _, port = server.server_address
        base_url = f"http://127.0.0.1:{port}"

        health = _request_json(f"{base_url}/api/health")
        assert health["ready"] is True
        assert health["supported_python"] == ">=3.11,<3.14"
        assert {check["name"] for check in health["checks"]} >= {"Python", "Core packages", "Core imports"}

        providers = _request_json(f"{base_url}/api/providers/status")
        assert providers["provider_free"]["ready"] is True
        assert "openai-compatible-endpoint" in providers["first_class_categories"]

        explanation = _request_json(f"{base_url}/api/workflows/demo-provider-free/explain")
        assert explanation["workflow_name"] == "demo-provider-free"
        assert "runs" in explanation["explanation"]["summary"]

        validation = _request_json(f"{base_url}/api/workflows/demo-provider-free/validate", method="POST")
        assert validation["ok"] is True
        assert validation["workflow_name"] == "demo-provider-free"

        start_run = _request_json(f"{base_url}/api/start", method="POST", payload={"limit": 1, "user": "starter"})
        assert start_run["href"].startswith("/runs/")
        assert (runs_dir / start_run["run_id"]).exists()

        launched = _request_json(
            f"{base_url}/api/runs",
            method="POST",
            payload={"workflow_name": "demo-provider-free", "limit": 1, "baseline_run_id": start_run["run_id"]},
        )
        assert launched["href"] == f"/runs/{launched['run_id']}"
        assert launched["compare"]["baseline_run_id"] == start_run["run_id"]

        runs_payload = _request_json(f"{base_url}/api/runs")
        assert runs_payload["schema_version"] == "xrtm.webui.runs.v2"
        assert runs_payload["surface"]["name"] == "Observatory"
        assert runs_payload["summary_cards"][0]["label"] == "Indexed runs"
        assert runs_payload["items"][0]["observatory"]["inspect_href"].startswith("/runs/")

        with urlopen(f"{base_url}/observatory", timeout=5) as response:
            assert response.headers["Content-Type"].startswith("text/html")
        with urlopen(f"{base_url}/observatory/{result.run_id}", timeout=5) as response:
            assert response.headers["Content-Type"].startswith("text/html")

        run_detail = _request_json(f"{base_url}/api/runs/{result.run_id}")
        assert run_detail["observatory"]["title"] == "Run inspector"
        assert run_detail["execution_trace"]["items"]

        report = _request_json(f"{base_url}/api/runs/{result.run_id}/report", method="POST")
        assert report["href"] == f"/runs/{result.run_id}/report"
        assert report_path.exists()

        with urlopen(f"{base_url}/api/runs/{result.run_id}/export?format=json", timeout=5) as response:
            exported = json.loads(response.read().decode("utf-8"))
            assert response.headers["Content-Type"].startswith("application/json")
        assert exported["run"]["run_id"] == result.run_id

        with urlopen(f"{base_url}/api/runs/{result.run_id}/export?format=csv", timeout=5) as response:
            csv_body = response.read().decode("utf-8")
            assert response.headers["Content-Type"].startswith("text/csv")
            assert response.headers["Content-Disposition"].endswith(f'{result.run_id}.csv"')
        assert "forecast_probability" in csv_body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_run_export_cleans_up_temp_files_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workflows_dir = tmp_path / "workflows"
    runs_dir = tmp_path / "runs"
    registry = WorkflowRegistry(local_roots=(workflows_dir,))
    result = run_workbench_workflow(registry, workflow_name="demo-provider-free", runs_dir=runs_dir)

    def _failing_export(_run_dir: Path, output_path: Path, *, format: str) -> None:
        output_path.write_text(f"partial-{format}", encoding="utf-8")
        raise RuntimeError("export failed")

    monkeypatch.setattr("xrtm.product.web.export_run", _failing_export)

    server = create_web_server(runs_dir=runs_dir, workflows_dir=workflows_dir, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        _, port = server.server_address
        base_url = f"http://127.0.0.1:{port}"
        with pytest.raises((HTTPError, RemoteDisconnected)):
            urlopen(f"{base_url}/api/runs/{result.run_id}/export?format=json", timeout=5)
        export_dir = runs_dir / ".webui-exports"
        assert export_dir.exists()
        assert list(export_dir.iterdir()) == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_cli_and_webui_run_mutations_share_launch_services(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workflows_dir = tmp_path / ".xrtm" / "workflows"
    profiles_dir = tmp_path / ".xrtm" / "profiles"
    runs_dir = tmp_path / "runs"
    workflows_dir.mkdir(parents=True)
    profile = WorkflowProfile(name="ops-profile", provider="mock", limit=2, runs_dir=str(runs_dir))
    ProfileStore(profiles_dir).create(profile)

    start_run_dir = runs_dir / "start-run"
    workflow_run_dir = runs_dir / "workflow-run"
    profile_run_dir = runs_dir / "profile-run"
    for path in (start_run_dir, workflow_run_dir, profile_run_dir):
        path.mkdir(parents=True, exist_ok=True)
        (path / "report.html").write_text("<html>ok</html>", encoding="utf-8")

    calls: list[tuple[Any, ...]] = []

    def fake_start_quickstart(*, limit: int, runs_dir: Path, user: str | None):
        calls.append(("start", limit, runs_dir, user))
        return SimpleNamespace(
            run_id="start-run",
            run=SimpleNamespace(run_id="start-run", run_dir=start_run_dir, status="succeeded", provider="mock", command="xrtm start"),
        )

    def fake_run_workflow(
        name: str,
        *,
        workflows_dir: Path,
        runs_dir: Path,
        limit: int | None,
        provider: str | None,
        base_url: str | None,
        model: str | None,
        api_key: str | None,
        max_tokens: int | None,
        write_report: bool,
        user: str | None,
        command: str | None = None,
    ):
        calls.append(("workflow", name, workflows_dir, runs_dir, limit, provider, write_report, user, command))
        return SimpleNamespace(
            run_id="workflow-run",
            run=SimpleNamespace(
                run_id="workflow-run",
                run_dir=workflow_run_dir,
                status="succeeded",
                provider=provider or "mock",
                command=command or f"xrtm workflow run {name}",
            ),
        )

    def fake_run_profile(name: str, *, profiles_dir: Path, runs_dir: Path | None = None):
        calls.append(("profile", name, profiles_dir, runs_dir))
        return SimpleNamespace(
            run_id="profile-run",
            run=SimpleNamespace(run_id="profile-run", run_dir=profile_run_dir, status="succeeded", provider="mock", command=f"xrtm run profile {name}"),
        )

    monkeypatch.setattr(cli_main, "run_doctor", lambda *args, **kwargs: True)
    monkeypatch.setattr(cli_main, "print_pipeline_result", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli_main, "print_post_run_summary", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli_main, "print_quickstart_summary", lambda *args, **kwargs: None)
    monkeypatch.setattr(launch_module, "run_start_quickstart", fake_start_quickstart)
    monkeypatch.setattr(launch_module, "run_registered_workflow", fake_run_workflow)
    monkeypatch.setattr(launch_module, "run_saved_profile", fake_run_profile)

    runner = CliRunner()
    cli_start = runner.invoke(cli, ["start", "--limit", "1", "--runs-dir", str(runs_dir), "--user", "cli-user"])
    cli_workflow = runner.invoke(
        cli,
        [
            "workflow",
            "run",
            "demo-provider-free",
            "--workflows-dir",
            str(workflows_dir),
            "--runs-dir",
            str(runs_dir),
            "--limit",
            "1",
            "--provider",
            "mock",
        ],
    )
    cli_profile = runner.invoke(cli, ["run", "profile", "ops-profile", "--profiles-dir", str(profiles_dir), "--runs-dir", str(runs_dir)])

    assert cli_start.exit_code == 0, cli_start.output
    assert cli_workflow.exit_code == 0, cli_workflow.output
    assert cli_profile.exit_code == 0, cli_profile.output

    server = create_web_server(runs_dir=runs_dir, workflows_dir=workflows_dir, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        _, port = server.server_address
        base_url = f"http://127.0.0.1:{port}"

        web_start = _request_json(f"{base_url}/api/start", method="POST", payload={"limit": 1, "user": "web-user"})
        web_workflow = _request_json(
            f"{base_url}/api/runs",
            method="POST",
            payload={"workflow_name": "demo-provider-free", "limit": 1, "provider": "mock"},
        )
        web_profile = _request_json(f"{base_url}/api/profiles/ops-profile/run", method="POST")

        assert web_start["run_id"] == "start-run"
        assert web_workflow["run_id"] == "workflow-run"
        assert web_profile["run_id"] == "profile-run"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert calls[0] == ("start", 1, runs_dir, "cli-user")
    assert calls[1][:6] == ("workflow", "demo-provider-free", workflows_dir, runs_dir, 1, "mock")
    assert calls[2] == ("profile", "ops-profile", profiles_dir, runs_dir)
    assert calls[3] == ("start", 1, runs_dir, "web-user")
    assert calls[4][:6] == ("workflow", "demo-provider-free", workflows_dir, runs_dir, 1, "mock")
    assert calls[5] == ("profile", "ops-profile", profiles_dir, None)


def test_webui_operator_api_routes_manage_profiles_monitors_and_cleanup(tmp_path: Path) -> None:
    workflows_dir = tmp_path / ".xrtm" / "workflows"
    runs_dir = tmp_path / "runs"
    server = create_web_server(runs_dir=runs_dir, workflows_dir=workflows_dir, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        _, port = server.server_address
        base_url = f"http://127.0.0.1:{port}"

        created_profile = _request_json(
            f"{base_url}/api/profiles",
            method="POST",
            payload={"name": "starter", "template": "starter"},
        )
        assert created_profile["profile"]["name"] == "starter"

        profiles = _request_json(f"{base_url}/api/profiles")
        assert [item["name"] for item in profiles["items"]] == ["starter"]

        profile_detail = _request_json(f"{base_url}/api/profiles/starter")
        assert profile_detail["profile"]["runs_dir"] == str(runs_dir)

        profile_run = _request_json(f"{base_url}/api/profiles/starter/run", method="POST")
        assert profile_run["href"] == f"/runs/{profile_run['run_id']}"

        monitor = _request_json(f"{base_url}/api/monitors", method="POST", payload={"limit": 1, "provider": "mock"})
        monitor_id = monitor["run_id"]
        listed_monitors = _request_json(f"{base_url}/api/monitors")
        assert any(item["run_id"] == monitor_id for item in listed_monitors["items"])

        monitor_detail = _request_json(f"{base_url}/api/monitors/{monitor_id}")
        assert monitor_detail["monitor"]["status"] in {"created", "monitoring"}

        monitor_once = _request_json(f"{base_url}/api/monitors/{monitor_id}/run-once", method="POST")
        assert monitor_once["monitor"]["cycles"] == 1

        paused = _request_json(f"{base_url}/api/monitors/{monitor_id}/pause", method="POST")
        assert paused["monitor"]["status"] == "paused"
        resumed = _request_json(f"{base_url}/api/monitors/{monitor_id}/resume", method="POST")
        assert resumed["monitor"]["status"] == "running"
        halted = _request_json(f"{base_url}/api/monitors/{monitor_id}/halt", method="POST")
        assert halted["monitor"]["status"] == "halted"

        artifacts = _request_json(f"{base_url}/api/artifacts/{profile_run['run_id']}")
        assert any(item["name"] == "run.json" for item in artifacts["artifacts"])

        _request_json(f"{base_url}/api/profiles/starter/run", method="POST")
        preview = _request_json(f"{base_url}/api/artifacts/cleanup-preview", method="POST", payload={"keep": 1})
        assert preview["count"] >= 1

        cleanup = _request_json(
            f"{base_url}/api/artifacts/cleanup",
            method="POST",
            payload={"keep": 1, "confirm": "delete"},
        )
        assert cleanup["count"] == preview["count"]
        removed_run_ids = {item["run_id"] for item in cleanup["items"]}
        for run_id in removed_run_ids:
            assert not (runs_dir / run_id).exists()
        assert len([path for path in runs_dir.iterdir() if path.is_dir()]) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_webui_playground_saveback_routes_persist_workflow_then_profile(tmp_path: Path) -> None:
    workflows_dir = tmp_path / ".xrtm" / "workflows"
    runs_dir = tmp_path / "runs"
    session = launch_module.run_sandbox_session(
        template_id="provider-free-demo",
        question="Will the playground save-back routes persist reusable state?",
        runs_dir=runs_dir,
        write_report=False,
    )

    server = create_web_server(runs_dir=runs_dir, workflows_dir=workflows_dir, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        _, port = server.server_address
        base_url = f"http://127.0.0.1:{port}"

        saved_workflow = _request_json(
            f"{base_url}/api/playground/runs/{session.run_id}/save-workflow",
            method="POST",
            payload={"workflow_name": "playground-web-workflow"},
        )
        assert saved_workflow["workflow"]["name"] == "playground-web-workflow"
        assert Path(saved_workflow["path"]).exists()

        saved_profile = _request_json(
            f"{base_url}/api/playground/runs/{session.run_id}/save-profile",
            method="POST",
            payload={"profile_name": "playground-web-profile"},
        )
        assert saved_profile["profile"]["name"] == "playground-web-profile"
        assert saved_profile["profile"]["workflow_name"] == "playground-web-workflow"
        assert Path(saved_profile["path"]).exists()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_webui_playground_save_profile_route_preserves_shared_error_semantics(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    session = launch_module.run_sandbox_session(
        template_id="provider-free-demo",
        question="Will the shared save-back error reach the WebUI route?",
        runs_dir=runs_dir,
        write_report=False,
    )

    server = create_web_server(runs_dir=runs_dir, workflows_dir=tmp_path / ".xrtm" / "workflows", port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        _, port = server.server_address
        request = Request(
            f"http://127.0.0.1:{port}/api/playground/runs/{session.run_id}/save-profile",
            data=json.dumps({"profile_name": "playground-web-profile"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(HTTPError) as excinfo:
            urlopen(request, timeout=5)
        assert excinfo.value.code == 400
        payload = json.loads(excinfo.value.read().decode("utf-8"))
        assert payload["error"] == "sandbox profile save requires saving the workflow first"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_run_detail_snapshot_surfaces_readable_forecast_rows_and_missing_report(tmp_path: Path) -> None:
    registry = WorkflowRegistry(local_roots=(tmp_path / "workflows",))
    runs_dir = tmp_path / "runs"
    result = run_workbench_workflow(registry, workflow_name="demo-provider-free", runs_dir=runs_dir)
    report_path = runs_dir / result.run_id / "report.html"
    report_path.unlink()

    store = WebUIStateStore(tmp_path / "app-state.db")
    store.ensure_schema()
    store.refresh_indexes(runs_dir=runs_dir, registry=registry)

    snapshot = store.run_detail_snapshot(runs_dir=runs_dir, registry=registry, run_id=result.run_id)

    assert snapshot["schema_version"] == "xrtm.webui.run-detail.v2"
    assert snapshot["observatory"]["runs_href"] == "/runs"
    assert "finished" in snapshot["hero"]["summary"]
    assert snapshot["metadata_groups"][0]["title"] == "Run metadata"
    assert snapshot["probability_summary"]["cards"][0]["label"] == "Forecast rows"
    assert snapshot["score_summary"]["groups"]
    assert snapshot["execution_trace"]["items"]
    assert [item["order"] for item in snapshot["execution_trace"]["items"]] == sorted(
        item["order"] for item in snapshot["execution_trace"]["items"]
    )
    assert snapshot["forecast_table"]["count"] >= 1
    assert snapshot["forecast_table"]["rows"][0]["question_title"]
    assert snapshot["artifacts"]["report"]["available"] is False
    assert snapshot["artifacts"]["report"]["href"] is None
    assert snapshot["artifacts"]["exports"][0]["href"] == f"/api/runs/{result.run_id}/export?format=json"
    assert snapshot["artifacts"]["items"][0]["label"] == "HTML report"
    assert "empty_state" in snapshot["uncertainty_summary"]


def test_compare_snapshot_groups_metrics_and_question_titles(tmp_path: Path) -> None:
    registry = WorkflowRegistry(local_roots=(tmp_path / "workflows",))
    runs_dir = tmp_path / "runs"
    baseline = run_workbench_workflow(registry, workflow_name="demo-provider-free", runs_dir=runs_dir)
    candidate = run_workbench_workflow(registry, workflow_name="demo-provider-free", runs_dir=runs_dir)

    store = WebUIStateStore(tmp_path / "app-state.db")
    store.ensure_schema()
    store.refresh_indexes(runs_dir=runs_dir, registry=registry)

    snapshot = store.compare_snapshot(
        runs_dir=runs_dir,
        candidate_run_id=candidate.run_id,
        baseline_run_id=baseline.run_id,
        refresh=True,
    )

    assert snapshot["schema_version"] == "xrtm.webui.compare.v2"
    assert snapshot["verdict"]["headline"]
    assert snapshot["verdict"]["next_step"]
    assert snapshot["run_pair"]["candidate"]["report"]["available"] is True
    assert snapshot["row_groups"]
    assert snapshot["question_rows"]
    assert snapshot["question_rows"][0]["question_title"]
    assert snapshot["summary_cards"][0]["label"] == "Improved metrics"
    assert snapshot["next_actions"][1]["description"] == snapshot["verdict"]["next_step"]


def test_refresh_indexes_replaces_rows_without_full_table_clears(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = WorkflowRegistry(local_roots=(tmp_path / "workflows",))
    runs_dir = tmp_path / "runs"
    run_workbench_workflow(registry, workflow_name="demo-provider-free", runs_dir=runs_dir)

    store = WebUIStateStore(tmp_path / "app-state.db")
    store.ensure_schema()
    store.refresh_indexes(runs_dir=runs_dir, registry=registry)

    workflows = registry.list_workflows()
    assert len(workflows) >= 2
    filtered_workflows = workflows[:1]
    traces: list[str] = []
    original_connect = store._connect

    def traced_connect():
        connection = original_connect()
        connection.set_trace_callback(traces.append)
        return connection

    monkeypatch.setattr(store, "_connect", traced_connect)
    monkeypatch.setattr(registry, "list_workflows", lambda: filtered_workflows)
    monkeypatch.setattr(webui_state_module, "list_run_records", lambda _: [])

    store.refresh_indexes(runs_dir=runs_dir, registry=registry)

    assert [item["name"] for item in store.list_workflows()] == [workflow.name for workflow in filtered_workflows]
    assert store.list_runs() == []
    statements = {" ".join(statement.split()) for statement in traces}
    assert "DELETE FROM workflow_index" not in statements
    assert "DELETE FROM run_index" not in statements


def test_playground_state_store_runs_shared_sandbox_session(tmp_path: Path) -> None:
    registry = WorkflowRegistry(local_roots=(tmp_path / "workflows",))
    runs_dir = tmp_path / "runs"
    store = WebUIStateStore(tmp_path / "app-state.db")
    store.ensure_schema()

    initial = store.playground_snapshot(runs_dir=runs_dir, registry=registry)
    assert initial["session"]["context_type"] == "workflow"
    assert initial["catalog"]["limits"]["max_questions"] == MAX_SANDBOX_QUESTIONS
    assert initial["catalog"]["limits"]["single_run_questions"] == 1
    assert initial["context_preview"]["canvas"]["nodes"][0]["id"].startswith("node:")
    assert initial["context_preview"]["canvas"]["entry_id"].startswith("node:")
    shell = store.app_shell_snapshot(runs_dir=runs_dir, registry=registry)
    assert shell["app"]["subtitle"] == "Local forecasting cockpit"
    assert shell["app"]["system_status"]["tone"] in {"healthy", "warning"}
    assert shell["app"]["system_status"]["label"] in {"System healthy", "System needs attention"}
    assert shell["app"]["system_status"]["detail"]
    assert "Shared local shell" in shell["app"]["trust_cues"]
    assert "SQLite draft state" in shell["app"]["trust_cues"]
    assert [item["label"] for item in shell["app"]["nav"]] == [
        "Hub",
        "Studio",
        "Playground",
        "Observatory",
        "Batch",
        "Versions",
        "Operations",
        "Control",
        "Advanced",
    ]
    assert any(item["href"] == "/studio" for item in shell["app"]["nav"])
    assert any(item["href"] == "/playground" for item in shell["app"]["nav"])
    assert any(item["href"] == "/batch" for item in shell["app"]["nav"])
    assert any(item["href"] == "/versions" for item in shell["app"]["nav"])
    assert any(item["href"] == "/api" for item in shell["app"]["nav"])
    assert shell["hub"]["doors"][0]["key"] == "quick-forecast"
    assert shell["hub"]["doors"][1]["primary_cta"]["href"].startswith("/studio")
    assert shell["hub"]["doors"][1]["secondary_cta"]["label"] == "Open legacy workbench"
    assert shell["hub"]["templates"][0]["playground_href"].startswith("/playground?context=template")
    assert shell["hub"]["workflows"][0]["studio_href"].startswith("/studio?workflow=")
    local_llm_card = next(item for item in shell["environment"]["cards"] if item["key"] == "local-llm")
    assert local_llm_card["label"] == "Local LLM"
    assert local_llm_card["status"] in {"healthy", "unavailable"}
    runs_snapshot = store.runs_snapshot(runs_dir=runs_dir, registry=registry)
    assert runs_snapshot["analytics"]["summary"]["run_count"] == 0
    assert runs_snapshot["empty_state"]["body"] == "Clear filters or start a provider-free workflow to create a run for inspection."
    assert len(runs_snapshot["analytics"]["calibration_curve"]) == 10
    assert len(runs_snapshot["analytics"]["uncertainty_distribution"]) == 10

    updated = store.update_playground_session(
        registry=registry,
        runs_dir=runs_dir,
        values={
            "context_type": "template",
            "template_id": "provider-free-demo",
            "question_prompt": "Will the playground surface expose ordered step inspection?",
            "question_title": "Playground inspection coverage",
        },
    )
    assert updated["session"]["template_id"] == "provider-free-demo"
    assert updated["session"]["question_title"] == "Playground inspection coverage"

    launched = store.run_playground_session(registry=registry, runs_dir=runs_dir)

    assert launched["last_result"]["run"]["command"] == "xrtm web playground"
    assert launched["last_result"]["context"]["template_id"] == "provider-free-demo"
    assert launched["last_result"]["inspection_steps"][0]["node_id"] == "load_questions"
    assert launched["last_result"]["graph_trace_artifact"]["available"] is True
    assert launched["last_result"]["execution_trace"]["source"] == "graph_trace"
    assert launched["last_result"]["ordered_node_trace"][0]["canvas_node_id"] == "node:load_questions"
    load_node = next(node for node in launched["last_result"]["canvas"]["nodes"] if node["name"] == "load_questions")
    assert load_node["executed"] is True
    assert load_node["trace_order"] == 1
    assert launched["last_result"]["save_back"]["profile"]["status"] == "requires_workflow_save"
    resume = store.resume_target()
    assert resume["kind"] == "playground"
    assert resume["href"] == "/playground"


def test_observatory_analytics_uses_eval_scoring_for_resolved_rows(tmp_path: Path) -> None:
    registry = WorkflowRegistry(local_roots=(tmp_path / "workflows",))
    runs_dir = tmp_path / "runs"
    _write_observatory_run_fixture(
        runs_dir,
        "observatory-canonical",
        probabilities=[0.9, 0.2, 0.6],
        outcomes=[True, False, None],
    )
    store = WebUIStateStore(tmp_path / "app-state.db")
    store.ensure_schema()

    snapshot = store.runs_snapshot(runs_dir=runs_dir, registry=registry)
    analytics = snapshot["analytics"]

    assert analytics["forecast_rows"] == 3
    assert analytics["resolved_rows"] == 2
    assert analytics["summary"]["resolved_score_rows"] == 2
    assert analytics["summary"]["brier"] == pytest.approx(((0.9 - 1.0) ** 2 + (0.2 - 0.0) ** 2) / 2)
    assert analytics["summary"]["ece"] == pytest.approx((abs(1.0 - 0.9) + abs(0.0 - 0.2)) / 2)
    assert analytics["summary"]["log_score"] == pytest.approx((-math.log(0.9) - math.log(0.8)) / 2)
    assert sum(bucket["count"] for bucket in analytics["calibration_curve"]) == 2
    assert sum(bucket["count"] for bucket in analytics["uncertainty_distribution"]) == 3
    assert analytics["workflow_scores"][0]["brier"] == analytics["summary"]["brier"]


def test_playground_state_store_uses_shared_launch_contract(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    registry = WorkflowRegistry(local_roots=(tmp_path / "workflows",))
    runs_dir = tmp_path / "runs"
    store = WebUIStateStore(tmp_path / "app-state.db")
    store.ensure_schema()
    original_resolve = launch_module.resolve_sandbox_context
    calls: list[tuple[str, Any]] = []

    def fake_resolve_sandbox_context(**kwargs: Any):
        calls.append(("resolve", kwargs))
        return original_resolve(**kwargs)

    def fake_run_sandbox_session(**kwargs: Any):
        calls.append(("run", kwargs))
        context = kwargs["context"]
        run_dir = kwargs["runs_dir"] / "sandbox-web-shared"
        run_dir.mkdir(parents=True, exist_ok=True)
        run_payload = {
            "run_id": "sandbox-web-shared",
            "status": "completed",
            "provider": "mock",
            "command": kwargs["command"],
            "created_at": "2026-05-01T10:00:00+00:00",
            "updated_at": "2026-05-01T10:00:05+00:00",
            "artifacts": {"run.json": str(run_dir / "run.json")},
            "summary": {},
        }
        (run_dir / "run.json").write_text(json.dumps(run_payload), encoding="utf-8")
        (run_dir / "run_summary.json").write_text(json.dumps({"summary": "Shared sandbox contract"}), encoding="utf-8")
        (run_dir / "blueprint.json").write_text(json.dumps(context.blueprint.to_json_dict()), encoding="utf-8")
        session = launch_module.SandboxSessionResult(
            run_id="sandbox-web-shared",
            run_dir=run_dir,
            run=run_payload,
            workflow={"name": context.blueprint.name, "title": context.blueprint.title},
            run_summary={"summary": "Shared sandbox contract"},
            context=context,
            labeling={
                "classification": "exploratory",
                "surface": "sandbox",
                "display_label": "Exploratory playground session",
                "notes": ["WebUI loaded the shared contract."],
            },
            questions=({"title": "Shared contract question", "description": "Shared contract question"},),
            inspection_steps=(
                {"order": 4, "node_id": "score", "label": "Score", "node_type": "node", "status": "completed", "output_preview": "Scored rows", "output": {}, "artifacts": [], "artifact_payloads": {}},
                {"order": 1, "node_id": "load_questions", "label": "Load", "node_type": "node", "status": "completed", "output_preview": "Loaded rows", "output": {}, "artifacts": [], "artifact_payloads": {}},
            ),
            save_back={
                "mode": "explicit",
                "workflow": {"status": "ready", "recommended_name": context.blueprint.name},
                "profile": {"status": "ready"},
            },
            total_seconds=0.5,
        )
        (run_dir / "sandbox_session.json").write_text(json.dumps(session.to_json_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return session

    monkeypatch.setattr(launch_module, "resolve_sandbox_context", fake_resolve_sandbox_context)
    monkeypatch.setattr(launch_module, "run_sandbox_session", fake_run_sandbox_session)

    store.update_playground_session(
        registry=registry,
        runs_dir=runs_dir,
        values={
            "context_type": "workflow",
            "workflow_name": "demo-provider-free",
            "question_prompt": "Will the WebUI stay on the shared contract?",
        },
    )
    launched = store.run_playground_session(registry=registry, runs_dir=runs_dir)

    assert [call[0] for call in calls] == ["resolve", "resolve", "run", "resolve"]
    assert launched["last_result"]["run"]["command"] == "xrtm web playground"
    assert [step["node_id"] for step in launched["last_result"]["inspection_steps"]] == ["load_questions", "score"]
    assert launched["last_result"]["graph_trace_artifact"]["available"] is False
    assert launched["last_result"]["graph_trace_artifact"]["empty_state"]["title"] == "No graph trace artifact"
    assert launched["last_result"]["execution_trace"]["source"] == "sandbox"
    assert [step["canvas_node_id"] for step in launched["last_result"]["ordered_node_trace"]] == ["node:load_questions", "node:score"]
    load_node = next(node for node in launched["last_result"]["canvas"]["nodes"] if node["name"] == "load_questions")
    assert load_node["executed"] is True
    assert load_node["trace_source"] == "sandbox"
    assert launched["last_result"]["save_back"]["mode"] == "explicit"
    assert launched["guidance"]["limitations"][0].startswith("This WebUI flow launches one question at a time")


def test_playground_webui_routes_update_state_and_run_session(tmp_path: Path) -> None:
    workflows_dir = tmp_path / "workflows"
    runs_dir = tmp_path / "runs"
    server = create_web_server(runs_dir=runs_dir, workflows_dir=workflows_dir, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        _, port = server.server_address
        base_url = f"http://127.0.0.1:{port}"

        with urlopen(f"{base_url}/playground", timeout=5) as response:
            html = response.read().decode("utf-8")
        assert "Hub · Studio · Playground · Observatory · Batch · Versions · Operations · Control · Advanced" in html
        with urlopen(f"{base_url}/hub", timeout=5) as response:
            hub_html = response.read().decode("utf-8")
        assert "initial_path\": \"/hub\"" in hub_html
        with urlopen(f"{base_url}/studio", timeout=5) as response:
            studio_html = response.read().decode("utf-8")
        assert "initial_path\": \"/studio\"" in studio_html
        with urlopen(f"{base_url}/workbench", timeout=5) as response:
            legacy_html = response.read().decode("utf-8")
        assert "initial_path\": \"/workbench\"" in legacy_html
        for route in ("/batch", "/versions", "/api"):
            with urlopen(f"{base_url}{route}", timeout=5) as response:
                route_html = response.read().decode("utf-8")
            assert f"initial_path\": \"{route}\"" in route_html

        snapshot = _request_json(f"{base_url}/api/playground")
        assert snapshot["session"]["context_type"] == "workflow"
        assert snapshot["catalog"]["templates"][0]["template_id"]

        updated = _request_json(
            f"{base_url}/api/playground",
            method="PATCH",
            payload={
                "context_type": "workflow",
                "workflow_name": "demo-provider-free",
                "question_prompt": "Will the WebUI playground reuse the shared sandbox backend?",
                "resolution_criteria": "Resolves YES if the response comes from the shared sandbox layer.",
            },
        )
        assert updated["session"]["workflow_name"] == "demo-provider-free"
        assert updated["session"]["question_prompt"].startswith("Will the WebUI playground")

        launched = _request_json(
            f"{base_url}/api/playground/run",
            method="POST",
            payload={
                "context_type": "workflow",
                "workflow_name": "demo-provider-free",
                "question_prompt": "Will the WebUI playground reuse the shared sandbox backend?",
            },
        )
        assert launched["last_result"]["labeling"]["classification"] == "exploratory"
        assert launched["last_result"]["run_href"] == f"/runs/{launched['last_result']['run_id']}"
        assert launched["last_result"]["inspection_steps"][1]["node_id"] == "forecast"
        assert launched["last_result"]["execution_trace"]["items"][1]["canvas_node_id"] == "node:forecast"
        assert launched["last_result"]["canvas"]["trace"]["executed_node_count"] >= 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_webui_state_store_product_foundation_schema_and_safe_mutations(tmp_path: Path) -> None:
    registry = WorkflowRegistry(local_roots=(tmp_path / "workflows",))
    store = WebUIStateStore(tmp_path / "app-state.db")
    store.ensure_schema()

    with sqlite3.connect(store.db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
    assert {"workflow_versions", "batch_runs", "batch_rows", "webhook_endpoints", "webhook_deliveries"} <= tables

    workflow_version = store.create_workflow_version(
        registry=registry,
        values={"workflow_name": "demo-provider-free", "label": "Provider-free v1"},
    )
    assert workflow_version["workflow_name"] == "demo-provider-free"
    assert workflow_version["source"] == "workflow"
    assert workflow_version["is_default"] is True
    assert workflow_version["blueprint"]["runtime"]["provider"] == "mock"
    assert workflow_version["graph"] == workflow_version["blueprint"]["graph"]
    assert workflow_version["config"]["runtime"]["provider"] == "mock"
    assert workflow_version["canvas"]["nodes"]
    assert workflow_version["run_provenance"]["execution_linkage"]["status"] == "metadata-only"
    assert workflow_version["metadata"]["no_arbitrary_code"] is True
    fetched_version = store.get_workflow_version(workflow_version["id"])
    assert fetched_version["id"] == workflow_version["id"]
    assert fetched_version["lineage"] == []

    unsafe_payload = registry.load("demo-provider-free").to_json_dict()
    unsafe_payload["name"] = "unsafe-webui-version"
    unsafe_payload["graph"]["nodes"]["forecast"]["implementation"] = "unsafe.custom.plugin_node"
    registry.local_roots[0].mkdir(parents=True, exist_ok=True)
    (registry.local_roots[0] / "unsafe-webui-version.json").write_text(
        json.dumps(unsafe_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="safe product node library"):
        store.create_workflow_version(registry=registry, values={"workflow_name": "unsafe-webui-version"})
    with pytest.raises(ValueError, match="safe product node library"):
        store.create_batch_run(
            registry=registry,
            values={"workflow_name": "unsafe-webui-version", "rows": [{"question": "blocked"}]},
        )

    draft = store.create_draft_session(
        registry=registry,
        runs_dir=tmp_path / "runs",
        creation_mode="scratch",
        draft_workflow_name="foundation-draft",
    )
    draft_version = store.create_workflow_version(
        registry=registry,
        values={"draft_id": draft["id"], "parent_id": workflow_version["id"], "label": "Draft snapshot"},
    )
    assert draft_version["source"] == "draft"
    assert draft_version["parent_id"] == workflow_version["id"]
    assert draft_version["metadata"]["draft"]["draft_workflow_name"] == "foundation-draft"
    fetched_draft_version = store.get_workflow_version(draft_version["id"])
    assert fetched_draft_version["lineage"][0]["id"] == workflow_version["id"]

    diff = store.diff_workflow_versions(workflow_version["id"], draft_version["id"])
    assert diff["summary"]["changed"] > 0
    assert "name" in diff["changed_paths"]

    restored = store.rollback_workflow_version(
        registry=registry,
        version_id=workflow_version["id"],
        values={"mode": "version", "label": "Provider-free restored"},
    )
    assert restored["mode"] == "version"
    assert restored["workflow"]["persisted"] is False
    assert restored["version"]["parent_id"] == workflow_version["id"]
    assert restored["version"]["is_default"] is True
    assert store.get_workflow_version(workflow_version["id"])["is_default"] is False
    assert store.versions_snapshot(registry=registry)["defaults"]["demo-provider-free"] == restored["version"]["id"]

    batch = store.create_batch_run(
        registry=registry,
        values={
            "version_id": workflow_version["id"],
            "rows": [{"question": "Will this dry run stay local?"}, '{"question":"Can pasted JSON parse?"}'],
        },
    )
    assert batch["status"] == "staged"
    assert batch["dry_run"] is False
    assert batch["progress"] == {"current": 0, "total": 2, "percent": 0.0}
    assert batch["rows"][1]["input"]["question"] == "Can pasted JSON parse?"
    assert batch["definition"]["no_arbitrary_code"] is True
    assert batch["definition"]["version_provenance"]["version_id"] == workflow_version["id"]
    assert batch["definition"]["version_provenance"]["execution_linkage"] == "batch-definition-only"
    assert batch["definition"]["blueprint"]["graph"]["nodes"]

    endpoint = store.create_webhook_endpoint(
        {
            "url": "https://example.com/xrtm",
            "events": ["run.completed", "workflow.version.created"],
            "secret": "super-secret-value",
        }
    )
    assert endpoint["enabled"] is True
    assert endpoint["signing"]["secret_set"] is True
    assert "super-secret-value" not in json.dumps(endpoint)

    updated = store.update_webhook_endpoint(endpoint["id"], {"enabled": False, "events": ["batch.completed"]})
    assert updated["enabled"] is False
    assert updated["events"] == ["batch.completed"]

    with pytest.raises(WorkbenchInputError, match="unsupported webhook event"):
        store.create_webhook_endpoint({"url": "https://example.com/hook", "events": ["arbitrary.code"]})

    deleted = store.delete_webhook_endpoint(endpoint["id"])
    assert deleted["deleted"] is True
    assert store.webhooks_snapshot()["items"] == []


def test_webui_product_foundation_api_routes_are_local_first(tmp_path: Path) -> None:
    workflows_dir = tmp_path / "workflows"
    server = create_web_server(runs_dir=tmp_path / "runs", workflows_dir=workflows_dir, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        _, port = server.server_address
        base_url = f"http://127.0.0.1:{port}"

        api_control = _request_json(f"{base_url}/api/api-control")
        assert api_control["schema_version"] == "xrtm.webui.api-control.v2"
        assert api_control["execution_policy"]["no_webui_only_arbitrary_code"] is True
        assert api_control["execution_policy"]["shared_services"]["validation"].endswith("validate_authored_workflow")
        assert api_control["execution_policy"]["shared_services"]["run"].endswith("run_authored_workflow")
        assert api_control["routes"]["versions"]["href"] == "/api/versions"
        assert api_control["routes"]["version_run"]["pattern"] == "/api/versions/{version_id}/run"
        assert api_control["token_behavior"]["required"] is False

        version = _request_json(
            f"{base_url}/api/versions",
            method="POST",
            payload={"workflow_name": "demo-provider-free", "label": "API foundation v1"},
        )
        assert version["id"].startswith("version-")
        assert version["graph"]["nodes"]
        assert version["canvas"]["nodes"]
        assert version["config"]["runtime"]["provider"] == "mock"

        fetched_version = _request_json(f"{base_url}/api/versions/{version['id']}")
        assert fetched_version["id"] == version["id"]
        assert fetched_version["is_default"] is True
        assert fetched_version["lineage"] == []
        assert fetched_version["routes"]["run"]["href"].endswith("/run")

        version_run = _request_json(
            f"{base_url}/api/versions/{version['id']}/run",
            method="POST",
            payload={"user": "api-local"},
        )
        assert version_run["version_id"] == version["id"]
        assert version_run["workflow_name"] == "demo-provider-free"
        assert version_run["href"].startswith("/runs/")

        fetched_version = _request_json(f"{base_url}/api/versions/{version['id']}")
        assert fetched_version["run_provenance"]["last_run_id"] == version_run["run_id"]
        assert fetched_version["run_provenance"]["execution_linkage"]["status"] == "run-linked"

        rollback = _request_json(
            f"{base_url}/api/versions/{version['id']}/rollback",
            method="POST",
            payload={"mode": "version", "label": "API restored v1"},
        )
        assert rollback["version"]["parent_id"] == version["id"]
        assert rollback["version"]["is_default"] is True

        defaulted = _request_json(
            f"{base_url}/api/versions/{version['id']}",
            method="PATCH",
            payload={"set_default": True},
        )
        assert defaulted["id"] == version["id"]
        assert defaulted["is_default"] is True

        version_diff = _request_json(f"{base_url}/api/versions/{version['id']}/diff/{rollback['version']['id']}")
        assert version_diff["summary"]["same_workflow"] is True

        versions = _request_json(f"{base_url}/api/versions")
        assert versions["defaults"]["demo-provider-free"] == version["id"]
        assert versions["guidance"]["no_arbitrary_code"] is True

        batch = _request_json(
            f"{base_url}/api/batch",
            method="POST",
            payload={
                "version_id": version["id"],
                "rows": "Will the batch run stay local?\n{\"question\":\"Does JSONL work?\"}",
            },
        )
        assert batch["id"].startswith("batch-")
        assert batch["status"] == "staged"
        assert batch["rows"][0]["input"]["text"] == "Will the batch run stay local?"
        assert batch["rows"][1]["input"]["question"] == "Does JSONL work?"
        assert batch["definition"]["blueprint"]["graph"]["nodes"]

        batch_snapshot = _request_json(f"{base_url}/api/batch")
        assert batch_snapshot["execution_policy"]["dry_run_only"] is False
        assert batch_snapshot["items"][0]["id"] == batch["id"]

        executed = _request_json(
            f"{base_url}/api/batch/{batch['id']}/run",
            method="POST",
            payload={"wait": True},
        )
        assert executed["status"] == "completed"
        assert executed["summary"]["completed_rows"] == 2
        assert executed["rows"][0]["run_id"]
        assert executed["rows"][0]["result"]["run_href"].startswith("/runs/")

        batch_detail = _request_json(f"{base_url}/api/batch/{batch['id']}")
        assert batch_detail["status"] == "completed"
        assert batch_detail["routes"]["export_csv"].endswith("format=csv")

        with urlopen(f"{base_url}/api/batch/{batch['id']}/export?format=csv", timeout=5) as response:
            export_body = response.read().decode("utf-8")
            export_type = response.headers.get("Content-Type", "")
        assert "row_index,status,question,title,run_id,run_href,probability,error" in export_body
        assert "text/csv" in export_type

        cancelled = _request_json(
            f"{base_url}/api/batch",
            method="POST",
            payload={"workflow_name": "demo-provider-free", "rows": [{"question": "Will cancel work?"}]},
        )
        cancelled = _request_json(
            f"{base_url}/api/batch/{cancelled['id']}",
            method="PATCH",
            payload={"action": "cancel"},
        )
        assert cancelled["status"] == "cancelled"
        assert cancelled["summary"]["cancelled_rows"] == 1

        retried = _request_json(
            f"{base_url}/api/batch/{cancelled['id']}/retry",
            method="POST",
            payload={"wait": True},
        )
        assert retried["status"] == "completed"
        assert retried["summary"]["completed_rows"] == 1

        observatory = _request_json(f"{base_url}/api/runs")
        assert observatory["analytics"]["version_scores"][0]["version_id"] == version["id"]
        assert any(row["version_id"] == version["id"] for row in observatory["analytics"]["score_history"])
        version_filtered = _request_json(f"{base_url}/api/runs?q={version['id']}")
        assert version_filtered["items"]
        assert version_filtered["items"][0]["observatory"]["version_id"] == version["id"]
        run_detail = _request_json(f"{base_url}/api/runs/{version_run['run_id']}")
        assert run_detail["version"]["version_id"] == version["id"]

        endpoint = _request_json(
            f"{base_url}/api/webhooks",
            method="POST",
            payload={"url": "https://example.com/xrtm", "events": ["run.completed"], "secret": "local-secret"},
        )
        assert endpoint["id"].startswith("webhook-")
        assert endpoint["signing"]["secret_set"] is True
        assert "local-secret" not in json.dumps(endpoint)

        patched = _request_json(
            f"{base_url}/api/webhooks/{endpoint['id']}",
            method="PATCH",
            payload={"enabled": False, "events": ["batch.completed"]},
        )
        assert patched["enabled"] is False
        assert patched["events"] == ["batch.completed"]

        with pytest.raises(HTTPError) as exc_info:
            _request_json(
                f"{base_url}/api/webhooks",
                method="POST",
                payload={"url": "file:///not-allowed", "events": ["run.completed"]},
            )
        assert exc_info.value.code == 400
        assert "http or https" in exc_info.value.read().decode("utf-8")

        deleted = _request_json(f"{base_url}/api/webhooks/{endpoint['id']}", method="DELETE")
        assert deleted["deleted"] is True
        assert _request_json(f"{base_url}/api/webhooks")["items"] == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_batch_runner_executes_and_exports_rows(tmp_path: Path) -> None:
    registry = WorkflowRegistry(local_roots=(tmp_path / "workflows",))
    store = WebUIStateStore(tmp_path / "app-state.db")
    store.ensure_schema()
    runs_dir = tmp_path / "runs"

    batch = store.create_batch_run(
        registry=registry,
        values={
            "workflow_name": "demo-provider-free",
            "label": "Local regression batch",
            "rows": [{"question": "Will provider-free batch rows execute?"}, {"question": "Will Observatory see row runs?"}],
        },
    )
    assert batch["status"] == "staged"

    executed = store.start_batch_run(batch_id=batch["id"], registry=registry, runs_dir=runs_dir, values={"wait": True})
    assert executed["status"] == "completed"
    assert executed["summary"]["completed_rows"] == 2
    assert all(row["result"]["run_id"] for row in executed["rows"])
    assert all(row["result"]["probability_summary"]["cards"][0]["value"] >= 1 for row in executed["rows"])

    exported_json = json.loads(store.export_batch_run(batch_id=batch["id"], export_format="json").decode("utf-8"))
    assert exported_json["id"] == batch["id"]
    exported_csv = store.export_batch_run(batch_id=batch["id"], export_format="csv").decode("utf-8")
    assert "batch_id,row_index,status,question,title,run_id,run_href,probability,error" in exported_csv
    assert "/runs/" in exported_csv


def test_webhook_deliveries_are_signed_redacted_and_retryable(tmp_path: Path) -> None:
    received: list[dict[str, Any]] = []

    class WebhookHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            received.append(
                {
                    "headers": {key.lower(): value for key, value in self.headers.items()},
                    "body": body,
                }
            )
            status = 500 if len(received) == 1 else 200
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"retry later" if status == 500 else b"ok")

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), WebhookHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        _, port = server.server_address
        store = WebUIStateStore(tmp_path / "app-state.db")
        store.ensure_schema()
        endpoint = store.create_webhook_endpoint(
            {
                "url": f"http://127.0.0.1:{port}/hooks",
                "events": ["run.completed"],
                "secret": "local-secret-value",
            }
        )
        failed = store.dispatch_webhook_event(
            "run.completed",
            {"api_key": "top-secret", "nested": {"token": "hidden"}, "visible": "ok"},
            endpoint_id=endpoint["id"],
        )[0]
        assert failed["status"] == "failed"
        assert failed["attempts"] == 1
        assert failed["next_attempt_at"] is not None
        assert received[0]["headers"]["x-xrtm-signature"].startswith("sha256=")
        assert "top-secret" not in received[0]["body"]
        assert "hidden" not in received[0]["body"]
        assert "[redacted]" in received[0]["body"]

        delivered = store.retry_webhook_delivery(failed["id"])
        assert delivered["status"] == "delivered"
        assert delivered["attempts"] == 2
        snapshot = store.webhooks_snapshot()
        assert snapshot["routes"]["test"]["href"].endswith("/test")
        assert snapshot["routes"]["retry_delivery"]["href"].endswith("/retry")
        assert snapshot["deliveries"][0]["status"] == "delivered"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _post_form(url: str, values: dict[str, str]):
    payload = urlencode(values).encode("utf-8")
    request = Request(
        url,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    return urlopen(request, timeout=5)


def _request_text(url: str) -> tuple[str, str]:
    with urlopen(url, timeout=5) as response:
        return response.read().decode("utf-8"), response.headers.get("Content-Type", "")



def _request_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    request = Request(
        url,
        data=None if payload is None else json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _extract_bootstrap_payload(html: str) -> dict[str, Any]:
    match = _BOOTSTRAP_PAYLOAD_RE.search(html)
    assert match is not None
    return json.loads(match.group("payload"))
