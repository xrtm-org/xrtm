#!/usr/bin/env python3
"""Validate the released CLI surface from an installed XRTM artifact."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REQUIRED_TOP_LEVEL_COMMANDS = (
    "doctor",
    "start",
    "playground",
    "artifacts",
    "runs",
    "report",
    "web",
    "workflow",
)
REQUIRED_WORKFLOWS = (
    "demo-provider-free",
    "flagship-benchmark",
)


def run_command(command: list[str]) -> str:
    result = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
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


def validate_cli_surface(xrtm_bin: Path) -> None:
    help_output = run_command([str(xrtm_bin), "--help"])
    require_contains(help_output, REQUIRED_TOP_LEVEL_COMMANDS, context="xrtm --help")

    workflow_list_output = run_command([str(xrtm_bin), "workflow", "list"])
    require_contains(workflow_list_output, REQUIRED_WORKFLOWS, context="xrtm workflow list")

    workflow_show_output = run_command([str(xrtm_bin), "workflow", "show", "demo-provider-free"])
    require_contains(workflow_show_output, ("demo-provider-free", "Runtime provider"), context="xrtm workflow show")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xrtm-bin", type=Path, default=Path("xrtm"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validate_cli_surface(args.xrtm_bin)
    print(f"Installed CLI surface check passed for {args.xrtm_bin}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
