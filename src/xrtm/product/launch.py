"""Shared product launch services for CLI and WebUI actions."""

from __future__ import annotations

from pathlib import Path

from xrtm.product.doctor import doctor_snapshot
from xrtm.product.pipeline import PipelineResult, run_pipeline
from xrtm.product.profiles import DEFAULT_PROFILES_DIR, ProfileStore
from xrtm.product.workflow_runner import build_demo_workflow_blueprint, run_workflow_blueprint
from xrtm.product.workflows import DEFAULT_LOCAL_WORKFLOWS_DIR, WorkflowBlueprint, WorkflowRegistry

DEFAULT_DEMO_LIMIT = 2
DEFAULT_MAX_TOKENS = 768


def run_start_quickstart(*, limit: int = DEFAULT_DEMO_LIMIT, runs_dir: Path = Path("runs"), user: str | None = None) -> PipelineResult:
    """Run the released provider-free quickstart workflow after readiness checks pass."""

    readiness = doctor_snapshot(runs_dir=runs_dir)
    if not readiness["ready"]:
        blocking = [check["detail"] for check in readiness["checks"] if not check["ok"]]
        detail = "; ".join(blocking) if blocking else "doctor readiness checks failed"
        raise ValueError(f"xrtm start prerequisites not satisfied: {detail}")
    return run_demo_workflow(
        provider="mock",
        limit=limit,
        runs_dir=runs_dir,
        user=user,
        command="xrtm start",
        name="demo-provider-free",
        title="XRTM Quickstart",
        description="Guided newcomer quickstart over the provider-free product shell baseline.",
    )


def run_demo_workflow(
    *,
    provider: str = "mock",
    limit: int = DEFAULT_DEMO_LIMIT,
    runs_dir: Path = Path("runs"),
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    write_report: bool = True,
    user: str | None = None,
    command: str = "xrtm demo",
    name: str | None = None,
    title: str = "XRTM Demo",
    description: str = "Bounded product demo over the released real-binary corpus.",
    workflow_kind: str = "demo",
) -> PipelineResult:
    """Run the shared demo workflow service used by CLI and WebUI."""

    blueprint = build_demo_workflow_blueprint(
        name=name or ("demo-provider-free" if provider == "mock" else "demo-local-llm"),
        title=title,
        description=description,
        provider=provider,
        limit=limit,
        max_tokens=max_tokens,
        workflow_kind=workflow_kind,
    )
    return run_workflow_blueprint(
        blueprint,
        command=command,
        runs_dir=runs_dir,
        user=user,
        limit=limit,
        provider=provider,
        base_url=base_url,
        model=model,
        api_key=api_key,
        max_tokens=max_tokens,
        write_report=write_report,
    )


def run_registered_workflow(
    name: str,
    *,
    workflows_dir: Path = DEFAULT_LOCAL_WORKFLOWS_DIR,
    runs_dir: Path = Path("runs"),
    limit: int | None = None,
    provider: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    max_tokens: int | None = None,
    write_report: bool = True,
    user: str | None = None,
    command: str | None = None,
) -> PipelineResult:
    """Run a named registered workflow through the shared blueprint runner."""

    registry = _workflow_registry(workflows_dir)
    blueprint = registry.load(name)
    return run_workflow_blueprint(
        blueprint,
        command=command or f"xrtm workflow run {name}",
        runs_dir=runs_dir,
        user=user,
        limit=limit,
        provider=provider,
        base_url=base_url,
        model=model,
        api_key=api_key,
        max_tokens=max_tokens,
        write_report=write_report,
    )


def run_saved_profile(name: str, *, profiles_dir: Path = DEFAULT_PROFILES_DIR, runs_dir: Path | None = None) -> PipelineResult:
    """Run a saved profile through the shared pipeline executor."""

    profile = ProfileStore(profiles_dir).load(name)
    return run_pipeline(profile.to_pipeline_options(runs_dir=runs_dir))


def load_registered_workflow(name: str, *, workflows_dir: Path = DEFAULT_LOCAL_WORKFLOWS_DIR) -> WorkflowBlueprint:
    """Load one workflow with the same resolution rules used by CLI and WebUI."""

    return _workflow_registry(workflows_dir).load(name)


def explain_registered_workflow(name: str, *, workflows_dir: Path = DEFAULT_LOCAL_WORKFLOWS_DIR) -> dict:
    """Explain one workflow with the shared registry."""

    return _workflow_registry(workflows_dir).explain(name)


def validate_registered_workflow(name: str, *, workflows_dir: Path = DEFAULT_LOCAL_WORKFLOWS_DIR) -> WorkflowBlueprint:
    """Validate one workflow with the shared registry."""

    return _workflow_registry(workflows_dir).validate(name)


def _workflow_registry(workflows_dir: Path) -> WorkflowRegistry:
    root = workflows_dir if workflows_dir.is_absolute() else Path.cwd() / workflows_dir
    return WorkflowRegistry(local_roots=(root,))


__all__ = [
    "DEFAULT_DEMO_LIMIT",
    "DEFAULT_MAX_TOKENS",
    "explain_registered_workflow",
    "load_registered_workflow",
    "run_demo_workflow",
    "run_registered_workflow",
    "run_saved_profile",
    "run_start_quickstart",
    "validate_registered_workflow",
]
