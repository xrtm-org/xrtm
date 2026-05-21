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
    workflow_help_output: str = "create edit clone list show validate explain run",
    profile_help_output: str = "create starter list show",
    monitor_help_output: str = "start list show run-once",
    workflow_list_output: str,
    workflow_show_output: str,
) -> Path:
    script_path = tmp_path / "fake-xrtm"
    script_path.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env python3
            import json
            import shutil
            import sys
            from pathlib import Path

            HELP_OUTPUT = {help_output!r}
            WORKFLOW_HELP_OUTPUT = {workflow_help_output!r}
            PROFILE_HELP_OUTPUT = {profile_help_output!r}
            MONITOR_HELP_OUTPUT = {monitor_help_output!r}
            WORKFLOW_LIST_OUTPUT = {workflow_list_output!r}
            WORKFLOW_SHOW_OUTPUT = {workflow_show_output!r}
            STATE_PATH = Path({str(tmp_path / "fake-state.json")!r})

            def load_state():
                if STATE_PATH.exists():
                    return json.loads(STATE_PATH.read_text(encoding="utf-8"))
                return {{"counter": 0}}

            def save_state(state):
                STATE_PATH.write_text(json.dumps(state), encoding="utf-8")

            def option_value(flag):
                try:
                    return args[args.index(flag) + 1]
                except (ValueError, IndexError) as exc:
                    raise SystemExit(f"missing required option: {{flag}}") from exc

            def create_run(runs_dir_value, *, command, monitor=False):
                runs_dir = Path(runs_dir_value)
                runs_dir.mkdir(parents=True, exist_ok=True)
                state = load_state()
                state["counter"] += 1
                save_state(state)
                run_id = f"20260501T000000Z-{{state['counter']:04d}}"
                run_dir = runs_dir / run_id
                run_dir.mkdir()
                run_payload = {{"run_id": run_id, "status": "monitoring" if monitor else "completed", "provider": "mock", "command": command}}
                (run_dir / "run.json").write_text(json.dumps(run_payload), encoding="utf-8")
                (run_dir / "run_summary.json").write_text(
                    json.dumps({{"forecast_count": 1, "warning_count": 0, "error_count": 0}}),
                    encoding="utf-8",
                )
                if monitor:
                    (run_dir / "monitor.json").write_text(
                        json.dumps({{"status": "created", "cycles": 0, "watches": [{{"watch_id": "watch-1", "status": "created", "trajectory": []}}]}}),
                        encoding="utf-8",
                    )
                else:
                    (run_dir / "report.html").write_text("<html>ok</html>", encoding="utf-8")
                    (run_dir / "blueprint.json").write_text("{{}}", encoding="utf-8")
                    (run_dir / "graph_trace.jsonl").write_text('{{"node":"forecast"}}\\n', encoding="utf-8")
                return run_dir

            args = sys.argv[1:]

            if args == ["--help"]:
                print(HELP_OUTPUT)
                raise SystemExit(0)
            if args == ["workflow", "--help"]:
                print(WORKFLOW_HELP_OUTPUT)
                raise SystemExit(0)
            if args == ["profile", "--help"]:
                print(PROFILE_HELP_OUTPUT)
                raise SystemExit(0)
            if args == ["monitor", "--help"]:
                print(MONITOR_HELP_OUTPUT)
                raise SystemExit(0)
            if args == ["workflow", "list"]:
                print(WORKFLOW_LIST_OUTPUT)
                raise SystemExit(0)
            if args == ["workflow", "show", "demo-provider-free"]:
                print(WORKFLOW_SHOW_OUTPUT)
                raise SystemExit(0)
            if args and args[0] == "doctor":
                print("doctor ok")
                raise SystemExit(0)
            if args and args[0] == "start":
                create_run(option_value("--runs-dir"), command="xrtm start")
                print("start ok")
                raise SystemExit(0)
            if args[:2] == ["runs", "show"]:
                print("Run details")
                raise SystemExit(0)
            if args[:2] == ["artifacts", "inspect"]:
                print("Canonical artifact inventory")
                raise SystemExit(0)
            if args[:2] == ["report", "html"]:
                print("Report written")
                raise SystemExit(0)
            if len(args) >= 4 and args[:3] == ["workflow", "create", "scratch"]:
                name = args[3]
                workflows_dir = Path(option_value("--workflows-dir"))
                workflows_dir.mkdir(parents=True, exist_ok=True)
                workflow_path = workflows_dir / f"{{name}}.json"
                workflow_path.write_text(json.dumps({{"name": name}}), encoding="utf-8")
                print(f"Workflow created: {{workflow_path}}")
                raise SystemExit(0)
            if len(args) >= 4 and args[:3] == ["workflow", "edit", "metadata"]:
                print(f"Workflow updated: {{args[3]}}")
                raise SystemExit(0)
            if args[:2] == ["workflow", "validate"]:
                print(f"Workflow valid: {{args[2]}}")
                raise SystemExit(0)
            if args[:2] == ["workflow", "show"]:
                print(f"Workflow: {{args[2]}}")
                raise SystemExit(0)
            if args[:2] == ["workflow", "run"]:
                create_run(option_value("--runs-dir"), command=f"xrtm workflow run {{args[2]}}")
                print(f"Workflow run complete: {{args[2]}}")
                raise SystemExit(0)
            if args[:2] == ["profile", "starter"]:
                name = args[2]
                profiles_dir = Path(option_value("--profiles-dir"))
                profiles_dir.mkdir(parents=True, exist_ok=True)
                profile_path = profiles_dir / f"{{name}}.json"
                profile_path.write_text(json.dumps({{"name": name, "provider": "mock"}}), encoding="utf-8")
                print(f"Starter profile: {{profile_path}}")
                raise SystemExit(0)
            if args[:2] == ["profile", "list"]:
                profiles_dir = Path(option_value("--profiles-dir"))
                print("\\n".join(sorted(path.stem for path in profiles_dir.glob("*.json"))))
                raise SystemExit(0)
            if args[:2] == ["profile", "show"]:
                profiles_dir = Path(option_value("--profiles-dir"))
                print((profiles_dir / f"{{args[2]}}.json").read_text(encoding="utf-8"))
                raise SystemExit(0)
            if args[:2] == ["run", "profile"]:
                create_run(option_value("--runs-dir"), command=f"xrtm run profile {{args[2]}}")
                print(f"Run complete: {{args[2]}}")
                raise SystemExit(0)
            if args[:2] == ["monitor", "start"]:
                create_run(option_value("--runs-dir"), command="xrtm monitor start", monitor=True)
                print("Monitor ready")
                raise SystemExit(0)
            if args[:2] == ["monitor", "list"]:
                runs_dir = Path(option_value("--runs-dir"))
                monitors = sorted(path.name for path in runs_dir.iterdir() if (path / "monitor.json").exists())
                print("\\n".join(monitors))
                raise SystemExit(0)
            if args[:2] == ["monitor", "show"]:
                print("Monitor State")
                raise SystemExit(0)
            if args[:2] == ["monitor", "run-once"]:
                run_dir = Path(args[2])
                monitor_path = run_dir / "monitor.json"
                payload = json.loads(monitor_path.read_text(encoding="utf-8"))
                payload["cycles"] = int(payload.get("cycles", 0)) + 1
                payload["status"] = "running"
                monitor_path.write_text(json.dumps(payload), encoding="utf-8")
                print("Monitor cycle complete")
                raise SystemExit(0)
            if args[:2] == ["runs", "export"]:
                output_path = Path(option_value("--output"))
                output_path.parent.mkdir(parents=True, exist_ok=True)
                if "--format" in args and option_value("--format").lower() == "csv":
                    output_path.write_text("run_id\\nexported\\n", encoding="utf-8")
                else:
                    output_path.write_text(json.dumps({{"run": "exported"}}), encoding="utf-8")
                print(f"Run exported: {{output_path}}")
                raise SystemExit(0)
            if args[:2] == ["artifacts", "cleanup"]:
                runs_dir = Path(option_value("--runs-dir"))
                keep = int(option_value("--keep"))
                run_dirs = sorted(path for path in runs_dir.iterdir() if (path / "run.json").exists())
                candidates = run_dirs[:-keep] if keep else run_dirs
                if "--delete" in args:
                    for path in candidates:
                        shutil.rmtree(path)
                    print(f"Retention removed {{len(candidates)}} run directorie(s).")
                else:
                    print(f"Retention would remove {{len(candidates)}} run directorie(s).")
                raise SystemExit(0)
            if args and args[0] == "tui":
                print("XRTM local product cockpit")
                raise SystemExit(0)
            if args and args[0] == "web":
                print("WebUI smoke ok: 3 run(s), 1 workflow(s), workbench ready")
                raise SystemExit(0)

            print(f"unexpected args: {{args}}")
            raise SystemExit(2)
            """
        ),
        encoding="utf-8",
    )
    script_path.chmod(0o755)
    return script_path


def test_validate_cli_surface_exercises_provider_free_spine(tmp_path: Path) -> None:
    module = _load_module()
    fake_xrtm = _write_fake_xrtm(
        tmp_path,
        help_output="doctor start playground artifacts profile runs monitor report tui web workflow",
        workflow_list_output="demo-provider-free flagship-benchmark",
        workflow_show_output="demo-provider-free Runtime provider",
    )

    workspace_dir = tmp_path / "workspace"
    module.validate_cli_surface(fake_xrtm, workspace_dir=workspace_dir)

    assert (workspace_dir / "profiles" / "installed-surface-local.json").exists()
    assert (workspace_dir / "workflows" / "installed-surface-smoke.json").exists()
    assert (workspace_dir / "exports" / "authored-run.json").exists()
    assert (workspace_dir / "exports" / "authored-run.csv").exists()
    remaining_runs = sorted(path for path in (workspace_dir / "runs").iterdir() if (path / "run.json").exists())
    assert len(remaining_runs) == 2


def test_validate_cli_surface_rejects_missing_workflow_command(tmp_path: Path) -> None:
    module = _load_module()
    fake_xrtm = _write_fake_xrtm(
        tmp_path,
        help_output="doctor start playground artifacts profile runs monitor report tui web",
        workflow_list_output="demo-provider-free flagship-benchmark",
        workflow_show_output="demo-provider-free Runtime provider",
    )

    with pytest.raises(RuntimeError, match="xrtm --help is missing required entries: workflow"):
        module.validate_cli_surface(fake_xrtm, workspace_dir=tmp_path / "workspace")


def test_validate_cli_surface_rejects_missing_playground_command(tmp_path: Path) -> None:
    module = _load_module()
    fake_xrtm = _write_fake_xrtm(
        tmp_path,
        help_output="doctor start artifacts profile runs monitor report tui web workflow",
        workflow_list_output="demo-provider-free flagship-benchmark",
        workflow_show_output="demo-provider-free Runtime provider",
    )

    with pytest.raises(RuntimeError, match="xrtm --help is missing required entries: playground"):
        module.validate_cli_surface(fake_xrtm, workspace_dir=tmp_path / "workspace")


def test_validate_cli_surface_rejects_missing_workflow_authoring_command(tmp_path: Path) -> None:
    module = _load_module()
    fake_xrtm = _write_fake_xrtm(
        tmp_path,
        help_output="doctor start playground artifacts profile runs monitor report tui web workflow",
        workflow_help_output="clone list show validate explain run",
        workflow_list_output="demo-provider-free flagship-benchmark",
        workflow_show_output="demo-provider-free Runtime provider",
    )

    with pytest.raises(RuntimeError, match="xrtm workflow --help is missing required entries: create, edit"):
        module.validate_cli_surface(fake_xrtm, workspace_dir=tmp_path / "workspace")


def test_validate_cli_surface_rejects_missing_profile_command(tmp_path: Path) -> None:
    module = _load_module()
    fake_xrtm = _write_fake_xrtm(
        tmp_path,
        help_output="doctor start playground artifacts profile runs monitor report tui web workflow",
        profile_help_output="create list show",
        workflow_list_output="demo-provider-free flagship-benchmark",
        workflow_show_output="demo-provider-free Runtime provider",
    )

    with pytest.raises(RuntimeError, match="xrtm profile --help is missing required entries: starter"):
        module.validate_cli_surface(fake_xrtm, workspace_dir=tmp_path / "workspace")


def test_validate_cli_surface_rejects_missing_monitor_command(tmp_path: Path) -> None:
    module = _load_module()
    fake_xrtm = _write_fake_xrtm(
        tmp_path,
        help_output="doctor start playground artifacts profile runs monitor report tui web workflow",
        monitor_help_output="start list show",
        workflow_list_output="demo-provider-free flagship-benchmark",
        workflow_show_output="demo-provider-free Runtime provider",
    )

    with pytest.raises(RuntimeError, match="xrtm monitor --help is missing required entries: run-once"):
        module.validate_cli_surface(fake_xrtm, workspace_dir=tmp_path / "workspace")


def test_validate_cli_surface_rejects_missing_builtin_workflow(tmp_path: Path) -> None:
    module = _load_module()
    fake_xrtm = _write_fake_xrtm(
        tmp_path,
        help_output="doctor start playground artifacts profile runs monitor report tui web workflow",
        workflow_list_output="demo-provider-free",
        workflow_show_output="demo-provider-free Runtime provider",
    )

    with pytest.raises(RuntimeError, match="xrtm workflow list is missing required entries: flagship-benchmark"):
        module.validate_cli_surface(fake_xrtm, workspace_dir=tmp_path / "workspace")


def test_parse_args_defaults_workspace_to_temp_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = _load_module()
    monkeypatch.setattr(module.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["check_installed_cli_surface.py"])

    args = module.parse_args()

    assert args.workspace_dir == tmp_path / ".installed-cli-surface-smoke"
