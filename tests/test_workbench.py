import json
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
        observed["validated_workflow"] = workflow_name or blueprint.name
        observed["validated_registry"] = registry
        return {"ok": True, "errors": [], "workflow": workflow_name or blueprint.name}

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
    calls: list[tuple[str, Any, ...]] = []

    def fake_validation_report(
        *,
        workflow_name: str | None = None,
        blueprint: Any | None = None,
        persist: bool = False,
        overwrite: bool = False,
        **_: Any,
    ) -> dict[str, Any]:
        calls.append(("validate", workflow_name, None if blueprint is None else blueprint.name, persist, overwrite))
        return {"ok": True, "errors": [], "workflow": workflow_name or blueprint.name}

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
    assert snapshot["safe_edit"]["aggregate_weight_editors"]
    assert "Overview · Start · Runs · Playground · Operations · Workbench" in html
    assert "version-pill" in html
    assert "/static/app.js" in html
    assert "Loading the local-first app shell" in html


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

    calls: list[tuple[str, Any, ...]] = []

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

    assert "finished" in snapshot["hero"]["summary"]
    assert snapshot["metadata_groups"][0]["title"] == "Run metadata"
    assert snapshot["forecast_table"]["count"] >= 1
    assert snapshot["forecast_table"]["rows"][0]["question_title"]
    assert snapshot["artifacts"]["report"]["available"] is False
    assert snapshot["artifacts"]["report"]["href"] is None
    assert snapshot["artifacts"]["items"][0]["label"] == "HTML report"


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


def test_playground_state_store_runs_shared_sandbox_session(tmp_path: Path) -> None:
    registry = WorkflowRegistry(local_roots=(tmp_path / "workflows",))
    runs_dir = tmp_path / "runs"
    store = WebUIStateStore(tmp_path / "app-state.db")
    store.ensure_schema()

    initial = store.playground_snapshot(runs_dir=runs_dir, registry=registry)
    assert initial["session"]["context_type"] == "workflow"
    assert initial["catalog"]["limits"]["max_questions"] == MAX_SANDBOX_QUESTIONS
    assert initial["catalog"]["limits"]["single_run_questions"] == 1
    shell = store.app_shell_snapshot(runs_dir=runs_dir, registry=registry)
    assert any(item["href"] == "/playground" for item in shell["app"]["nav"])

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
    assert launched["last_result"]["save_back"]["profile"]["status"] == "requires_workflow_save"
    resume = store.resume_target()
    assert resume["kind"] == "playground"
    assert resume["href"] == "/playground"


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
        assert "Overview · Start · Runs · Playground · Operations · Workbench" in html

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



def _request_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    request = Request(
        url,
        data=None if payload is None else json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))
