from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "docker_provider_free_acceptance.py"
    spec = importlib.util.spec_from_file_location("docker_provider_free_acceptance", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_default_artifacts_dir_uses_docker_provider_free_path() -> None:
    module = _load_module()

    path = module.default_artifacts_dir(Path("/workspace"), "20260507T190000Z")

    assert path == Path("/workspace/acceptance-studies/docker-provider-free/20260507T190000Z")


def test_install_commands_separate_wheelhouse_and_pypi_modes() -> None:
    module = _load_module()
    venv_python = Path("/venv/bin/python")

    wheelhouse = module.wheelhouse_install_command(venv_python, Path("/wheelhouse"), ["xrtm==0.3.0"])
    pypi = module.pypi_install_command(venv_python, ["xrtm==0.3.0"])

    assert "--no-index" in wheelhouse
    assert "/wheelhouse" in wheelhouse
    assert "--no-index" not in pypi
    assert pypi[-1] == "xrtm==0.3.0"


def test_default_specs_support_repo_root_equal_to_workspace_root(tmp_path) -> None:
    module = _load_module()
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "xrtm"\nversion = "0.3.0"\n', encoding="utf-8")
    forecast_dir = tmp_path / "forecast"
    forecast_dir.mkdir()
    (forecast_dir / "pyproject.toml").write_text('[project]\nname = "xrtm-forecast"\nversion = "0.6.6"\n', encoding="utf-8")

    xrtm_spec, forecast_spec = module.default_specs(tmp_path, tmp_path)

    assert xrtm_spec == "xrtm==0.3.0"
    assert forecast_spec == "xrtm-forecast==0.6.6"


def test_repo_source_dir_prefers_repo_root_when_workspace_has_no_xrtm_checkout(tmp_path: Path) -> None:
    module = _load_module()
    workspace_root = tmp_path / "workspace"
    xrtm_repo_root = workspace_root
    workspace_root.mkdir()

    resolved = module.repo_source_dir("xrtm", workspace_root, xrtm_repo_root)

    assert resolved == xrtm_repo_root


def test_repo_source_dir_keeps_sibling_checkout_for_non_xrtm_repo(tmp_path: Path) -> None:
    module = _load_module()
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    resolved = module.repo_source_dir("forecast", workspace_root, workspace_root)

    assert resolved == workspace_root / "forecast"


def test_docker_run_command_is_disposable_and_mounts_persistent_artifacts(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module.os, "getuid", lambda: 1000)
    monkeypatch.setattr(module.os, "getgid", lambda: 1001)
    config = module.HostConfig(
        workspace_root=Path("/workspace"),
        xrtm_repo_root=Path("/workspace/xrtm"),
        artifact_source="wheelhouse",
        artifacts_dir=Path("/artifacts-host"),
        wheelhouse_dir=Path("/wheelhouse-host"),
        image_tag="xrtm-provider-free-acceptance:py311",
        python_image="python:3.11-slim",
        xrtm_spec="xrtm==0.3.0",
        forecast_spec="xrtm-forecast==0.6.6",
    )

    command = module.docker_run_command(config)

    assert command[:3] == ["docker", "run", "--rm"]
    assert "--user" in command
    assert "/workspace:/workspace:ro" in command
    assert "/artifacts-host:/artifacts" in command
    assert "/wheelhouse-host:/wheelhouse:ro" in command
    assert command[-2:] == ["--wheelhouse-dir", "/wheelhouse"]


def test_docker_run_command_supports_repo_root_equal_to_workspace_root(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module.os, "getuid", lambda: 1000)
    monkeypatch.setattr(module.os, "getgid", lambda: 1001)
    config = module.HostConfig(
        workspace_root=Path("/workspace-root"),
        xrtm_repo_root=Path("/workspace-root"),
        artifact_source="wheelhouse",
        artifacts_dir=Path("/artifacts-host"),
        wheelhouse_dir=Path("/wheelhouse-host"),
        image_tag="xrtm-provider-free-acceptance:py311",
        python_image="python:3.11-slim",
        xrtm_spec="xrtm==0.3.0",
        forecast_spec="xrtm-forecast==0.6.6",
    )

    command = module.docker_run_command(config)
    repo_root_index = command.index("--xrtm-repo-root")

    assert command[repo_root_index + 1] == "/workspace"


def test_prepare_host_artifacts_dir_uses_managed_sandbox_when_requested(tmp_path, monkeypatch) -> None:
    module = _load_module()
    workspace_root = tmp_path / "workspace"
    requested_dir = tmp_path / "requested-artifacts"
    manager_path = tmp_path / "sandbox_manager.py"
    registry_root = tmp_path / "registry"
    workspace_root.mkdir()
    manager_path.write_text("# stub\n", encoding="utf-8")
    created_dir = tmp_path / "managed-artifacts"
    captured: dict[str, object] = {}

    def fake_run_sandbox_manager_json(manager, command, *, registry_root=None):
        captured["manager_path"] = manager
        captured["command"] = command
        captured["registry_root"] = registry_root
        return {
            "id": "sandbox-123",
            "path": str(created_dir),
            "state": "active",
            "purpose": "docker-provider-free acceptance (pypi)",
            "type": "validation",
            "expires_at": "2026-05-12T00:00:00Z",
            "cleanup_policy": {"mode": "manual"},
            "integrity": {
                "manifest_path": str(registry_root / "manifests" / "sandbox-123.json"),
                "registry_root": str(registry_root),
            },
        }

    monkeypatch.setattr(module, "run_sandbox_manager_json", fake_run_sandbox_manager_json)
    args = module.build_parser().parse_args(
        [
            "host",
            "--artifact-source",
            "pypi",
            "--managed-sandbox",
            "--artifacts-dir",
            str(requested_dir),
            "--sandbox-manager",
            str(manager_path),
            "--sandbox-registry-root",
            str(registry_root),
            "--sandbox-ttl-hours",
            "12",
            "--sandbox-cleanup-policy",
            "manual",
        ]
    )

    artifacts_dir, managed = module.prepare_host_artifacts_dir(
        args=args,
        workspace_root_path=workspace_root,
        repo_name="xrtm",
        purpose="docker-provider-free acceptance (pypi)",
        default_dir_factory=module.default_artifacts_dir,
    )

    assert artifacts_dir == created_dir
    assert artifacts_dir.is_dir()
    assert managed is not None
    assert managed.manager_path == manager_path
    assert managed.registry_root == registry_root
    assert captured["manager_path"] == manager_path
    assert captured["registry_root"] == registry_root
    assert captured["command"] == [
        "create",
        "--repo",
        "xrtm",
        "--purpose",
        "docker-provider-free acceptance (pypi)",
        "--type",
        "validation",
        "--cleanup-policy",
        "manual",
        "--ttl-hours",
        "12.0",
        "--path",
        str(requested_dir),
    ]


def test_run_first_success_uses_released_start_journey(tmp_path, monkeypatch) -> None:
    module = _load_module()
    calls: list[list[str]] = []
    written: dict[str, object] = {}

    def fake_run_logged(command, *, log_path, cwd=None, env=None):
        calls.append(command)
        return None

    def fake_load_json(path: Path):
        if path.name == "run.json":
            return {"status": "completed"}
        if path.name == "run_summary.json":
            return {"forecast_count": 1}
        raise AssertionError(f"unexpected load_json path: {path}")

    monkeypatch.setattr(module, "run_logged", fake_run_logged)
    monkeypatch.setattr(module, "latest_run_id", lambda runs_dir: "run-123")
    monkeypatch.setattr(module, "discover_run_ids", lambda runs_dir: ["run-123"])
    monkeypatch.setattr(module, "new_run_id", lambda previous_run_ids, runs_dir: "run-456")
    monkeypatch.setattr(module, "load_json", fake_load_json)
    monkeypatch.setattr(module, "write_json", lambda path, payload: written.update(path=path, payload=payload))

    summary = module.run_first_success({}, tmp_path)

    journey_dir = tmp_path / "xrtm-release" / "first-success"
    runs_dir = journey_dir / "runs"
    assert calls == [
        ["xrtm", "doctor"],
        ["xrtm", "start", "--runs-dir", str(runs_dir)],
        ["xrtm", "workflow", "list"],
        ["xrtm", "workflow", "show", "demo-provider-free"],
        ["xrtm", "workflow", "run", "demo-provider-free", "--runs-dir", str(runs_dir)],
        ["xrtm", "runs", "show", "latest", "--runs-dir", str(runs_dir)],
        ["xrtm", "artifacts", "inspect", "--latest", "--runs-dir", str(runs_dir)],
        ["xrtm", "report", "html", "--latest", "--runs-dir", str(runs_dir)],
        ["xrtm", "web", "--runs-dir", str(runs_dir), "--smoke"],
    ]
    assert summary == {
        "run_id": "run-123",
        "workflow_run_id": "run-456",
        "status": "completed",
        "forecast_count": 1,
        "report_exists": False,
        "blueprint_exists": False,
    }
    assert written["path"] == journey_dir / "summary.json"
    assert written["payload"] == summary


def test_run_workflow_authoring_covers_cli_and_webui_paths(tmp_path, monkeypatch) -> None:
    module = _load_module()
    calls: list[list[str]] = []
    captured_urls: list[tuple[str, str]] = []
    workflows_dir = tmp_path / "xrtm-release" / "workflow-authoring" / ".xrtm" / "workflows"
    runs_dir = tmp_path / "xrtm-release" / "workflow-authoring" / "runs"

    def fake_run_logged(command, *, log_path, cwd=None, env=None):
        calls.append(command)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("$ " + " ".join(command) + "\n", encoding="utf-8")
        if command[:2] == ["xrtm", "start"]:
            run_dir = runs_dir / "baseline-run"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "run.json").write_text(json.dumps({"status": "completed"}), encoding="utf-8")
        elif command[:4] == ["xrtm", "workflow", "create", "scratch"]:
            workflows_dir.mkdir(parents=True, exist_ok=True)
            (workflows_dir / "gate2-scratch-authoring.json").write_text("{}", encoding="utf-8")
        elif command[:4] == ["xrtm", "workflow", "run", "gate2-scratch-authoring"]:
            run_dir = runs_dir / "scratch-run"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "run.json").write_text(json.dumps({"status": "completed"}), encoding="utf-8")
        elif command[:3] == ["xrtm", "report", "html"]:
            scratch_run_dir = runs_dir / "scratch-run"
            scratch_run_dir.mkdir(parents=True, exist_ok=True)
            (scratch_run_dir / "report.html").write_text("<html>scratch</html>", encoding="utf-8")
        elif command[:4] == ["xrtm", "workflow", "create", "clone"]:
            workflows_dir.mkdir(parents=True, exist_ok=True)
            (workflows_dir / "gate2-clone-authoring.json").write_text("{}", encoding="utf-8")
        elif command[:4] == ["xrtm", "workflow", "run", "gate2-clone-authoring"]:
            run_dir = runs_dir / "clone-run"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "run.json").write_text(json.dumps({"status": "completed"}), encoding="utf-8")
        return None

    def fake_fetch_json(url, *, output_path, method="GET", payload=None):
        captured_urls.append((method, url))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if url.endswith("/api/health"):
            body = {"ready": True}
        elif url.endswith("/api/authoring/catalog"):
            body = {
                "creation_modes": [{"key": "scratch"}, {"key": "template"}, {"key": "clone"}],
                "templates": [{"template_id": "provider-free-demo"}],
            }
        elif url.endswith("/api/drafts") and method == "POST":
            workflows_dir.mkdir(parents=True, exist_ok=True)
            (workflows_dir / "gate2-template-authoring.json").write_text("{}", encoding="utf-8")
            body = {"id": "draft-123", "draft_workflow_name": "gate2-template-authoring"}
        elif url.endswith("/api/drafts/draft-123") and method == "PATCH":
            body = {"authoring": {"core_form": {"title": "Gate 2 template workflow"}}}
        elif url.endswith("/api/drafts/draft-123") and method == "GET":
            body = {"workflow": {"source": "local"}}
        elif url.endswith("/api/drafts/draft-123/validate"):
            body = {"validation": {"ok": True}}
        elif url.endswith("/api/drafts/draft-123/run"):
            run_dir = runs_dir / "web-run"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "run.json").write_text(json.dumps({"status": "completed"}), encoding="utf-8")
            body = {"run_id": "web-run", "compare": {"baseline_run_id": "baseline-run"}}
        elif url.endswith("/api/runs/web-run"):
            body = {"summary": {"status": "completed"}}
        elif url.endswith("/api/runs/web-run/compare/baseline-run"):
            body = {"baseline_run_id": "baseline-run", "rows": [{"metric": "status"}]}
        elif url.endswith("/api/runs/web-run/report"):
            run_dir = runs_dir / "web-run"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "report.html").write_text("<html>report</html>", encoding="utf-8")
            body = {"report_path": str(run_dir / "report.html")}
        else:  # pragma: no cover - defensive fallback
            raise AssertionError(f"unexpected url: {method} {url}")
        output_path.write_text(json.dumps(body), encoding="utf-8")
        return body

    def fake_fetch_text(url, *, output_path):
        captured_urls.append(("GET", url))
        if url.endswith("/report"):
            body = "<html>report</html>"
        else:
            body = "<html>Loading the local-first app shell</html>"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(body, encoding="utf-8")
        return body

    class DummyPopen:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def terminate(self):
            return None

        def wait(self, timeout=None):
            return 0

        def kill(self):
            return None

    monkeypatch.setattr(module, "run_logged", fake_run_logged)
    monkeypatch.setattr(module, "reserve_local_port", lambda: 8876)
    monkeypatch.setattr(module, "wait_for_web_server", lambda base_url, timeout_seconds=15.0: {"ready": True})
    monkeypatch.setattr(module, "fetch_json", fake_fetch_json)
    monkeypatch.setattr(module, "fetch_text", fake_fetch_text)
    monkeypatch.setattr(module.subprocess, "Popen", DummyPopen)

    summary = module.run_workflow_authoring({}, tmp_path)

    journey_dir = tmp_path / "xrtm-release" / "workflow-authoring"
    assert calls == [
        ["xrtm", "start", "--runs-dir", str(runs_dir)],
        [
            "xrtm",
            "workflow",
            "create",
            "scratch",
            "gate2-scratch-authoring",
            "--title",
            "Gate 2 scratch workflow",
            "--description",
            "Provider-free scratch workflow created in clean-room validation.",
            "--question-limit",
            "1",
            "--max-tokens",
            "512",
            "--workflows-dir",
            str(workflows_dir),
        ],
        ["xrtm", "workflow", "validate", "gate2-scratch-authoring", "--workflows-dir", str(workflows_dir)],
        ["xrtm", "workflow", "run", "gate2-scratch-authoring", "--workflows-dir", str(workflows_dir), "--runs-dir", str(runs_dir)],
        ["xrtm", "runs", "show", "scratch-run", "--runs-dir", str(runs_dir)],
        ["xrtm", "runs", "compare", "baseline-run", "scratch-run", "--runs-dir", str(runs_dir)],
        ["xrtm", "report", "html", str(runs_dir / "scratch-run")],
        ["xrtm", "workflow", "create", "clone", "demo-provider-free", "gate2-clone-authoring", "--workflows-dir", str(workflows_dir)],
        [
            "xrtm",
            "workflow",
            "edit",
            "metadata",
            "gate2-clone-authoring",
            "--title",
            "Gate 2 cloned workflow",
            "--description",
            "Cloned workflow proved during clean-room validation.",
            "--tag",
            "gate2",
            "--tag",
            "clone",
            "--workflows-dir",
            str(workflows_dir),
        ],
        ["xrtm", "workflow", "validate", "gate2-clone-authoring", "--workflows-dir", str(workflows_dir)],
        [
            "xrtm",
            "workflow",
            "run",
            "gate2-clone-authoring",
            "--workflows-dir",
            str(workflows_dir),
            "--runs-dir",
            str(runs_dir),
            "--limit",
            "1",
        ],
    ]
    assert summary == {
        "baseline_run_id": "baseline-run",
        "cli": {
            "scratch_workflow_path": str(workflows_dir / "gate2-scratch-authoring.json"),
            "scratch_run_id": "scratch-run",
            "scratch_status": "completed",
            "scratch_report_exists": True,
            "clone_workflow_path": str(workflows_dir / "gate2-clone-authoring.json"),
            "clone_run_id": "clone-run",
            "clone_status": "completed",
        },
        "webui": {
            "catalog_modes": ["scratch", "template", "clone"],
            "draft_id": "draft-123",
            "workflow_name": "gate2-template-authoring",
            "workflow_path": str(workflows_dir / "gate2-template-authoring.json"),
            "updated_title": "Gate 2 template workflow",
            "validate_ok": True,
            "candidate_run_id": "web-run",
            "candidate_status": "completed",
            "compare_baseline_run_id": "baseline-run",
            "compare_row_count": 1,
            "report_exists": True,
            "workbench_route_ok": True,
            "workflow_detail_route_ok": True,
            "run_detail_route_ok": True,
            "compare_route_ok": True,
            "report_route_ok": True,
            "draft_source": "local",
            "health_ready": True,
        },
    }
    assert (journey_dir / "summary.json").exists()
    assert any(url.endswith("/api/authoring/catalog") for _, url in captured_urls)
    assert any(url.endswith("/runs/web-run/compare/baseline-run") for _, url in captured_urls)


