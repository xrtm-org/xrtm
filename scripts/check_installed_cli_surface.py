#!/usr/bin/env python3
"""Validate the released CLI surface from an installed XRTM artifact."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REQUIRED_TOP_LEVEL_COMMANDS = (
    "doctor",
    "start",
    "playground",
    "artifacts",
    "profile",
    "runs",
    "monitor",
    "report",
    "tui",
    "web",
    "workflow",
)
REQUIRED_WORKFLOW_COMMANDS = (
    "create",
    "edit",
    "clone",
    "list",
    "show",
    "validate",
    "explain",
    "run",
)
REQUIRED_PROFILE_COMMANDS = (
    "create",
    "starter",
    "list",
    "show",
)
REQUIRED_MONITOR_COMMANDS = (
    "start",
    "list",
    "show",
    "run-once",
)
REQUIRED_WORKFLOWS = (
    "demo-deterministic",
    "flagship-benchmark",
)


def run_command(command: list[str], *, cwd: Path | None = None) -> str:
    result = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        cwd=cwd,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {result.returncode}: {' '.join(command)}\n\n{result.stdout}"
        )
    return result.stdout


def require_contains(output: str, required_items: tuple[str, ...], *, context: str) -> None:
    missing = [item for item in required_items if item not in output]
    if missing:
        raise RuntimeError(f"{context} is missing required entries: {', '.join(missing)}")


def require_paths_exist(root: Path, required_paths: tuple[str, ...], *, context: str) -> None:
    missing = [relative_path for relative_path in required_paths if not (root / relative_path).exists()]
    if missing:
        raise RuntimeError(f"{context} is missing required files: {', '.join(missing)}")


def discover_run_dirs(runs_dir: Path) -> set[Path]:
    if not runs_dir.exists():
        return set()
    return {path for path in runs_dir.iterdir() if path.is_dir() and (path / "run.json").exists()}


def expect_new_run_dir(
    runs_dir: Path,
    before: set[Path],
    *,
    context: str,
    require_monitor: bool = False,
) -> Path:
    candidates = sorted(discover_run_dirs(runs_dir) - before)
    if len(candidates) != 1:
        raise RuntimeError(f"{context} expected exactly one new run directory, found {len(candidates)}")
    run_dir = candidates[0]
    if require_monitor and not (run_dir / "monitor.json").exists():
        raise RuntimeError(f"{context} did not create a monitor run: {run_dir}")
    if not require_monitor and (run_dir / "monitor.json").exists():
        raise RuntimeError(f"{context} unexpectedly created a monitor run: {run_dir}")
    return run_dir


def validate_cli_surface(xrtm_bin: Path, *, workspace_dir: Path) -> None:
    xrtm_bin = xrtm_bin.resolve()
    workspace_dir = workspace_dir.resolve()

    help_output = run_command([str(xrtm_bin), "--help"])
    require_contains(help_output, REQUIRED_TOP_LEVEL_COMMANDS, context="xrtm --help")

    workflow_help_output = run_command([str(xrtm_bin), "workflow", "--help"])
    require_contains(workflow_help_output, REQUIRED_WORKFLOW_COMMANDS, context="xrtm workflow --help")

    profile_help_output = run_command([str(xrtm_bin), "profile", "--help"])
    require_contains(profile_help_output, REQUIRED_PROFILE_COMMANDS, context="xrtm profile --help")

    monitor_help_output = run_command([str(xrtm_bin), "monitor", "--help"])
    require_contains(monitor_help_output, REQUIRED_MONITOR_COMMANDS, context="xrtm monitor --help")

    workflow_list_output = run_command([str(xrtm_bin), "workflow", "list"])
    require_contains(workflow_list_output, REQUIRED_WORKFLOWS, context="xrtm workflow list")

    workflow_show_output = run_command([str(xrtm_bin), "workflow", "show", "demo-deterministic"])
    require_contains(workflow_show_output, ("demo-deterministic", "Runtime provider"), context="xrtm workflow show")

    workspace_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = workspace_dir / "runs"
    profiles_dir = workspace_dir / "profiles"
    workflows_dir = workspace_dir / "workflows"
    exports_dir = workspace_dir / "exports"
    for path in (runs_dir, profiles_dir, workflows_dir, exports_dir):
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
        path.mkdir(parents=True, exist_ok=True)

    run_command([str(xrtm_bin), "doctor"], cwd=workspace_dir)

    before_start = discover_run_dirs(runs_dir)
    run_command([str(xrtm_bin), "start", "--runs-dir", "runs"], cwd=workspace_dir)
    start_run_dir = expect_new_run_dir(runs_dir, before_start, context="xrtm start")
    require_paths_exist(
        start_run_dir,
        ("run.json", "run_summary.json", "report.html", "blueprint.json", "graph_trace.jsonl"),
        context="xrtm start artifacts",
    )

    run_command([str(xrtm_bin), "runs", "show", "latest", "--runs-dir", "runs"], cwd=workspace_dir)
    run_command([str(xrtm_bin), "artifacts", "inspect", "--latest", "--runs-dir", "runs"], cwd=workspace_dir)
    run_command([str(xrtm_bin), "report", "html", "--latest", "--runs-dir", "runs"], cwd=workspace_dir)

    authored_workflow = "installed-surface-smoke"
    run_command(
        [
            str(xrtm_bin),
            "workflow",
            "create",
            "scratch",
            authored_workflow,
            "--title",
            "Installed surface smoke workflow",
            "--description",
            "Deterministic workflow authored by installed wheel smoke.",
            "--question-limit",
            "1",
            "--max-tokens",
            "512",
            "--workflows-dir",
            "workflows",
        ],
        cwd=workspace_dir,
    )
    require_paths_exist(workflows_dir, (f"{authored_workflow}.json",), context="xrtm workflow create scratch")
    run_command(
        [
            str(xrtm_bin),
            "workflow",
            "edit",
            "metadata",
            authored_workflow,
            "--title",
            "Installed surface smoke workflow v2",
            "--tag",
            "installed-surface",
            "--workflows-dir",
            "workflows",
        ],
        cwd=workspace_dir,
    )
    run_command([str(xrtm_bin), "workflow", "validate", authored_workflow, "--workflows-dir", "workflows"], cwd=workspace_dir)
    authored_show_output = run_command(
        [str(xrtm_bin), "workflow", "show", authored_workflow, "--workflows-dir", "workflows"],
        cwd=workspace_dir,
    )
    require_contains(authored_show_output, (authored_workflow,), context="xrtm workflow show authored workflow")

    before_workflow_run = discover_run_dirs(runs_dir)
    run_command(
        [
            str(xrtm_bin),
            "workflow",
            "run",
            authored_workflow,
            "--workflows-dir",
            "workflows",
            "--runs-dir",
            "runs",
            "--limit",
            "1",
        ],
        cwd=workspace_dir,
    )
    authored_run_dir = expect_new_run_dir(runs_dir, before_workflow_run, context="xrtm workflow run")
    require_paths_exist(
        authored_run_dir,
        ("run.json", "run_summary.json", "report.html", "blueprint.json", "graph_trace.jsonl"),
        context="xrtm workflow run artifacts",
    )

    profile_name = "installed-surface-local"
    run_command(
        [
            str(xrtm_bin),
            "profile",
            "starter",
            profile_name,
            "--profiles-dir",
            "profiles",
            "--runs-dir",
            "runs",
        ],
        cwd=workspace_dir,
    )
    require_paths_exist(profiles_dir, (f"{profile_name}.json",), context="xrtm profile starter")
    profile_list_output = run_command([str(xrtm_bin), "profile", "list", "--profiles-dir", "profiles"], cwd=workspace_dir)
    require_contains(profile_list_output, (profile_name,), context="xrtm profile list")
    profile_show_output = run_command(
        [str(xrtm_bin), "profile", "show", profile_name, "--profiles-dir", "profiles"],
        cwd=workspace_dir,
    )
    require_contains(profile_show_output, ("deterministic",), context="xrtm profile show")

    before_profile_run = discover_run_dirs(runs_dir)
    run_command(
        [
            str(xrtm_bin),
            "run",
            "profile",
            profile_name,
            "--profiles-dir",
            "profiles",
            "--runs-dir",
            "runs",
        ],
        cwd=workspace_dir,
    )
    profile_run_dir = expect_new_run_dir(runs_dir, before_profile_run, context="xrtm run profile")
    require_paths_exist(profile_run_dir, ("run.json", "run_summary.json", "report.html"), context="xrtm run profile artifacts")

    before_monitor = discover_run_dirs(runs_dir)
    run_command(
        [
            str(xrtm_bin),
            "monitor",
            "start",
            "--provider",
            "deterministic",
            "--limit",
            "1",
            "--runs-dir",
            "runs",
        ],
        cwd=workspace_dir,
    )
    monitor_run_dir = expect_new_run_dir(runs_dir, before_monitor, context="xrtm monitor start", require_monitor=True)
    require_paths_exist(monitor_run_dir, ("run.json", "monitor.json"), context="xrtm monitor start artifacts")
    monitor_list_output = run_command([str(xrtm_bin), "monitor", "list", "--runs-dir", "runs"], cwd=workspace_dir)
    require_contains(monitor_list_output, (monitor_run_dir.name,), context="xrtm monitor list")
    run_command([str(xrtm_bin), "monitor", "show", str(monitor_run_dir)], cwd=workspace_dir)
    run_command([str(xrtm_bin), "monitor", "run-once", str(monitor_run_dir)], cwd=workspace_dir)
    require_paths_exist(monitor_run_dir, ("run_summary.json",), context="xrtm monitor run-once artifacts")

    run_command(
        [
            str(xrtm_bin),
            "runs",
            "export",
            authored_run_dir.name,
            "--runs-dir",
            "runs",
            "--output",
            "exports/authored-run.json",
        ],
        cwd=workspace_dir,
    )
    run_command(
        [
            str(xrtm_bin),
            "runs",
            "export",
            authored_run_dir.name,
            "--runs-dir",
            "runs",
            "--output",
            "exports/authored-run.csv",
            "--format",
            "csv",
        ],
        cwd=workspace_dir,
    )
    require_paths_exist(exports_dir, ("authored-run.json", "authored-run.csv"), context="xrtm runs export")

    tui_output = run_command([str(xrtm_bin), "tui", "--runs-dir", "runs"], cwd=workspace_dir)
    require_contains(tui_output, ("XRTM local product cockpit",), context="xrtm tui")
    web_output = run_command(
        [str(xrtm_bin), "web", "--runs-dir", "runs", "--workflows-dir", "workflows", "--smoke"],
        cwd=workspace_dir,
    )
    require_contains(web_output, ("WebUI smoke ok", "workbench ready"), context="xrtm web --smoke")

    cleanup_preview_output = run_command(
        [str(xrtm_bin), "artifacts", "cleanup", "--runs-dir", "runs", "--keep", "2"],
        cwd=workspace_dir,
    )
    require_contains(cleanup_preview_output, ("would remove",), context="xrtm artifacts cleanup preview")
    cleanup_delete_output = run_command(
        [str(xrtm_bin), "artifacts", "cleanup", "--runs-dir", "runs", "--keep", "2", "--delete"],
        cwd=workspace_dir,
    )
    require_contains(cleanup_delete_output, ("removed",), context="xrtm artifacts cleanup delete")
    remaining_runs = discover_run_dirs(runs_dir)
    if len(remaining_runs) != 2:
        raise RuntimeError(f"xrtm artifacts cleanup --delete should leave 2 runs, found {len(remaining_runs)}")


def default_workspace_dir() -> Path:
    return Path(tempfile.gettempdir()) / ".installed-cli-surface-smoke"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xrtm-bin", type=Path, default=Path("xrtm"))
    parser.add_argument("--workspace-dir", type=Path, default=default_workspace_dir())
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validate_cli_surface(args.xrtm_bin, workspace_dir=args.workspace_dir)
    print(f"Installed CLI surface check passed for {args.xrtm_bin}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
