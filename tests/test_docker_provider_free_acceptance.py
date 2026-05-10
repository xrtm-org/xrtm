from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


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
