import json
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest

from xrtm.product import workbench as workbench_module
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

    def fake_run_workflow_blueprint(
        blueprint: Any, *, command: str, runs_dir: Path, user: str | None
    ) -> SimpleNamespace:
        run_dir = runs_dir / "edited-run"
        run_dir.mkdir(parents=True)
        observed["blueprint"] = blueprint.name
        observed["command"] = command
        observed["runs_dir"] = runs_dir
        observed["user"] = user
        return SimpleNamespace(run=SimpleNamespace(run_id="edited-run", run_dir=run_dir))

    def fake_compare_runs(left_dir: Path, right_dir: Path) -> list[dict[str, object]]:
        observed["compare"] = (left_dir, right_dir)
        return [{"metric": "status", "left": "succeeded", "right": "succeeded"}]

    monkeypatch.setattr(workbench_module, "run_workflow_blueprint", fake_run_workflow_blueprint)
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
    assert observed["blueprint"] == "demo-provider-free"
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


def test_workbench_snapshot_and_html_expose_gui_loop(tmp_path: Path) -> None:
    workflows_dir = tmp_path / "workflows"
    snapshot = workbench_snapshot(Path("missing-runs"), workflows_dir, workflow_name="flagship-benchmark")
    html = render_workbench_html(Path("missing-runs"), workflows_dir, query_string="workflow=flagship-benchmark")

    assert snapshot["canvas"]["nodes"]
    assert snapshot["safe_edit"]["aggregate_weight_editors"]
    assert "Overview · Runs · Workbench" in html
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
