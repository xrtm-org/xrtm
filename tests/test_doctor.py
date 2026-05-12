import re
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from xrtm.cli.main import cli

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_PACKAGE_VERSIONS = {
    "xrtm": "0.3.1",
    "xrtm-data": "0.2.6",
    "xrtm-eval": "0.2.5",
    "xrtm-forecast": "0.6.7",
    "xrtm-train": "0.2.6",
}


def test_doctor_reports_provider_free_readiness_and_next_steps() -> None:
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
            result = runner.invoke(cli, ["doctor"])

    output = _strip_ansi(result.output)
    assert result.exit_code == 0, output
    assert "XRTM Doctor" in output
    assert "xrtm-forecast" in output
    assert "Provider-Free Smoke/Baseline Checks" in output
    assert "Default provider-free smoke/baseline first run: READY" in output
    assert "Released next command: xrtm start --runs-dir runs" in output
    assert "xrtm doctor verifies package health" in output
    assert "runs/ will be created" in output
    assert "xrtm runs show latest --runs-dir runs" in output
    assert "xrtm artifacts inspect --latest --runs-dir runs" in output
    assert "xrtm report html --latest --runs-dir runs" in output
    assert "xrtm workflow list" in output
    assert "xrtm workflow show demo-provider-free" in output
    assert "xrtm profile starter my-local" in output
    assert "local OpenAI-compatible endpoint profile" in output
    assert "Coding-agent CLI contracts are a separate integration category" in output
    assert "If released docs ever claim cloud/API support" in output
    assert "commercial OpenAI-compatible profile" in output
    assert "Status: not ready (optional)" in output


def test_doctor_keeps_local_llm_health_secondary_to_default_readiness() -> None:
    runner = CliRunner()
    local_status = {
        "base_url": "http://127.0.0.1:8000/v1",
        "health_url": "http://127.0.0.1:8000/health",
        "models_url": "http://127.0.0.1:8000/v1/models",
        "healthy": False,
        "models": [],
        "gpu": {"available": False},
        "error": "service unavailable",
    }

    with runner.isolated_filesystem():
        with patch("xrtm.product.doctor.package_versions", return_value=_PACKAGE_VERSIONS), patch(
            "xrtm.product.doctor.local_llm_status", return_value=local_status
        ):
            result = runner.invoke(cli, ["doctor"])

    output = _strip_ansi(result.output)
    assert result.exit_code == 0, output
    assert "Default provider-free smoke/baseline first run: READY" in output
    assert "Health check error: service unavailable" in output
    assert "Use xrtm providers doctor or xrtm local-llm status" in output


def test_doctor_fails_when_default_runs_dir_is_blocked() -> None:
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
        Path("runs").write_text("blocked", encoding="utf-8")
        with patch("xrtm.product.doctor.package_versions", return_value=_PACKAGE_VERSIONS), patch(
            "xrtm.product.doctor.local_llm_status", return_value=local_status
        ):
            result = runner.invoke(cli, ["doctor"])

    output = _strip_ansi(result.output)
    assert result.exit_code == 1, output
    assert "Default provider-free smoke/baseline first run: NOT READY" in output
    assert "runs exists but is not a directory." in output
    assert "Default runs dir: Remove or rename runs" in output
    assert "When doctor shows READY" in output
    assert "xrtm start --runs-dir runs" in output


def _strip_ansi(output: str) -> str:
    return _ANSI_RE.sub("", output)
