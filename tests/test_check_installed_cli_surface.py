from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

import pytest


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "check_installed_cli_surface.py"
    spec = importlib.util.spec_from_file_location("check_installed_cli_surface", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_fake_xrtm(
    tmp_path: Path,
    *,
    help_output: str,
    workflow_list_output: str,
    workflow_show_output: str,
) -> Path:
    script_path = tmp_path / "fake-xrtm"
    script_path.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env python3
            import sys

            args = sys.argv[1:]
            if args == ["--help"]:
                print({help_output!r})
                raise SystemExit(0)
            if args == ["workflow", "list"]:
                print({workflow_list_output!r})
                raise SystemExit(0)
            if args == ["workflow", "show", "demo-provider-free"]:
                print({workflow_show_output!r})
                raise SystemExit(0)
            print(f"unexpected args: {{args}}")
            raise SystemExit(2)
            """
        ),
        encoding="utf-8",
    )
    script_path.chmod(0o755)
    return script_path


def test_validate_cli_surface_accepts_required_commands(tmp_path: Path) -> None:
    module = _load_module()
    fake_xrtm = _write_fake_xrtm(
        tmp_path,
        help_output="doctor start artifacts runs report web workflow",
        workflow_list_output="demo-provider-free flagship-benchmark",
        workflow_show_output="demo-provider-free Runtime provider",
    )

    module.validate_cli_surface(fake_xrtm)


def test_validate_cli_surface_rejects_missing_workflow_command(tmp_path: Path) -> None:
    module = _load_module()
    fake_xrtm = _write_fake_xrtm(
        tmp_path,
        help_output="doctor start artifacts runs report web",
        workflow_list_output="demo-provider-free flagship-benchmark",
        workflow_show_output="demo-provider-free Runtime provider",
    )

    with pytest.raises(RuntimeError, match="xrtm --help is missing required entries: workflow"):
        module.validate_cli_surface(fake_xrtm)


def test_validate_cli_surface_rejects_missing_builtin_workflow(tmp_path: Path) -> None:
    module = _load_module()
    fake_xrtm = _write_fake_xrtm(
        tmp_path,
        help_output="doctor start artifacts runs report web workflow",
        workflow_list_output="demo-provider-free",
        workflow_show_output="demo-provider-free Runtime provider",
    )

    with pytest.raises(RuntimeError, match="xrtm workflow list is missing required entries: flagship-benchmark"):
        module.validate_cli_surface(fake_xrtm)
