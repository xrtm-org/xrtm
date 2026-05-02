"""Onboarding-focused doctor checks for the XRTM CLI."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from xrtm.product.pipeline import package_versions
from xrtm.product.providers import local_llm_status

SUPPORTED_PYTHON = ">=3.11,<3.13"
SUPPORTED_PYTHON_MIN = (3, 11)
SUPPORTED_PYTHON_MAX_EXCLUSIVE = (3, 13)
DEFAULT_RUNS_DIR = Path("runs")
RELEASED_DEMO_COMMAND = "xrtm demo --provider mock --limit 1 --runs-dir runs"
_PACKAGE_IMPORTS = {
    "xrtm": "xrtm.product.pipeline",
    "xrtm-data": "xrtm.data.corpora",
    "xrtm-eval": "xrtm.eval",
    "xrtm-forecast": "xrtm.forecast.providers.inference.factory",
    "xrtm-train": "xrtm.train",
}


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    ok: bool
    detail: str
    fix: str | None = None


def run_doctor(
    console: Console,
    *,
    base_url: str | None = None,
    runs_dir: Path = DEFAULT_RUNS_DIR,
    show_next_steps: bool = True,
) -> bool:
    versions = package_versions()
    checks = [
        _python_check(),
        _package_check(versions),
        _import_check(),
        _runs_dir_check(runs_dir),
    ]
    ready = all(check.ok for check in checks)
    local_status = local_llm_status(base_url=base_url)

    _print_package_versions(console, versions)
    _print_readiness_checks(console, checks)
    _print_readiness_summary(console, ready)
    if show_next_steps:
        _print_next_steps(console, ready, checks)
    _print_local_llm_panel(console, local_status)
    return ready


def _python_check() -> DoctorCheck:
    version_info = sys.version_info
    version_text = f"{version_info.major}.{version_info.minor}.{version_info.micro}"
    supported = SUPPORTED_PYTHON_MIN <= (version_info.major, version_info.minor) < SUPPORTED_PYTHON_MAX_EXCLUSIVE
    detail = f"Python {version_text} (supported: {SUPPORTED_PYTHON})"
    fix = None if supported else f"Use Python {SUPPORTED_PYTHON} and reinstall XRTM in that environment."
    return DoctorCheck(name="Python", ok=supported, detail=detail, fix=fix)


def _package_check(versions: dict[str, str]) -> DoctorCheck:
    missing = [package for package, package_version in versions.items() if package_version == "unknown"]
    if not missing:
        return DoctorCheck(
            name="Core packages",
            ok=True,
            detail=f"{len(versions)} core packages reported version metadata.",
        )
    missing_list = ", ".join(missing)
    return DoctorCheck(
        name="Core packages",
        ok=False,
        detail=f"Missing package metadata for: {missing_list}.",
        fix="Reinstall XRTM and its sibling packages so all core distributions are available.",
    )


def _import_check() -> DoctorCheck:
    failures: list[str] = []
    for package, module_name in _PACKAGE_IMPORTS.items():
        try:
            import_module(module_name)
        except Exception as exc:
            failures.append(f"{package} ({module_name}): {exc}")
    if not failures:
        return DoctorCheck(
            name="Core imports",
            ok=True,
            detail="Provider-free runtime imports loaded successfully.",
        )
    return DoctorCheck(
        name="Core imports",
        ok=False,
        detail="Import failures: " + "; ".join(failures),
        fix="Reinstall or repair the failing package imports before running the default demo.",
    )


def _runs_dir_check(runs_dir: Path) -> DoctorCheck:
    target = runs_dir.expanduser()
    display = f"{runs_dir.as_posix().rstrip('/')}/"
    if target.exists():
        if not target.is_dir():
            return DoctorCheck(
                name="Default runs dir",
                ok=False,
                detail=f"{target} exists but is not a directory.",
                fix=f"Remove or rename {target} so XRTM can create {display} for local runs.",
            )
        if os.access(target, os.W_OK | os.X_OK):
            return DoctorCheck(
                name="Default runs dir",
                ok=True,
                detail=f"{target} exists and is writable.",
            )
        return DoctorCheck(
            name="Default runs dir",
            ok=False,
            detail=f"{target} exists but is not writable.",
            fix=f"Grant write access to {target} or run XRTM from a writable workspace.",
        )

    parent = _nearest_existing_parent(target)
    if parent.is_dir() and os.access(parent, os.W_OK | os.X_OK):
        return DoctorCheck(
            name="Default runs dir",
            ok=True,
            detail=f"{display} will be created in {parent.resolve()} on the first guided run.",
        )
    return DoctorCheck(
        name="Default runs dir",
        ok=False,
        detail=f"{display} cannot be created because {parent} is not writable.",
        fix="Choose a writable working directory before running the provider-free demo path.",
    )


def _nearest_existing_parent(path: Path) -> Path:
    current = path.parent
    while not current.exists() and current != current.parent:
        current = current.parent
    return current


def _print_package_versions(console: Console, versions: dict[str, str]) -> None:
    table = Table(title="XRTM Doctor")
    table.add_column("Package", style="cyan")
    table.add_column("Version", style="green")
    for package, package_version in versions.items():
        table.add_row(package, package_version)
    console.print(table)


def _print_readiness_checks(console: Console, checks: list[DoctorCheck]) -> None:
    table = Table(title="Provider-Free Readiness Checks")
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    table.add_column("Details")
    for check in checks:
        status = "ready" if check.ok else "not ready"
        table.add_row(check.name, status, check.detail)
    console.print(table)


def _print_readiness_summary(console: Console, ready: bool) -> None:
    status = "READY" if ready else "NOT READY"
    color = "green" if ready else "red"
    lines = [
        f"Default provider-free first run: {status}",
        f"Released next command: {RELEASED_DEMO_COMMAND}",
        "xrtm doctor verifies package health; the released demo writes the first scored run and report.",
        "No API keys, cloud provider, or local model server are required for this path.",
    ]
    console.print(Panel("\n".join(lines), title="Readiness Summary", border_style=color))


def _print_next_steps(console: Console, ready: bool, checks: list[DoctorCheck]) -> None:
    if ready:
        lines = [
            f"1. Run {RELEASED_DEMO_COMMAND}",
            "2. Review run history with xrtm runs list --runs-dir runs",
            "3. Copy the run id from the demo output or runs list, then inspect it with xrtm runs show <run-id> --runs-dir runs",
            "4. Confirm artifacts with xrtm artifacts inspect runs/<run-id>",
            "5. Open/regenerate the report with xrtm report html runs/<run-id>",
            "6. Browse the same run with xrtm web --runs-dir runs or xrtm tui --runs-dir runs",
            "7. Only after that, treat local-llm as the optional advanced path.",
        ]
    else:
        failed_checks = [check for check in checks if not check.ok]
        lines = ["1. Fix the blocking provider-free checks above."]
        for index, check in enumerate(failed_checks, start=2):
            action = check.fix or check.detail
            lines.append(f"{index}. {check.name}: {action}")
        lines.append(f"{len(failed_checks) + 2}. Rerun xrtm doctor")
        lines.append(f"{len(failed_checks) + 3}. When doctor shows READY, run {RELEASED_DEMO_COMMAND}")
    console.print(Panel("\n".join(lines), title="What to do next", border_style="blue"))


def _print_local_llm_panel(console: Console, status: dict) -> None:
    healthy = bool(status.get("healthy"))
    color = "green" if healthy else "yellow"
    readiness = "ready" if healthy else "not ready (optional)"
    lines = [
        "local-llm is optional and does not affect provider-free readiness.",
        f"Status: {readiness}",
        f"Base URL: {status['base_url']}",
        f"Health URL: {status['health_url']}",
    ]
    models = status.get("models") or []
    if models:
        lines.append(f"Models: {', '.join(models)}")
    error = status.get("error")
    if error:
        lines.append(f"Health check error: {error}")
    lines.append("Use xrtm providers doctor or xrtm local-llm status when you are ready for the advanced path.")
    console.print(Panel("\n".join(lines), title="Optional advanced path: local-llm", border_style=color))


__all__ = ["DEFAULT_RUNS_DIR", "DoctorCheck", "run_doctor"]
