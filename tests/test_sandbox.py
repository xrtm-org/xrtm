from __future__ import annotations

import json
from pathlib import Path

import pytest

from xrtm.product import launch as launch_module
from xrtm.product.read_models import list_run_records, read_run_detail
from xrtm.product.sandbox import (
    MAX_SANDBOX_QUESTIONS,
    SANDBOX_INSPECTION_MODE,
    SANDBOX_SAVE_BACK_MODE,
    SANDBOX_SESSION_SCHEMA_VERSION,
    SandboxQuestionInput,
    read_sandbox_session,
    resolve_sandbox_context,
    run_sandbox_session,
)
from xrtm.product.workflows import WorkflowRegistry


def test_sandbox_session_runs_workflow_context_and_persists_read_only_inspection(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    registry = WorkflowRegistry(local_roots=(tmp_path / "workflows",))
    context = resolve_sandbox_context(workflow_name="demo-provider-free", registry=registry)

    session = run_sandbox_session(
        context=context,
        question=SandboxQuestionInput(
            title="Will sandbox support ship by June?",
            prompt="Will sandbox support ship by June? Use this as a bounded exploratory prompt.",
            resolution_criteria="Resolves YES if the shared sandbox layer lands before June 30.",
            tags=("custom",),
        ),
        runs_dir=runs_dir,
        write_report=False,
    )

    assert session.context.workflow_name == "demo-provider-free"
    assert session.labeling["classification"] == "exploratory"
    assert session.labeling["benchmark_evidence"] is False
    assert session.save_back["profile"]["status"] == "ready"
    assert session.save_back["profile"]["workflow_name"] == "demo-provider-free"
    assert (session.run_dir / "sandbox_session.json").exists()

    payload = json.loads((session.run_dir / "sandbox_session.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == SANDBOX_SESSION_SCHEMA_VERSION
    assert payload["context"]["workflow_name"] == "demo-provider-free"
    assert payload["labeling"]["inspection_mode"] == SANDBOX_INSPECTION_MODE
    assert payload["labeling"]["save_back_mode"] == SANDBOX_SAVE_BACK_MODE
    assert payload["save_back"]["mode"] == SANDBOX_SAVE_BACK_MODE
    assert [step["node_id"] for step in payload["inspection_steps"]] == [
        "load_questions",
        "forecast",
        "score",
        "backtest",
        "report",
    ]
    assert payload["inspection_steps"][0]["artifact_payloads"]["questions"][0]["title"] == "Will sandbox support ship by June?"
    assert payload["inspection_steps"][1]["artifact_payloads"]["forecasts"][0]["question_id"].startswith("playground-1-")
    assert payload["inspection_steps"][2]["artifact_payloads"]["eval"]["total_evaluations"] == 0
    assert payload["inspection_steps"][3]["artifact_payloads"]["train"]["training_samples"] == 0

    detail = read_run_detail(session.run_dir)
    assert detail["sandbox"]["labeling"]["classification"] == "exploratory"
    records = list_run_records(runs_dir)
    assert records[0]["sandbox"]["classification"] == "exploratory"
    assert records[0]["sandbox"]["workflow_name"] == "demo-provider-free"


def test_read_sandbox_session_normalizes_order_and_contract_metadata() -> None:
    payload = read_sandbox_session(
        {
            "run_id": "sandbox-001",
            "run_dir": "runs/sandbox-001",
            "questions": [{"id": "q2"}, {"id": "q1"}],
            "inspection_steps": [
                {"order": 3, "node_id": "score", "status": "completed"},
                {"order": 1, "node_id": "load_questions", "status": "completed"},
                {"node_id": "forecast", "status": "completed"},
            ],
            "save_back": {"workflow": {"status": "ready"}, "profile": {"status": "ready"}},
        }
    )

    assert [step["node_id"] for step in payload["inspection_steps"]] == ["load_questions", "forecast", "score"]
    assert payload["labeling"]["inspection_mode"] == SANDBOX_INSPECTION_MODE
    assert payload["labeling"]["save_back_mode"] == SANDBOX_SAVE_BACK_MODE
    assert payload["labeling"]["question_count"] == 2
    assert payload["labeling"]["batch"] is True
    assert payload["save_back"]["mode"] == SANDBOX_SAVE_BACK_MODE


def test_sandbox_template_context_prepares_explicit_save_back_state(tmp_path: Path) -> None:
    session = run_sandbox_session(
        template_id="provider-free-demo",
        question="Will the template-backed sandbox session run successfully?",
        runs_dir=tmp_path / "runs",
        write_report=False,
    )

    assert session.context.context_type == "template"
    assert session.context.template_id == "provider-free-demo"
    assert session.save_back["workflow"]["status"] == "ready"
    assert session.save_back["workflow"]["requires_explicit_name"] is True
    assert session.save_back["profile"]["status"] == "requires_workflow_save"
    assert session.save_back["profile"]["requires_saved_workflow"] is True


def test_sandbox_save_workflow_unblocks_profile_save_for_template_sessions(tmp_path: Path) -> None:
    workflows_dir = tmp_path / ".xrtm" / "workflows"
    profiles_dir = tmp_path / ".xrtm" / "profiles"
    session = run_sandbox_session(
        template_id="provider-free-demo",
        question="Will the template-backed sandbox session save successfully?",
        runs_dir=tmp_path / "runs",
        write_report=False,
    )

    saved_workflow = launch_module.save_sandbox_workflow(
        session.run_dir,
        workflow_name="saved-playground-workflow",
        workflows_dir=workflows_dir,
    )
    assert saved_workflow["workflow"]["name"] == "saved-playground-workflow"
    assert Path(saved_workflow["path"]).exists()
    assert WorkflowRegistry(local_roots=(workflows_dir,)).validate("saved-playground-workflow").name == "saved-playground-workflow"

    refreshed = json.loads((session.run_dir / "sandbox_session.json").read_text(encoding="utf-8"))
    assert refreshed["labeling"]["classification"] == "exploratory"
    assert refreshed["save_back"]["profile"]["status"] == "ready"
    assert refreshed["save_back"]["profile"]["workflow_name"] == "saved-playground-workflow"
    assert refreshed["save_back"]["workflow"]["saved_workflow_name"] == "saved-playground-workflow"

    saved_profile = launch_module.save_sandbox_profile(
        session.run_dir,
        profile_name="saved-playground-profile",
        profiles_dir=profiles_dir,
        workflows_dir=workflows_dir,
    )
    assert Path(saved_profile["path"]).exists()
    assert saved_profile["profile"]["workflow_name"] == "saved-playground-workflow"


def test_sandbox_save_profile_requires_saved_workflow_when_session_blueprint_changed(tmp_path: Path) -> None:
    workflows_dir = tmp_path / ".xrtm" / "workflows"
    profiles_dir = tmp_path / ".xrtm" / "profiles"
    registry = WorkflowRegistry(local_roots=(workflows_dir,))
    session = run_sandbox_session(
        workflow_name="demo-provider-free",
        registry=registry,
        question="Will the workflow-backed session reject unsaved graph changes?",
        runs_dir=tmp_path / "runs",
        write_report=False,
    )

    payload = json.loads((session.run_dir / "sandbox_session.json").read_text(encoding="utf-8"))
    payload["save_back"]["workflow"]["blueprint"]["graph"]["edges"].append({"from_node": "load_questions", "to_node": "score"})
    (session.run_dir / "sandbox_session.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="saving workflow changes"):
        launch_module.save_sandbox_profile(
            session.run_dir,
            profile_name="changed-session-profile",
            profiles_dir=profiles_dir,
            workflows_dir=workflows_dir,
        )


def test_sandbox_save_profile_persists_runtime_preferences_and_workflow_reference(tmp_path: Path) -> None:
    workflows_dir = tmp_path / ".xrtm" / "workflows"
    profiles_dir = tmp_path / ".xrtm" / "profiles"
    registry = WorkflowRegistry(local_roots=(workflows_dir,))
    session = run_sandbox_session(
        workflow_name="demo-provider-free",
        registry=registry,
        question="Will the workflow-backed session save a reusable profile?",
        runs_dir=tmp_path / "runs",
        write_report=False,
        provider="mock",
        max_tokens=256,
        user="sandbox-user",
    )

    saved_profile = launch_module.save_sandbox_profile(
        session.run_dir,
        profile_name="workflow-backed-profile",
        profiles_dir=profiles_dir,
        workflows_dir=workflows_dir,
    )
    profile_payload = json.loads(Path(saved_profile["path"]).read_text(encoding="utf-8"))
    assert profile_payload["name"] == "workflow-backed-profile"
    assert profile_payload["workflow_name"] == "demo-provider-free"
    assert profile_payload["provider"] == "mock"
    assert profile_payload["max_tokens"] == 256
    assert profile_payload["user"] == "sandbox-user"
    rerun = launch_module.run_saved_profile("workflow-backed-profile", profiles_dir=profiles_dir)
    rerun_blueprint = json.loads((rerun.run.run_dir / "blueprint.json").read_text(encoding="utf-8"))
    assert rerun_blueprint["name"] == "demo-provider-free"

    refreshed = json.loads((session.run_dir / "sandbox_session.json").read_text(encoding="utf-8"))
    assert refreshed["save_back"]["profile"]["saved_profile_name"] == "workflow-backed-profile"


def test_sandbox_rejects_batches_larger_than_five(tmp_path: Path) -> None:
    registry = WorkflowRegistry(local_roots=(tmp_path / "workflows",))
    with pytest.raises(ValueError, match=f"at most {MAX_SANDBOX_QUESTIONS}"):
        run_sandbox_session(
            workflow_name="demo-provider-free",
            registry=registry,
            questions=[f"Question {index}?" for index in range(MAX_SANDBOX_QUESTIONS + 1)],
            runs_dir=tmp_path / "runs",
        )
