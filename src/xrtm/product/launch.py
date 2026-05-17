"""Shared product launch services for CLI and WebUI actions."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from xrtm.product.doctor import doctor_snapshot
from xrtm.product.pipeline import PipelineResult, run_pipeline
from xrtm.product.profiles import DEFAULT_PROFILES_DIR, ProfileStore
from xrtm.product.sandbox import (
    SandboxContext,
    SandboxQuestionInput,
    SandboxSessionResult,
    record_sandbox_profile_save,
    record_sandbox_workflow_save,
    resolve_sandbox_context,
    run_sandbox_session,
    run_template_sandbox_session,
    run_workflow_sandbox_session,
    sandbox_profile_for_save,
    sandbox_workflow_blueprint,
)
from xrtm.product.workflow_authoring import persist_authored_workflow
from xrtm.product.workflow_runner import build_demo_workflow_blueprint, run_workflow_blueprint
from xrtm.product.workflows import (
    DEFAULT_LOCAL_WORKFLOWS_DIR,
    WorkflowBlueprint,
    WorkflowRegistry,
    explain_blueprint,
    validate_product_blueprint,
)

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

    return run_authored_workflow(
        workflow_name=name,
        workflows_dir=workflows_dir,
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
    if profile.workflow_name:
        resolved_runs_dir = runs_dir or Path(profile.runs_dir)
        return run_authored_workflow(
            workflow_name=profile.workflow_name,
            workflows_dir=_workflows_dir_for_profiles(profiles_dir),
            command=f"xrtm run profile {name}",
            runs_dir=resolved_runs_dir,
            user=profile.user,
            limit=profile.limit,
            provider=profile.provider,
            base_url=profile.base_url,
            model=profile.model,
            max_tokens=profile.max_tokens,
            write_report=profile.write_report,
        )
    return run_pipeline(profile.to_pipeline_options(runs_dir=runs_dir))


def load_registered_workflow(name: str, *, workflows_dir: Path = DEFAULT_LOCAL_WORKFLOWS_DIR) -> WorkflowBlueprint:
    """Load one workflow with the same resolution rules used by CLI and WebUI."""

    return _workflow_registry(workflows_dir).load(name)


def explain_registered_workflow(name: str, *, workflows_dir: Path = DEFAULT_LOCAL_WORKFLOWS_DIR) -> dict:
    """Explain one workflow with the shared registry."""

    return explain_authored_workflow(workflow_name=name, workflows_dir=workflows_dir)


def validate_registered_workflow(name: str, *, workflows_dir: Path = DEFAULT_LOCAL_WORKFLOWS_DIR) -> WorkflowBlueprint:
    """Validate one workflow with the shared registry."""

    return validate_authored_workflow(workflow_name=name, workflows_dir=workflows_dir)


def authored_workflow_validation_report(
    *,
    workflow_name: str | None = None,
    blueprint: WorkflowBlueprint | None = None,
    workflows_dir: Path = DEFAULT_LOCAL_WORKFLOWS_DIR,
    registry: WorkflowRegistry | None = None,
    persist: bool = False,
    overwrite: bool = True,
    destination_root: Path | None = None,
) -> dict[str, Any]:
    """Return a shared validation payload for authored workflows and drafts."""

    requested_name = workflow_name or (blueprint.name if blueprint is not None else None)
    try:
        validated = validate_authored_workflow(
            workflow_name=workflow_name,
            blueprint=blueprint,
            workflows_dir=workflows_dir,
            registry=registry,
            persist=persist,
            overwrite=overwrite,
            destination_root=destination_root,
        )
    except (FileNotFoundError, ValueError) as exc:
        return {
            "ok": False,
            "errors": _workflow_error_lines(exc),
            "workflow": requested_name,
        }
    return {
        "ok": True,
        "errors": [],
        "workflow": validated.name,
        "schema_version": validated.schema_version,
        "title": validated.title,
    }


def explain_authored_workflow(
    *,
    workflow_name: str | None = None,
    blueprint: WorkflowBlueprint | None = None,
    workflows_dir: Path = DEFAULT_LOCAL_WORKFLOWS_DIR,
    registry: WorkflowRegistry | None = None,
    persist: bool = False,
    overwrite: bool = True,
    destination_root: Path | None = None,
) -> dict[str, Any]:
    """Explain one authored workflow or in-memory draft through the shared validation path."""

    validated = validate_authored_workflow(
        workflow_name=workflow_name,
        blueprint=blueprint,
        workflows_dir=workflows_dir,
        registry=registry,
        persist=persist,
        overwrite=overwrite,
        destination_root=destination_root,
    )
    return explain_blueprint(validated)


def validate_authored_workflow(
    *,
    workflow_name: str | None = None,
    blueprint: WorkflowBlueprint | None = None,
    workflows_dir: Path = DEFAULT_LOCAL_WORKFLOWS_DIR,
    registry: WorkflowRegistry | None = None,
    persist: bool = False,
    overwrite: bool = True,
    destination_root: Path | None = None,
) -> WorkflowBlueprint:
    """Validate one authored workflow or in-memory draft."""

    active_registry = registry or _workflow_registry(workflows_dir)
    if workflow_name is not None and blueprint is not None:
        raise ValueError("pass either workflow_name or blueprint, not both")
    if workflow_name is None and blueprint is None:
        raise ValueError("workflow_name or blueprint is required")
    if workflow_name is not None:
        return active_registry.validate(workflow_name)
    validated = _validated_blueprint(blueprint)
    if persist:
        persist_authored_workflow(
            active_registry,
            validated,
            overwrite=overwrite,
            destination_root=destination_root,
        )
    return validated


def run_authored_workflow(
    *,
    workflow_name: str | None = None,
    blueprint: WorkflowBlueprint | None = None,
    workflows_dir: Path = DEFAULT_LOCAL_WORKFLOWS_DIR,
    registry: WorkflowRegistry | None = None,
    persist: bool = False,
    overwrite: bool = True,
    destination_root: Path | None = None,
    command: str,
    runs_dir: Path = Path("runs"),
    user: str | None = None,
    limit: int | None = None,
    provider: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    max_tokens: int | None = None,
    write_report: bool = True,
) -> PipelineResult:
    """Run one authored workflow or draft through the shared validation path."""

    validated = validate_authored_workflow(
        workflow_name=workflow_name,
        blueprint=blueprint,
        workflows_dir=workflows_dir,
        registry=registry,
        persist=persist,
        overwrite=overwrite,
        destination_root=destination_root,
    )
    return run_workflow_blueprint(
        validated,
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


def save_sandbox_workflow(
    source: SandboxSessionResult | Path | Mapping[str, Any],
    *,
    workflow_name: str | None = None,
    workflows_dir: Path = DEFAULT_LOCAL_WORKFLOWS_DIR,
    registry: WorkflowRegistry | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Persist sandbox workflow state through the shared authored-workflow path."""

    active_registry = registry or _workflow_registry(workflows_dir)
    blueprint = sandbox_workflow_blueprint(source, workflow_name=workflow_name)
    validated = validate_authored_workflow(
        blueprint=blueprint,
        registry=active_registry,
        persist=True,
        overwrite=overwrite,
    )
    path = active_registry.local_path(validated.name)
    payload = record_sandbox_workflow_save(source, blueprint=validated, workflow_path=path)
    return {
        "path": str(path),
        "workflow": {
            "name": validated.name,
            "schema_version": validated.schema_version,
            "title": validated.title,
        },
        "save_back": payload["save_back"],
    }


