"""Shared sandbox/playground services for bounded exploratory workflow sessions."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from xrtm.data.core.schemas.forecast import ForecastQuestion, MetadataBase
from xrtm.product.artifacts import ArtifactStore, to_json_safe
from xrtm.product.profiles import WorkflowProfile
from xrtm.product.read_models import read_run_detail
from xrtm.product.workflow_authoring import build_workflow_from_template
from xrtm.product.workflow_graph import graph_trace_rows
from xrtm.product.workflow_runner import execute_workflow_blueprint
from xrtm.product.workflows import DEFAULT_LOCAL_WORKFLOWS_DIR, WorkflowBlueprint, WorkflowRegistry

SANDBOX_SESSION_SCHEMA_VERSION = "xrtm.sandbox-session.v1"
SANDBOX_CORPUS_ID = "xrtm-playground.v1"
MAX_SANDBOX_QUESTIONS = 5
SANDBOX_INSPECTION_MODE = "read-only"
SANDBOX_SAVE_BACK_MODE = "explicit"
_QUESTION_ID_CHARS = re.compile(r"[^A-Za-z0-9_.-]+")


@dataclass(frozen=True)
class SandboxQuestionInput:
    """One bounded custom question for exploratory sandbox runs."""

    prompt: str
    title: str | None = None
    resolution_criteria: str | None = None
    question_id: str | None = None
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        prompt = self.prompt.strip()
        if not prompt:
            raise ValueError("sandbox question prompt is required")
        title = self.title.strip() if isinstance(self.title, str) else None
        resolution_criteria = self.resolution_criteria.strip() if isinstance(self.resolution_criteria, str) else None
        question_id = self.question_id.strip() if isinstance(self.question_id, str) else None
        tags = tuple(tag.strip() for tag in self.tags if isinstance(tag, str) and tag.strip())
        object.__setattr__(self, "prompt", prompt)
        object.__setattr__(self, "title", title or None)
        object.__setattr__(self, "resolution_criteria", resolution_criteria or None)
        object.__setattr__(self, "question_id", question_id or None)
        object.__setattr__(self, "tags", tags)

    def to_forecast_question(self, *, index: int) -> ForecastQuestion:
        now = datetime.now(timezone.utc)
        title = self.title or _question_title(self.prompt)
        question_id = self.question_id or f"playground-{index}-{_normalize_token(title)}"
        metadata = MetadataBase(
            id=f"{question_id}:metadata",
            created_at=now,
            snapshot_time=now,
            tags=list(dict.fromkeys((*self.tags, "sandbox", "exploratory"))),
            subject_type="binary",
            source_version=SANDBOX_CORPUS_ID,
            raw_data={
                "id": question_id,
                "title": title,
                "content": self.prompt,
                "resolution_criteria": self.resolution_criteria,
                "source": "playground",
                "exploratory": True,
            },
            source="playground",
            exploratory=True,
        )
        return ForecastQuestion(
            id=question_id,
            title=title,
            content=self.prompt,
            resolution_criteria=self.resolution_criteria,
            metadata=metadata,
        )


@dataclass(frozen=True)
class SandboxContext:
    """Resolved workflow/template context for one sandbox session."""

    context_type: str
    reference_name: str
    source: str
    blueprint: WorkflowBlueprint
    workflow_name: str | None = None
    template_id: str | None = None

    def __post_init__(self) -> None:
        if self.context_type not in {"workflow", "template"}:
            raise ValueError(f"unsupported sandbox context type: {self.context_type}")

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "context_type": self.context_type,
            "reference_name": self.reference_name,
            "source": self.source,
            "workflow_name": self.workflow_name,
            "template_id": self.template_id,
            "blueprint": self.blueprint.to_json_dict(),
        }


@dataclass(frozen=True)
class SandboxSessionResult:
    """Stable read-only payload returned by the shared sandbox service."""

    run_id: str
    run_dir: Path
    run: dict[str, Any]
    workflow: dict[str, Any]
    run_summary: dict[str, Any]
    context: SandboxContext
    labeling: dict[str, Any]
    questions: tuple[dict[str, Any], ...]
    inspection_steps: tuple[dict[str, Any], ...]
    save_back: dict[str, Any]
    total_seconds: float

    def to_json_dict(self) -> dict[str, Any]:
        return _normalize_sandbox_payload(
            {
                "schema_version": SANDBOX_SESSION_SCHEMA_VERSION,
                "run_id": self.run_id,
                "run_dir": str(self.run_dir),
                "run": self.run,
                "workflow": self.workflow,
                "run_summary": self.run_summary,
                "context": self.context.to_json_dict(),
                "labeling": self.labeling,
                "questions": list(self.questions),
                "inspection_steps": list(self.inspection_steps),
                "save_back": self.save_back,
                "total_seconds": self.total_seconds,
            }
        )


def resolve_sandbox_context(
    *,
    workflow_name: str | None = None,
    template_id: str | None = None,
    workflows_dir: Path = DEFAULT_LOCAL_WORKFLOWS_DIR,
    registry: WorkflowRegistry | None = None,
) -> SandboxContext:
    """Resolve one safe workflow or starter template into a sandbox context."""

    if (workflow_name is None) == (template_id is None):
        raise ValueError("pass exactly one of workflow_name or template_id")
    active_registry = registry or _workflow_registry(workflows_dir)
    if workflow_name is not None:
        blueprint = active_registry.validate(workflow_name)
        summary = next((item for item in active_registry.list_workflows() if item.name == workflow_name), None)
        return SandboxContext(
            context_type="workflow",
            reference_name=workflow_name,
            source=summary.source if summary is not None else "workflow",
            workflow_name=workflow_name,
            blueprint=blueprint,
        )
    assert template_id is not None
    blueprint = build_workflow_from_template(template_id, _template_blueprint_name(template_id))
    return SandboxContext(
        context_type="template",
        reference_name=template_id,
        source="template",
        template_id=template_id,
        blueprint=blueprint,
    )


def run_sandbox_session(
    *,
    context: SandboxContext | None = None,
    workflow_name: str | None = None,
    template_id: str | None = None,
    question: SandboxQuestionInput | str | None = None,
    questions: Sequence[SandboxQuestionInput | str] | None = None,
    workflows_dir: Path = DEFAULT_LOCAL_WORKFLOWS_DIR,
    registry: WorkflowRegistry | None = None,
    runs_dir: Path = Path("runs"),
    provider: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    max_tokens: int | None = None,
    write_report: bool | None = None,
    user: str | None = None,
    command: str = "xrtm playground",
) -> SandboxSessionResult:
    """Run one bounded exploratory workflow session through the shared workflow runner."""

    active_context = context or resolve_sandbox_context(
        workflow_name=workflow_name,
        template_id=template_id,
        workflows_dir=workflows_dir,
        registry=registry,
    )
    custom_questions = tuple(item.to_forecast_question(index=index) for index, item in enumerate(_question_inputs(question, questions), start=1))
    execution = execute_workflow_blueprint(
        active_context.blueprint,
        command=command,
        runs_dir=runs_dir,
        user=user,
        limit=len(custom_questions),
        questions=custom_questions,
        corpus_id=SANDBOX_CORPUS_ID,
        provider=provider,
        base_url=base_url,
        model=model,
        api_key=api_key,
        max_tokens=max_tokens,
        write_report=write_report,
    )
    run = execution.pipeline_result.run
    detail = read_run_detail(run.run_dir)
    run.artifacts.setdefault("sandbox_session.json", str(run.run_dir / "sandbox_session.json"))
    session = SandboxSessionResult(
        run_id=run.run_id,
        run_dir=run.run_dir,
        run=run.to_json_dict(),
        workflow=detail.get("workflow", {}),
        run_summary=detail.get("summary", {}),
        context=active_context,
        labeling=_sandbox_labeling(question_count=len(custom_questions)),
        questions=tuple(question.model_dump(mode="json") for question in custom_questions),
        inspection_steps=tuple(_inspection_steps(execution=execution, detail=detail)),
        save_back=_save_back_state(active_context=active_context, options=execution.options),
        total_seconds=execution.pipeline_result.total_seconds,
    )
    store = ArtifactStore(run.run_dir.parent)
    store.write_json(run, "sandbox_session.json", session.to_json_dict())
    store.append_event(
        run,
        "sandbox_session_attached",
        classification="exploratory",
        question_count=len(custom_questions),
        context_type=active_context.context_type,
        reference_name=active_context.reference_name,
    )
    store.finish(run, status=run.status, errors=run.errors)
    return session


def run_workflow_sandbox_session(
    workflow_name: str,
    *,
    question: SandboxQuestionInput | str | None = None,
    questions: Sequence[SandboxQuestionInput | str] | None = None,
    workflows_dir: Path = DEFAULT_LOCAL_WORKFLOWS_DIR,
    registry: WorkflowRegistry | None = None,
    runs_dir: Path = Path("runs"),
    provider: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    max_tokens: int | None = None,
    write_report: bool | None = None,
    user: str | None = None,
    command: str = "xrtm playground",
) -> SandboxSessionResult:
    return run_sandbox_session(
        workflow_name=workflow_name,
        question=question,
        questions=questions,
        workflows_dir=workflows_dir,
        registry=registry,
        runs_dir=runs_dir,
        provider=provider,
        base_url=base_url,
        model=model,
        api_key=api_key,
        max_tokens=max_tokens,
        write_report=write_report,
        user=user,
        command=command,
    )


def run_template_sandbox_session(
    template_id: str,
    *,
    question: SandboxQuestionInput | str | None = None,
    questions: Sequence[SandboxQuestionInput | str] | None = None,
    workflows_dir: Path = DEFAULT_LOCAL_WORKFLOWS_DIR,
    registry: WorkflowRegistry | None = None,
    runs_dir: Path = Path("runs"),
    provider: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    max_tokens: int | None = None,
    write_report: bool | None = None,
    user: str | None = None,
    command: str = "xrtm playground",
) -> SandboxSessionResult:
    return run_sandbox_session(
        template_id=template_id,
        question=question,
        questions=questions,
        workflows_dir=workflows_dir,
        registry=registry,
        runs_dir=runs_dir,
        provider=provider,
        base_url=base_url,
        model=model,
        api_key=api_key,
        max_tokens=max_tokens,
        write_report=write_report,
        user=user,
        command=command,
    )


def _inspection_steps(*, execution: Any, detail: dict[str, Any]) -> list[dict[str, Any]]:
    blueprint = execution.compiled.blueprint
    trace = detail.get("graph_trace") or graph_trace_rows(execution.compiled, execution.state)
    steps: list[dict[str, Any]] = []
    for row in trace:
        node_id = str(row.get("node"))
        node = blueprint.graph.nodes.get(node_id)
        output = _stable_output(execution.state.node_reports.get(node_id))
        artifact_payloads = _artifact_payloads(node_id=node_id, output=output, detail=detail)
        steps.append(
            {
                "order": int(row.get("sequence", len(steps) + 1)),
                "node_id": node_id,
                "label": node.description if node is not None and node.description else node_id,
                "node_type": row.get("kind", node.kind if node is not None else "parallel-group"),
                "status": row.get("status", "completed"),
                "optional": bool(row.get("optional", node.optional if node is not None else False)),
                "latency_seconds": row.get("latency_seconds"),
                "route": row.get("route"),
                "output": output,
                "output_preview": _preview_for_step(node_id=node_id, output=output, row=row, blueprint=blueprint),
                "artifacts": _artifact_refs(artifact_payloads=artifact_payloads, detail=detail),
                "artifact_payloads": artifact_payloads,
            }
        )
    return _ordered_inspection_steps(steps)


def _artifact_payloads(*, node_id: str, output: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
    payloads: dict[str, Any] = {}
    if "question_count" in output and detail.get("questions"):
        payloads["questions"] = [
            {
                "id": question.get("id"),
                "title": question.get("title"),
                "description": question.get("description"),
                "resolution_criteria": question.get("resolution_criteria"),
                "tags": question.get("metadata", {}).get("tags", []),
            }
            for question in detail["questions"]
        ]
    if "record_count" in output and detail.get("forecasts"):
        payloads["forecasts"] = [
            {
                "question_id": forecast.get("question_id"),
                "probability": forecast.get("output", {}).get("probability"),
                "reasoning_preview": _truncate(forecast.get("output", {}).get("reasoning")),
                "provider_model": forecast.get("provider_metadata", {}).get("model"),
            }
            for forecast in detail["forecasts"]
        ]
    if "total_evaluations" in output and "training_samples" not in output and detail.get("eval"):
        payloads["eval"] = {
            "total_evaluations": detail["eval"].get("total_evaluations"),
            "summary_statistics": detail["eval"].get("summary_statistics", {}),
            "slices": detail["eval"].get("slices", {}),
        }
    if "training_samples" in output and detail.get("train"):
        payloads["train"] = {
            "total_evaluations": detail["train"].get("total_evaluations"),
            "training_samples": detail["train"].get("training_samples"),
            "summary_statistics": detail["train"].get("summary_statistics", {}),
            "slices": detail["train"].get("slices", {}),
        }
    if node_id == "report" or "report_path" in output:
        if detail.get("provider"):
            payloads["provider"] = detail["provider"]
        report_path = detail.get("run", {}).get("artifacts", {}).get("report.html")
        if report_path:
            payloads["report"] = {"path": report_path}
    return payloads


def _artifact_refs(*, artifact_payloads: dict[str, Any], detail: dict[str, Any]) -> list[dict[str, Any]]:
    run_artifacts = detail.get("run", {}).get("artifacts", {})
    refs: list[dict[str, Any]] = []
    artifact_names = {
        "questions": "questions.jsonl",
        "forecasts": "forecasts.jsonl",
        "eval": "eval.json",
        "train": "train.json",
        "provider": "provider.json",
        "report": "report.html",
    }
    for key, artifact_name in artifact_names.items():
        if key in artifact_payloads and artifact_name in run_artifacts:
            refs.append({"name": artifact_name, "path": run_artifacts[artifact_name]})
    return refs


def _stable_output(report: Any) -> dict[str, Any]:
    if isinstance(report, dict):
        safe = to_json_safe(report)
        return {
            key: value
            for key, value in safe.items()
            if isinstance(value, (str, int, float, bool, type(None)))
            or (isinstance(value, list) and all(isinstance(item, (str, int, float, bool, type(None))) for item in value))
        }
    if report is None:
        return {}
    return {"value": _truncate(str(report))}


def _preview_for_step(*, node_id: str, output: dict[str, Any], row: dict[str, Any], blueprint: WorkflowBlueprint) -> str:
    if row.get("status") == "failed":
        return f"Failed: {row.get('error', 'unknown error')}"
    if row.get("kind") == "parallel-group":
        group = blueprint.graph.parallel_groups.get(node_id)
        members = ", ".join(group.nodes) if group is not None else "parallel members"
        return f"Completed parallel group for {members}."
    if "question_count" in output:
        return f"Loaded {output['question_count']} exploratory question(s)."
    if "record_count" in output:
        provider = output.get("provider")
        return f"Produced {output['record_count']} forecast record(s){f' via {provider}' if provider else ''}."
    if "candidate_count" in output:
        return f"Generated {output['candidate_count']} candidate forecast(s)."
    if "training_samples" in output:
        return (
            f"Backtested {output.get('total_evaluations', 0)} resolved forecast(s) "
            f"and prepared {output['training_samples']} training sample(s)."
        )
    if "total_evaluations" in output:
        return f"Scored {output['total_evaluations']} resolved forecast(s)."
    if "report_path" in output:
        return "Attached provider snapshot and report artifacts."
    if "route" in output:
        return f"Routed execution to {output['route']}."
    if "prompt" in output:
        return f"Human gate completed for prompt: {_truncate(str(output['prompt']))}"
    if output:
        return ", ".join(f"{key}={value}" for key, value in output.items())
    return f"Completed {node_id}."


def _save_back_state(*, active_context: SandboxContext, options: Any) -> dict[str, Any]:
    workflow_reference = active_context.workflow_name
    workflow_state = {
        "status": "ready",
        "source_type": active_context.context_type,
        "source_name": active_context.reference_name,
        "existing_workflow_name": workflow_reference,
        "recommended_name": workflow_reference or active_context.blueprint.name,
        "requires_explicit_name": workflow_reference is None,
        "blueprint": active_context.blueprint.to_json_dict(),
        "notes": [
            "Save-back stays explicit; exploratory runs remain labeled as sandbox output.",
            "Workflow persistence must reuse the normal authored-workflow validation path.",
        ],
    }
    profile_state = {
        "status": "ready" if workflow_reference is not None else "requires_workflow_save",
        "workflow_name": workflow_reference,
        "requires_saved_workflow": workflow_reference is None,
        "launch": {
            "provider": options.provider,
            "limit": options.limit,
            "base_url": options.base_url,
            "model": options.model,
            "max_tokens": options.max_tokens,
            "write_report": options.write_report,
            "runs_dir": str(options.runs_dir),
            "user": options.user,
        },
        "notes": [
            "Profiles must reference a workflow explicitly.",
            "Persisting a profile later must not silently capture unsaved workflow snapshots.",
        ],
    }
    return {"mode": SANDBOX_SAVE_BACK_MODE, "workflow": workflow_state, "profile": profile_state}


def _sandbox_labeling(*, question_count: int) -> dict[str, Any]:
    return {
        "classification": "exploratory",
        "surface": "sandbox",
        "display_label": "Exploratory playground session",
        "inspection_mode": SANDBOX_INSPECTION_MODE,
        "save_back_mode": SANDBOX_SAVE_BACK_MODE,
        "benchmark_evidence": False,
        "release_evidence": False,
        "question_count": question_count,
        "batch": question_count > 1,
        "notes": [
            "Sandbox output is inspectable but not benchmark-grade or release-grade evidence by default.",
            "Saving a workflow or profile later does not relabel this exploratory run.",
        ],
    }


def _question_inputs(
    question: SandboxQuestionInput | str | None,
    questions: Sequence[SandboxQuestionInput | str] | None,
) -> tuple[SandboxQuestionInput, ...]:
    if question is not None and questions is not None:
        raise ValueError("pass either question or questions, not both")
    raw_items: Sequence[SandboxQuestionInput | str]
    if question is not None:
        raw_items = (question,)
    elif questions is not None:
        raw_items = questions
    else:
        raise ValueError("sandbox question input is required")
    normalized = tuple(item if isinstance(item, SandboxQuestionInput) else SandboxQuestionInput(prompt=item) for item in raw_items)
    if not normalized:
        raise ValueError("sandbox question input is required")
    if len(normalized) > MAX_SANDBOX_QUESTIONS:
        raise ValueError(f"sandbox accepts at most {MAX_SANDBOX_QUESTIONS} exploratory questions")
    return normalized


def _question_title(prompt: str) -> str:
    first_line = next((line.strip() for line in prompt.splitlines() if line.strip()), prompt.strip())
    return _truncate(first_line, limit=120) or ""


def _template_blueprint_name(template_id: str) -> str:
    return f"playground-{_normalize_token(template_id)}"


def _normalize_token(value: str) -> str:
    normalized = _QUESTION_ID_CHARS.sub("-", value.strip().lower()).strip("-.")
    return normalized or "session"


def _truncate(value: str | None, *, limit: int = 160) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def _workflow_registry(workflows_dir: Path) -> WorkflowRegistry:
    root = workflows_dir if workflows_dir.is_absolute() else Path.cwd() / workflows_dir
    return WorkflowRegistry(local_roots=(root,))


def sandbox_workflow_blueprint(
    source: SandboxSessionResult | Path | Mapping[str, Any],
    *,
    workflow_name: str | None = None,
) -> WorkflowBlueprint:
    payload, _ = _sandbox_session_payload(source)
    workflow_state = _mapping(payload.get("save_back", {}).get("workflow"), context="save_back.workflow")
    raw_name = workflow_name.strip() if isinstance(workflow_name, str) else None
    if workflow_state.get("requires_explicit_name") and not raw_name:
        raise ValueError("sandbox workflow save requires workflow_name for template-backed sessions")
    blueprint = WorkflowBlueprint.from_payload(_mapping(workflow_state.get("blueprint"), context="save_back.workflow.blueprint"))
    target_name = raw_name or _string_or_none(workflow_state.get("existing_workflow_name")) or blueprint.name
    if target_name != blueprint.name:
        blueprint_payload = blueprint.to_json_dict()
        blueprint_payload["name"] = target_name
        blueprint = WorkflowBlueprint.from_payload(blueprint_payload)
    return blueprint


def sandbox_profile_for_save(
    source: SandboxSessionResult | Path | Mapping[str, Any],
    *,
    profile_name: str,
    registry: WorkflowRegistry,
    workflow_name: str | None = None,
) -> WorkflowProfile:
    payload, _ = _sandbox_session_payload(source)
    save_back = _mapping(payload.get("save_back"), context="save_back")
    profile_state = _mapping(save_back.get("profile"), context="save_back.profile")
    target_workflow_name = (
        workflow_name.strip()
        if isinstance(workflow_name, str) and workflow_name.strip()
        else _string_or_none(profile_state.get("workflow_name"))
    )
    if not target_workflow_name:
        raise ValueError("sandbox profile save requires saving the workflow first")
    current_blueprint = sandbox_workflow_blueprint(payload, workflow_name=target_workflow_name)
    saved_blueprint = registry.load(target_workflow_name)
    if current_blueprint.to_json_dict() != saved_blueprint.to_json_dict():
        raise ValueError("sandbox profile save requires saving workflow changes before creating a reusable profile")
    launch = _mapping(profile_state.get("launch"), context="save_back.profile.launch")
    limit = launch.get("limit", 2)
    max_tokens = launch.get("max_tokens", 768)
    return WorkflowProfile(
        name=profile_name,
        workflow_name=target_workflow_name,
        provider=str(launch.get("provider") or current_blueprint.runtime.provider),
        limit=int(limit),
        runs_dir=str(launch.get("runs_dir") or "runs"),
        base_url=_string_or_none(launch.get("base_url")),
        model=_string_or_none(launch.get("model")),
        max_tokens=int(max_tokens),
        write_report=bool(launch.get("write_report", True)),
        user=_string_or_none(launch.get("user")),
    )


def record_sandbox_workflow_save(
    source: SandboxSessionResult | Path | Mapping[str, Any],
    *,
    blueprint: WorkflowBlueprint,
    workflow_path: Path,
) -> dict[str, Any]:
    payload, run_dir = _sandbox_session_payload(source)
    workflow_state = dict(_mapping(payload.get("save_back", {}).get("workflow"), context="save_back.workflow"))
    profile_state = dict(_mapping(payload.get("save_back", {}).get("profile"), context="save_back.profile"))
    workflow_state.update(
        {
            "existing_workflow_name": blueprint.name,
            "recommended_name": blueprint.name,
            "requires_explicit_name": False,
            "blueprint": blueprint.to_json_dict(),
            "saved_workflow_name": blueprint.name,
            "saved_workflow_path": str(workflow_path),
        }
    )
    profile_state.update(
        {
            "status": "ready",
            "workflow_name": blueprint.name,
            "workflow_path": str(workflow_path),
            "requires_saved_workflow": False,
        }
    )
    payload["save_back"] = {"mode": SANDBOX_SAVE_BACK_MODE, "workflow": workflow_state, "profile": profile_state}
    _write_sandbox_session_payload(run_dir, payload)
    return payload


def record_sandbox_profile_save(
    source: SandboxSessionResult | Path | Mapping[str, Any],
    *,
    profile: WorkflowProfile,
    profile_path: Path,
) -> dict[str, Any]:
    payload, run_dir = _sandbox_session_payload(source)
    save_back = _mapping(payload.get("save_back"), context="save_back")
    workflow_state = dict(_mapping(save_back.get("workflow"), context="save_back.workflow"))
    profile_state = dict(_mapping(save_back.get("profile"), context="save_back.profile"))
    profile_state.update(
        {
            "status": "ready",
            "workflow_name": profile.workflow_name,
            "requires_saved_workflow": False,
            "saved_profile_name": profile.name,
            "saved_profile_path": str(profile_path),
        }
    )
    payload["save_back"] = {"mode": SANDBOX_SAVE_BACK_MODE, "workflow": workflow_state, "profile": profile_state}
    _write_sandbox_session_payload(run_dir, payload)
    return payload


def read_sandbox_session(
    source: SandboxSessionResult | Path | Mapping[str, Any],
) -> dict[str, Any]:
    payload, _ = _sandbox_session_payload(source)
    return payload


def _sandbox_session_payload(
    source: SandboxSessionResult | Path | Mapping[str, Any],
) -> tuple[dict[str, Any], Path | None]:
    if isinstance(source, SandboxSessionResult):
        return source.to_json_dict(), source.run_dir
    if isinstance(source, Path):
        path = source / "sandbox_session.json" if source.is_dir() else source
        if path.name != "sandbox_session.json":
            raise ValueError("sandbox session path must reference a run directory or sandbox_session.json")
        if not path.exists():
            raise FileNotFoundError(f"sandbox session does not exist: {path}")
        return _normalize_sandbox_payload(json.loads(path.read_text(encoding="utf-8"))), path.parent
    if not isinstance(source, Mapping):
        raise ValueError("sandbox session source must be a result, run directory, or payload mapping")
    payload = _normalize_sandbox_payload(dict(source))
    run_dir = payload.get("run_dir")
    return payload, Path(str(run_dir)) if isinstance(run_dir, str) and run_dir else None


def _write_sandbox_session_payload(run_dir: Path | None, payload: dict[str, Any]) -> None:
    if run_dir is None:
        return
    normalized = _normalize_sandbox_payload(payload)
    (run_dir / "sandbox_session.json").write_text(json.dumps(normalized, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _normalize_sandbox_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    questions = normalized.get("questions")
    question_count = len(questions) if isinstance(questions, (list, tuple)) else 0
    labeling = normalized.get("labeling")
    base_labeling = _sandbox_labeling(question_count=question_count)
    if isinstance(labeling, Mapping):
        base_labeling.update(dict(labeling))
    base_labeling["question_count"] = question_count
    base_labeling["batch"] = question_count > 1
    normalized["labeling"] = base_labeling

    inspection_steps = normalized.get("inspection_steps")
    if isinstance(inspection_steps, (list, tuple)):
        normalized["inspection_steps"] = _ordered_inspection_steps([dict(step) for step in inspection_steps if isinstance(step, Mapping)])

    save_back = normalized.get("save_back")
    if isinstance(save_back, Mapping):
        normalized["save_back"] = {**dict(save_back), "mode": SANDBOX_SAVE_BACK_MODE}
    return normalized


def _ordered_inspection_steps(steps: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    assigned_orders = {
        int(step["order"])
        for step in steps
        if isinstance(step.get("order"), int) or (isinstance(step.get("order"), str) and step["order"].strip().isdigit())
    }
    next_order = 1
    ordered: list[tuple[tuple[int, int, str], dict[str, Any]]] = []
    for index, step in enumerate(steps, start=1):
        normalized = dict(step)
        raw_order = normalized.get("order")
        if isinstance(raw_order, int) or (isinstance(raw_order, str) and raw_order.strip().isdigit()):
            order = int(raw_order)
        else:
            while next_order in assigned_orders:
                next_order += 1
            order = next_order
            assigned_orders.add(order)
        normalized["order"] = order
        ordered.append(((order, index, str(normalized.get("node_id", ""))), normalized))
    ordered.sort(key=lambda item: item[0])
    return [step for _, step in ordered]


def _mapping(value: Any, *, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    return value


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = [
    "MAX_SANDBOX_QUESTIONS",
    "SANDBOX_CORPUS_ID",
    "SANDBOX_INSPECTION_MODE",
    "SANDBOX_SAVE_BACK_MODE",
    "SANDBOX_SESSION_SCHEMA_VERSION",
    "SandboxContext",
    "SandboxQuestionInput",
    "SandboxSessionResult",
    "read_sandbox_session",
    "record_sandbox_profile_save",
    "record_sandbox_workflow_save",
    "resolve_sandbox_context",
    "run_sandbox_session",
    "sandbox_profile_for_save",
    "sandbox_workflow_blueprint",
    "run_template_sandbox_session",
    "run_workflow_sandbox_session",
]
