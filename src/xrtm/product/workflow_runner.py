"""Blueprint-backed workflow runner for the XRTM product shell."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from xrtm.product.artifacts import ArtifactStore
from xrtm.product.observability import build_run_summary
from xrtm.product.pipeline import (
    PipelineOptions,
    PipelineResult,
    _finalize_failure,
    _prepare_run,
    _select_questions,
)
from xrtm.product.providers import provider_snapshot
from xrtm.product.reports import render_html_report
from xrtm.product.workflow_graph import WorkflowGraphState, compile_workflow_blueprint, graph_trace_rows
from xrtm.product.workflows import (
    ArtifactPolicy,
    EdgeSpec,
    GraphSpec,
    NodeSpec,
    QuestionSourceSpec,
    RuntimeProfileSpec,
    WorkflowBlueprint,
)


def build_demo_workflow_blueprint(
    *,
    name: str,
    title: str,
    description: str,
    provider: str,
    limit: int,
    max_tokens: int,
    workflow_kind: str = "demo",
) -> WorkflowBlueprint:
    runtime_name = "provider-free-demo" if provider == "mock" else "local-openai-compatible"
    nodes = {
        "load_questions": NodeSpec(kind="tool", implementation="xrtm.product.workflow_nodes.load_questions_node"),
        "forecast": NodeSpec(
            kind="model",
            implementation="xrtm.product.workflow_nodes.forecast_node",
            runtime=runtime_name,
            description="Graph-backed compatibility runner that preserves the current released artifact contract.",
        ),
        "score": NodeSpec(kind="scorer", implementation="xrtm.product.workflow_nodes.score_node"),
        "backtest": NodeSpec(
            kind="model",
            implementation="xrtm.product.workflow_nodes.backtest_node",
        ),
        "report": NodeSpec(kind="tool", implementation="xrtm.product.workflow_nodes.report_node"),
    }
    edges = (
        EdgeSpec(from_node="load_questions", to_node="forecast"),
        EdgeSpec(from_node="forecast", to_node="score"),
        EdgeSpec(from_node="score", to_node="backtest"),
        EdgeSpec(from_node="backtest", to_node="report"),
    )
    return WorkflowBlueprint(
        name=name,
        title=title,
        description=description,
        workflow_kind=workflow_kind,
        questions=QuestionSourceSpec(limit=limit),
        runtime=RuntimeProfileSpec(provider=provider, max_tokens=max_tokens),
        graph=GraphSpec(entry="load_questions", nodes=nodes, edges=edges),
        artifacts=ArtifactPolicy(write_report=True, write_blueprint_copy=True, write_graph_trace=True),
    )


def workflow_to_pipeline_options(
    blueprint: WorkflowBlueprint,
    *,
    command: str,
    runs_dir: Path,
    user: str | None,
    limit: int | None = None,
    provider: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    max_tokens: int | None = None,
    write_report: bool | None = None,
) -> PipelineOptions:
    return PipelineOptions(
        provider=provider or blueprint.runtime.provider,
        limit=limit or blueprint.questions.limit,
        corpus_id=blueprint.questions.corpus_id,
        runs_dir=runs_dir,
        base_url=base_url or blueprint.runtime.base_url,
        model=model or blueprint.runtime.model,
        api_key=api_key or blueprint.runtime.api_key,
        max_tokens=max_tokens or blueprint.runtime.max_tokens,
        write_report=blueprint.artifacts.write_report if write_report is None else write_report,
        command=command,
        user=user,
    )


def run_workflow_blueprint(
    blueprint: WorkflowBlueprint,
    *,
    command: str,
    runs_dir: Path,
    user: str | None = None,
    limit: int | None = None,
    provider: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    max_tokens: int | None = None,
    write_report: bool | None = None,
    node_callables: dict[str, Any] | None = None,
) -> PipelineResult:
    options = workflow_to_pipeline_options(
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
    questions = _select_questions(options)
    store, run = _prepare_run(options, question_count=len(questions))
    compiled = compile_workflow_blueprint(blueprint, node_callables=node_callables)
    state = WorkflowGraphState(
        subject_id=run.run_id,
        context={
            "options": options,
            "store": store,
            "run": run,
            "questions": questions,
        },
    )
    start = time.perf_counter()
    try:
        state = asyncio.run(compiled.orchestrator.run(state, entry_node=compiled.entry_node))
    except Exception as exc:
        _finalize_failure(store=store, run=run, provider=options.provider, started_at=start, error=exc)
        raise
    total_seconds = time.perf_counter() - start
    return _finalize_graph_success(
        blueprint=blueprint,
        compiled=compiled,
        state=state,
        store=store,
        run_artifact=run,
        options=options,
        total_seconds=total_seconds,
    )


def _finalize_graph_success(
    *,
    blueprint: WorkflowBlueprint,
    compiled: Any,
    state: WorkflowGraphState,
    store: ArtifactStore,
    run_artifact: Any,
    options: PipelineOptions,
    total_seconds: float,
) -> PipelineResult:
    records = tuple(state.context.get("records", ()))
    provider = state.context.get("provider")
    resolved_provider_name = str(state.context.get("resolved_provider_name", options.provider))
    eval_payload = state.context.get("eval_payload", {"summary_statistics": {}, "slices": {}, "total_evaluations": 0})
    train_payload = state.context.get(
        "train_payload",
        {"summary_statistics": {}, "slices": {}, "total_evaluations": 0, "training_samples": 0},
    )
    training_samples = int(state.context.get("training_samples", train_payload.get("training_samples", 0)))
    if provider is not None and "provider.json" not in run_artifact.artifacts:
        store.write_json(
            run_artifact,
            "provider.json",
            provider_snapshot(provider, resolved_provider_name, base_url=options.base_url),
        )
    if options.write_report and "report.html" not in run_artifact.artifacts:
        report_path = render_html_report(run_artifact.run_dir)
        run_artifact.artifacts["report.html"] = str(report_path)
    _attach_workflow_artifacts(store, run_artifact, blueprint, compiled=compiled, state=state)
    run_artifact.provider = resolved_provider_name
    summary = build_run_summary(
        status="completed",
        provider=resolved_provider_name,
        total_seconds=total_seconds,
        forecast_records=list(records),
        eval_payload=eval_payload,
        train_payload=train_payload,
        warnings=run_artifact.warnings,
        errors=run_artifact.errors,
    )
    store.write_summary(run_artifact, summary)
    store.append_event(run_artifact, "run_completed", total_seconds=total_seconds)
    store.finish(run_artifact, status="completed")
    return PipelineResult(
        run=run_artifact,
        forecast_records=len(records),
        eval_brier_score=eval_payload["summary_statistics"].get("brier_score"),
        train_brier_score=train_payload["summary_statistics"].get("brier_score"),
        eval_summary=eval_payload["summary_statistics"],
        eval_slices=eval_payload.get("slices", {}),
        train_summary=train_payload["summary_statistics"],
        training_samples=training_samples,
        total_seconds=total_seconds,
    )


def _attach_workflow_artifacts(
    store: ArtifactStore,
    run_artifact: Any,
    blueprint: WorkflowBlueprint,
    *,
    compiled: Any,
    state: WorkflowGraphState,
) -> None:
    if blueprint.artifacts.write_blueprint_copy:
        store.write_json(run_artifact, "blueprint.json", blueprint.to_json_dict())
    if blueprint.artifacts.write_graph_trace:
        store.write_jsonl(run_artifact, "graph_trace.jsonl", graph_trace_rows(compiled, state))
    store.append_event(
        run_artifact,
        "workflow_blueprint_attached",
        workflow=blueprint.name,
        workflow_kind=blueprint.workflow_kind,
        entry=blueprint.graph.entry,
    )


__all__ = [
    "build_demo_workflow_blueprint",
    "run_workflow_blueprint",
    "workflow_to_pipeline_options",
]