def save_sandbox_profile(
    source: SandboxSessionResult | Path | Mapping[str, Any],
    *,
    profile_name: str,
    profiles_dir: Path = DEFAULT_PROFILES_DIR,
    workflows_dir: Path = DEFAULT_LOCAL_WORKFLOWS_DIR,
    registry: WorkflowRegistry | None = None,
    workflow_name: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Persist sandbox launch/runtime state into the reusable profile store."""

    active_registry = registry or _workflow_registry(workflows_dir)
    profile = sandbox_profile_for_save(
        source,
        profile_name=profile_name,
        registry=active_registry,
        workflow_name=workflow_name,
    )
    path = ProfileStore(profiles_dir).create(profile, overwrite=overwrite)
    payload = record_sandbox_profile_save(source, profile=profile, profile_path=path)
    return {
        "path": str(path),
        "profile": profile.to_json_dict(),
        "save_back": payload["save_back"],
    }


def _workflow_registry(workflows_dir: Path) -> WorkflowRegistry:
    root = workflows_dir if workflows_dir.is_absolute() else Path.cwd() / workflows_dir
    return WorkflowRegistry(local_roots=(root,))


def _workflows_dir_for_profiles(profiles_dir: Path) -> Path:
    root = profiles_dir if profiles_dir.is_absolute() else Path.cwd() / profiles_dir
    return root.parent / "workflows"


def _validated_blueprint(blueprint: WorkflowBlueprint | None) -> WorkflowBlueprint:
    if blueprint is None:
        raise ValueError("workflow_name or blueprint is required")
    validated = WorkflowBlueprint.from_payload(blueprint.to_json_dict())
    validate_product_blueprint(validated)
    return validated


def _workflow_error_lines(exc: Exception) -> list[str]:
    lines = [line.strip() for line in str(exc).splitlines() if line.strip()]
    return lines or [str(exc)]


__all__ = [
    "DEFAULT_DEMO_LIMIT",
    "DEFAULT_MAX_TOKENS",
    "authored_workflow_validation_report",
    "explain_authored_workflow",
    "explain_registered_workflow",
    "load_registered_workflow",
    "resolve_sandbox_context",
    "run_demo_workflow",
    "run_authored_workflow",
    "run_registered_workflow",
    "run_sandbox_session",
    "run_saved_profile",
    "run_start_quickstart",
    "run_template_sandbox_session",
    "run_workflow_sandbox_session",
    "save_sandbox_profile",
    "save_sandbox_workflow",
    "SandboxContext",
    "SandboxQuestionInput",
    "SandboxSessionResult",
    "validate_authored_workflow",
    "validate_registered_workflow",
]