def test_run_playground_covers_cli_and_webui_paths(tmp_path, monkeypatch) -> None:
    module = _load_module()
    calls: list[list[str]] = []
    captured_urls: list[tuple[str, str]] = []
    journey_dir = tmp_path / "xrtm-release" / "playground"
    runs_dir = journey_dir / "runs"
    workflows_dir = journey_dir / ".xrtm" / "workflows"
    profiles_dir = journey_dir / ".xrtm" / "profiles"

    def cli_session_payload() -> dict[str, object]:
        return {
            "schema_version": "xrtm.sandbox-session.v1",
            "run_id": "cli-playground-run",
            "run": {"provider": "mock", "status": "completed"},
            "context": {"context_type": "workflow", "workflow_name": "demo-provider-free"},
            "labeling": {
                "classification": "exploratory",
                "inspection_mode": "read-only ordered step inspection",
            },
            "questions": [{"title": "CLI playground question"}],
            "inspection_steps": [
                {
                    "order": 1,
                    "node_id": "load_questions",
                    "label": "Load questions",
                    "artifact_payloads": {"questions": [{"title": "CLI playground question"}]},
                },
                {
                    "order": 2,
                    "node_id": "forecast",
                    "label": "Forecast",
                    "artifact_payloads": {"forecasts": [{"question_id": "playground-1-1"}]},
                },
                {
                    "order": 3,
                    "node_id": "score",
                    "label": "Score",
                    "artifact_payloads": {"eval": {"total_evaluations": 0}},
                },
            ],
            "save_back": {
                "mode": "explicit",
                "workflow": {"status": "ready", "recommended_name": "demo-provider-free"},
                "profile": {"status": "ready", "workflow_name": "demo-provider-free"},
            },
        }

    def web_session_payload() -> dict[str, object]:
        return {
            "schema_version": "xrtm.sandbox-session.v1",
            "run_id": "web-playground-run",
            "run": {"provider": "mock", "status": "completed"},
            "context": {"context_type": "template", "template_id": "provider-free-demo"},
            "labeling": {
                "classification": "exploratory",
                "inspection_mode": "read-only ordered step inspection",
            },
            "questions": [{"title": "Web playground question"}],
            "inspection_steps": [
                {
                    "order": 1,
                    "node_id": "load_questions",
                    "label": "Load questions",
                    "artifact_payloads": {"questions": [{"title": "Web playground question"}]},
                },
                {
                    "order": 2,
                    "node_id": "forecast",
                    "label": "Forecast",
                    "artifact_payloads": {"forecasts": [{"question_id": "playground-1-2"}]},
                },
                {
                    "order": 3,
                    "node_id": "score",
                    "label": "Score",
                    "artifact_payloads": {"eval": {"total_evaluations": 0}},
                },
            ],
            "save_back": {
                "mode": "explicit",
                "workflow": {"status": "ready", "recommended_name": "provider-free-demo"},
                "profile": {"status": "requires_workflow_save", "requires_saved_workflow": True},
            },
        }

    def fake_run_logged(command, *, log_path, cwd=None, env=None):
        calls.append(command)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("$ " + " ".join(command) + "\n", encoding="utf-8")
        if command[:2] == ["xrtm", "start"]:
            run_dir = runs_dir / "baseline-run"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "run.json").write_text(json.dumps({"status": "completed"}), encoding="utf-8")
        elif command[:2] == ["xrtm", "playground"]:
            run_dir = runs_dir / "cli-playground-run"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "run.json").write_text(json.dumps({"status": "completed"}), encoding="utf-8")
            (run_dir / "sandbox_session.json").write_text(json.dumps(cli_session_payload(), indent=2, sort_keys=True), encoding="utf-8")
            log_path.write_text(
                "$ " + " ".join(command) + "\nExploratory playground session\nStep inspection\n",
                encoding="utf-8",
            )
        elif command[:3] == ["xrtm", "report", "html"]:
            target = Path(command[3])
            target.mkdir(parents=True, exist_ok=True)
            (target / "report.html").write_text("<html>report</html>", encoding="utf-8")
        elif command[:3] == ["xrtm", "workflow", "validate"]:
            saved_path = workflows_dir / "gate2-playground-web-workflow.json"
            saved_path.parent.mkdir(parents=True, exist_ok=True)
            saved_path.write_text("{}", encoding="utf-8")
        elif command[:3] == ["xrtm", "profile", "show"]:
            saved_path = profiles_dir / "gate2-playground-web-profile.json"
            saved_path.parent.mkdir(parents=True, exist_ok=True)
            saved_path.write_text(
                json.dumps({"name": "gate2-playground-web-profile", "workflow_name": "gate2-playground-web-workflow"}),
                encoding="utf-8",
            )
        return None

    def fake_fetch_json(url, *, output_path, method="GET", payload=None):
        captured_urls.append((method, url))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if url.endswith("/api/health"):
            body = {"ready": True}
        elif url.endswith("/api/playground") and method == "GET":
            body = {"session": {"context_type": "workflow"}}
        elif url.endswith("/api/playground") and method == "PATCH":
            body = {
                "session": {"context_type": "template", "ready_to_run": True},
                "guidance": {"limitations": ["Inspection is read-only: node identity, order, status, previews, and normalized artifact-backed payloads only."]},
            }
        elif url.endswith("/api/playground/run"):
            run_dir = runs_dir / "web-playground-run"
            run_dir.mkdir(parents=True, exist_ok=True)
            session_payload = web_session_payload()
            (run_dir / "run.json").write_text(json.dumps({"status": "completed"}), encoding="utf-8")
            (run_dir / "sandbox_session.json").write_text(json.dumps(session_payload, indent=2, sort_keys=True), encoding="utf-8")
            body = {
                "last_result": {
                    **session_payload,
                    "run_id": "web-playground-run",
                    "run_href": "/runs/web-playground-run",
                    "report": {"available": True, "href": "/runs/web-playground-run/report"},
                }
            }
        elif url.endswith("/api/runs/web-playground-run"):
            body = {"summary": {"status": "completed"}}
        elif url.endswith("/api/runs/web-playground-run/compare/baseline-run"):
            body = {"baseline_run_id": "baseline-run", "rows": [{"metric": "status"}]}
        elif url.endswith("/api/runs/web-playground-run/report"):
            run_dir = runs_dir / "web-playground-run"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "report.html").write_text("<html>report</html>", encoding="utf-8")
            body = {"report_path": str(run_dir / "report.html")}
        elif url.endswith("/api/playground/runs/web-playground-run/save-workflow"):
            path = workflows_dir / "gate2-playground-web-workflow.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}", encoding="utf-8")
            payload = web_session_payload()
            payload["save_back"]["workflow"]["saved_workflow_name"] = "gate2-playground-web-workflow"
            payload["save_back"]["profile"] = {
                "status": "ready",
                "workflow_name": "gate2-playground-web-workflow",
            }
            (runs_dir / "web-playground-run" / "sandbox_session.json").write_text(
                json.dumps(payload, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            body = {"workflow": {"name": "gate2-playground-web-workflow"}, "path": str(path)}
        elif url.endswith("/api/playground/runs/web-playground-run/save-profile"):
            path = profiles_dir / "gate2-playground-web-profile.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps({"name": "gate2-playground-web-profile", "workflow_name": "gate2-playground-web-workflow"}),
                encoding="utf-8",
            )
            payload = json.loads((runs_dir / "web-playground-run" / "sandbox_session.json").read_text(encoding="utf-8"))
            payload["save_back"]["profile"]["saved_profile_name"] = "gate2-playground-web-profile"
            (runs_dir / "web-playground-run" / "sandbox_session.json").write_text(
                json.dumps(payload, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            body = {
                "profile": {
                    "name": "gate2-playground-web-profile",
                    "workflow_name": "gate2-playground-web-workflow",
                },
                "path": str(path),
            }
        else:  # pragma: no cover - defensive fallback
            raise AssertionError(f"unexpected url: {method} {url}")
        output_path.write_text(json.dumps(body), encoding="utf-8")
        return body

    def fake_fetch_text(url, *, output_path):
        captured_urls.append(("GET", url))
        if url.endswith("/report"):
            body = "<html>report</html>"
        else:
            body = "<html>Loading the local-first app shell</html>"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(body, encoding="utf-8")
        return body

    class DummyPopen:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def terminate(self):
            return None

        def wait(self, timeout=None):
            return 0

        def kill(self):
            return None

    monkeypatch.setattr(module, "run_logged", fake_run_logged)
    monkeypatch.setattr(module, "reserve_local_port", lambda: 8876)
    monkeypatch.setattr(module, "wait_for_web_server", lambda base_url, timeout_seconds=15.0: {"ready": True})
    monkeypatch.setattr(module, "fetch_json", fake_fetch_json)
    monkeypatch.setattr(module, "fetch_text", fake_fetch_text)
    monkeypatch.setattr(module.subprocess, "Popen", DummyPopen)

    summary = module.run_playground({}, tmp_path)

    assert calls == [
        ["xrtm", "start", "--runs-dir", str(runs_dir)],
        [
            "xrtm",
            "playground",
            "--workflow",
            "demo-provider-free",
            "--question",
            "Will the provider-free CLI playground custom-question flow pass Gate 2?",
            "--workflows-dir",
            str(workflows_dir),
            "--runs-dir",
            str(runs_dir),
        ],
        ["xrtm", "runs", "show", "cli-playground-run", "--runs-dir", str(runs_dir)],
        ["xrtm", "runs", "compare", "baseline-run", "cli-playground-run", "--runs-dir", str(runs_dir)],
        ["xrtm", "report", "html", str(runs_dir / "cli-playground-run")],
        ["xrtm", "workflow", "validate", "gate2-playground-web-workflow", "--workflows-dir", str(workflows_dir)],
        ["xrtm", "profile", "show", "gate2-playground-web-profile", "--profiles-dir", str(profiles_dir)],
    ]
    assert summary == {
        "baseline_run_id": "baseline-run",
        "cli": {
            "run_id": "cli-playground-run",
            "provider": "mock",
            "question_count": 1,
            "inspection_step_ids": ["load_questions", "forecast", "score"],
            "inspection_ordered": True,
            "inspection_mode": "read-only ordered step inspection",
            "save_back_mode": "explicit",
            "report_exists": True,
        },
        "webui": {
            "run_id": "web-playground-run",
            "provider": "mock",
            "question_count": 1,
            "inspection_step_ids": ["load_questions", "forecast", "score"],
            "inspection_ordered": True,
            "playground_route_ok": True,
            "run_detail_route_ok": True,
            "compare_route_ok": True,
            "report_route_ok": True,
            "saved_workflow_name": "gate2-playground-web-workflow",
            "saved_profile_name": "gate2-playground-web-profile",
            "saved_profile_workflow_name": "gate2-playground-web-workflow",
            "health_ready": True,
        },
    }
    assert any(url.endswith("/api/playground/run") for _, url in captured_urls)
    assert any(url.endswith("/api/playground/runs/web-playground-run/save-profile") for _, url in captured_urls)
    assert (journey_dir / "summary.json").exists()


def test_run_host_records_managed_sandbox_metadata(tmp_path, monkeypatch) -> None:
    module = _load_module()
    workspace_root = tmp_path / "workspace"
    xrtm_repo_root = workspace_root / "xrtm"
    artifacts_dir = tmp_path / "managed-provider-free"
    manager_path = tmp_path / "sandbox_manager.py"
    registry_root = tmp_path / "registry"
    workspace_root.mkdir()
    xrtm_repo_root.mkdir(parents=True)
    artifacts_dir.mkdir()
    manager_path.write_text("# stub\n", encoding="utf-8")
    managed = module.ManagedSandboxContext(
        manager_path=manager_path,
        registry_root=registry_root,
        manifest={
            "id": "sandbox-123",
            "path": str(artifacts_dir),
            "state": "active",
            "purpose": "docker-provider-free acceptance (pypi)",
            "type": "validation",
            "expires_at": "2026-05-12T00:00:00Z",
            "cleanup_policy": {"mode": "delete"},
            "integrity": {
                "manifest_path": str(registry_root / "manifests" / "sandbox-123.json"),
                "registry_root": str(registry_root),
            },
        },
    )

    def fake_run_logged(command, *, log_path, cwd=None, env=None):
        if command[:2] == ["docker", "run"]:
            (artifacts_dir / "summary.json").write_text(json.dumps({"status": "passed"}), encoding="utf-8")
        return None

    monkeypatch.setattr(
        module,
        "prepare_host_artifacts_dir",
        lambda **kwargs: (artifacts_dir, managed),
    )
    monkeypatch.setattr(module, "default_specs", lambda root, repo_root: ("xrtm==0.3.0", "xrtm-forecast==0.6.6"))
    monkeypatch.setattr(module, "run_logged", fake_run_logged)

    args = module.build_parser().parse_args(
        [
            "host",
            "--workspace-root",
            str(workspace_root),
            "--xrtm-repo-root",
            str(xrtm_repo_root),
            "--artifact-source",
            "pypi",
        ]
    )

    assert module.run_host(args) == 0
    request_payload = json.loads((artifacts_dir / "metadata" / "request.json").read_text(encoding="utf-8"))
    summary_payload = json.loads((artifacts_dir / "summary.json").read_text(encoding="utf-8"))
    managed_payload = json.loads((artifacts_dir / "metadata" / "managed-sandbox.json").read_text(encoding="utf-8"))

    assert request_payload["managed_sandbox"]["id"] == "sandbox-123"
    assert request_payload["managed_sandbox"]["manager_path"] == str(manager_path)
    assert summary_payload["managed_sandbox"]["path"] == str(artifacts_dir)
    assert managed_payload["id"] == "sandbox-123"


def test_run_logged_appends_core_diagnostics_on_failure(tmp_path) -> None:
    module = _load_module()
    log_path = tmp_path / "failure.log"
    (tmp_path / "core.123").write_bytes(b"core")

    with pytest.raises(subprocess.CalledProcessError):
        module.run_logged(
            [sys.executable, "-c", "import sys; print('boom'); sys.exit(7)"],
            log_path=log_path,
            cwd=tmp_path,
        )

    log_text = log_path.read_text(encoding="utf-8")
    assert "boom" in log_text
    assert "[diagnostics]" in log_text
    assert "return code: 7" in log_text
    assert "core.123" in log_text


def test_run_benchmark_matrix_covers_benchmark_and_competition_surfaces(tmp_path, monkeypatch) -> None:
    module = _load_module()
    calls: list[list[str]] = []
    written: dict[str, object] = {}

    def fake_run_logged(command, *, log_path, cwd=None, env=None):
        calls.append(command)
        if "competition" in command:
            run_dir = tmp_path / "xrtm-release" / "benchmark-matrix" / "runs-competition" / "run-competition"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "competition_submission.json").write_text("{}", encoding="utf-8")
        return None

    monkeypatch.setattr(module, "run_logged", fake_run_logged)
    monkeypatch.setattr(module, "latest_run_id", lambda runs_dir: "run-competition")
    monkeypatch.setattr(module, "discover_run_ids", lambda runs_dir: ["run-benchmark-1", "run-benchmark-2"])
    monkeypatch.setattr(module, "write_json", lambda path, payload: written.update(path=path, payload=payload))

    benchmark_output_dir = tmp_path / "xrtm-release" / "benchmark-matrix" / "benchmark-output"
    benchmark_output_dir.mkdir(parents=True)
    (benchmark_output_dir / "compare-summary.json").write_text("{}", encoding="utf-8")
    (benchmark_output_dir / "stress-summary.json").write_text("{}", encoding="utf-8")

    summary = module.run_benchmark_matrix({}, tmp_path)

    journey_dir = tmp_path / "xrtm-release" / "benchmark-matrix"
    benchmark_runs_dir = journey_dir / "runs-benchmark"
    competition_runs_dir = journey_dir / "runs-competition"
    assert calls == [
        [
            "xrtm",
            "benchmark",
            "run",
            "--corpus-id",
            "xrtm-real-binary-v1",
            "--split",
            "eval",
            "--provider",
            "mock",
            "--limit",
            "5",
            "--iterations",
            "2",
            "--runs-dir",
            str(benchmark_runs_dir),
            "--output-dir",
            str(journey_dir / "benchmark-output"),
            "--release-gate-mode",
        ],
        [
            "xrtm",
            "benchmark",
            "compare",
            "--corpus-id",
            "xrtm-real-binary-v1",
            "--split",
            "eval",
            "--limit",
            "5",
            "--runs-dir",
            str(benchmark_runs_dir),
            "--output-dir",
            str(journey_dir / "benchmark-output"),
            "--release-gate-mode",
            "--baseline-label",
            "mock-control",
            "--baseline-provider",
            "mock",
            "--candidate-label",
            "mock-candidate",
            "--candidate-provider",
            "mock",
        ],
        [
            "xrtm",
            "benchmark",
            "stress",
            "--corpus-id",
            "xrtm-real-binary-v1",
            "--split",
            "eval",
            "--limit",
            "3",
            "--repeats",
            "2",
            "--runs-dir",
            str(benchmark_runs_dir),
            "--output-dir",
            str(journey_dir / "benchmark-output"),
            "--release-gate-mode",
            "--baseline-label",
            "mock-control",
            "--baseline-provider",
            "mock",
            "--candidate-label",
            "mock-candidate",
            "--candidate-provider",
            "mock",
        ],
        [
            "xrtm",
            "competition",
            "dry-run",
            "metaculus-cup",
            "--runs-dir",
            str(competition_runs_dir),
            "--provider",
            "mock",
            "--limit",
            "2",
        ],
    ]
    assert summary == {
        "benchmark_artifacts": ["compare-summary.json", "stress-summary.json"],
        "benchmark_run_ids": ["run-benchmark-1", "run-benchmark-2"],
        "competition_bundle_exists": True,
        "competition_run_id": "run-competition",
    }
    assert written["path"] == journey_dir / "summary.json"
    assert written["payload"] == summary


def test_run_product_shell_includes_workflow_authoring_and_playground(tmp_path, monkeypatch) -> None:
    module = _load_module()
    calls: list[str] = []

    def record(name, payload):
        def _inner(*args, **kwargs):
            calls.append(name)
            return payload
        return _inner

    monkeypatch.setattr(module, "create_venv", lambda venv_dir, log_dir, install_env: Path("/fake-venv/bin/python"))
    monkeypatch.setattr(module, "venv_env", lambda venv_python, base_env: {"PATH": "/fake-venv/bin"})
    monkeypatch.setattr(module, "install_specs", lambda *args, **kwargs: calls.append("install_specs"))
    monkeypatch.setattr(module, "write_versions", lambda *args, **kwargs: calls.append("write_versions"))
    monkeypatch.setattr(module, "run_cli_surface_check", lambda *args, **kwargs: calls.append("run_cli_surface_check"))
    monkeypatch.setattr(module, "run_release_claims", lambda *args, **kwargs: calls.append("run_release_claims"))
    monkeypatch.setattr(module, "run_first_success", record("run_first_success", {"status": "first"}))
    monkeypatch.setattr(module, "run_workflow_authoring", record("run_workflow_authoring", {"status": "authoring"}))
    monkeypatch.setattr(module, "run_playground", record("run_playground", {"status": "playground"}))
    monkeypatch.setattr(module, "run_operator", record("run_operator", {"status": "operator"}))
    monkeypatch.setattr(module, "run_research_eval", record("run_research_eval", {"status": "research"}))
    monkeypatch.setattr(module, "run_benchmark_matrix", record("run_benchmark_matrix", {"status": "benchmark"}))

    summary = module.run_product_shell(
        workspace_root_path=tmp_path,
        xrtm_repo_root_path=tmp_path,
        install_source="wheelhouse",
        wheelhouse_dir=tmp_path / "wheelhouse",
        artifacts_dir=tmp_path / "artifacts",
        xrtm_spec="xrtm==0.8.4",
        base_env={},
        scratch_dir=tmp_path / "scratch",
    )

    assert summary == {
        "first_success": {"status": "first"},
        "workflow_authoring": {"status": "authoring"},
        "playground": {"status": "playground"},
        "operator": {"status": "operator"},
        "research_eval": {"status": "research"},
        "benchmark_matrix": {"status": "benchmark"},
    }
    assert "run_workflow_authoring" in calls
    assert "run_playground" in calls
