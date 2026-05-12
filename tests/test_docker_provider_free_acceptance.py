from __future__ import annotations

import importlib.util
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
