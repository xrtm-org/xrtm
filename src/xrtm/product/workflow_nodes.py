"""Product workflow graph node implementations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import fmean
from typing import Any

from xrtm.data.core.schemas.forecast import CausalNode, ForecastOutput, MetadataBase
from xrtm.data.corpora import load_real_binary_questions
from xrtm.forecast.e2e.real_questions import ForecastHarnessRecord, run_real_question_e2e
from xrtm.product.competition import CompetitionPackRegistry, competition_submission_payload
from xrtm.product.pipeline import _run_forecast_stage, _write_eval_payload, _write_train_payload
from xrtm.product.providers import build_provider, local_llm_status, provider_snapshot
from xrtm.product.reports import render_html_report


@dataclass(frozen=True)
class BuiltinWorkflowNodeDefinition:
    name: str
    kind: str
    implementation: str
    summary: str
    safe_offline: bool = True
    real_runtime_ready: bool = False


BUILTIN_WORKFLOW_NODES = (
    BuiltinWorkflowNodeDefinition(
        name="load-questions",
        kind="tool",
        implementation="xrtm.product.workflow_nodes.load_questions_node",
        summary="Load the released real-binary benchmark questions into workflow state.",
    ),
    BuiltinWorkflowNodeDefinition(
        name="forecast-stage",
        kind="model",
        implementation="xrtm.product.workflow_nodes.forecast_node",
        summary="Run the released end-to-end forecast stage and write canonical artifacts.",
        real_runtime_ready=True,
    ),
    BuiltinWorkflowNodeDefinition(
        name="score-stage",
        kind="scorer",
        implementation="xrtm.product.workflow_nodes.score_node",
        summary="Score the current workflow records with the released evaluator.",
    ),
    BuiltinWorkflowNodeDefinition(
        name="backtest-stage",
        kind="model",
        implementation="xrtm.product.workflow_nodes.backtest_node",
        summary="Run the released backtest/training summary stage.",
    ),
    BuiltinWorkflowNodeDefinition(
        name="report-stage",
        kind="tool",
        implementation="xrtm.product.workflow_nodes.report_node",
        summary="Write provider metadata and render the HTML report.",
    ),
    BuiltinWorkflowNodeDefinition(
        name="question-context",
        kind="tool",
        implementation="xrtm.product.workflow_nodes.question_context_node",
        summary="Extract question context for downstream non-LLM or agent nodes.",
    ),
    BuiltinWorkflowNodeDefinition(
        name="provider-free-candidate",
        kind="model",
        implementation="xrtm.product.workflow_nodes.provider_free_candidate_node",
        summary="Generate deterministic provider-free candidate forecasts without writing the final artifacts.",
    ),
    BuiltinWorkflowNodeDefinition(
        name="real-runtime-candidate",
        kind="model",
        implementation="xrtm.product.workflow_nodes.candidate_forecast_node",
        summary="Generate a real-runtime candidate forecast collection without writing the final artifacts.",
        real_runtime_ready=True,
    ),
    BuiltinWorkflowNodeDefinition(
        name="time-series-baseline",
        kind="model",
        implementation="xrtm.product.workflow_nodes.time_series_baseline_node",
        summary="Generate a deterministic non-LLM baseline forecast candidate from time/metadata heuristics.",
    ),
    BuiltinWorkflowNodeDefinition(
        name="ensemble-aggregate",
        kind="aggregator",
        implementation="xrtm.product.workflow_nodes.aggregate_candidate_forecasts_node",
        summary="Combine heterogeneous candidate forecasts into the official workflow records.",
    ),
    BuiltinWorkflowNodeDefinition(
        name="runtime-router",
        kind="router",
        implementation="xrtm.product.workflow_nodes.runtime_router_node",
        summary="Route between real-runtime and fallback branches from product runtime state.",
        real_runtime_ready=True,
    ),
    BuiltinWorkflowNodeDefinition(
        name="human-gate-placeholder",
        kind="human-gate",
        implementation="xrtm.product.workflow_nodes.human_gate_placeholder_node",
        summary="Insert an explicit human approval placeholder into a workflow graph.",
    ),
    BuiltinWorkflowNodeDefinition(
        name="competition-submission",
        kind="tool",
        implementation="xrtm.product.workflow_nodes.competition_submission_node",
        summary="Prepare a redacted dry-run competition submission bundle from the current workflow records.",
    ),
)


def list_builtin_workflow_nodes() -> tuple[BuiltinWorkflowNodeDefinition, ...]:
    return BUILTIN_WORKFLOW_NODES


def load_questions_node(*, state: Any, **_: Any) -> dict[str, Any]:
    options = state.context["options"]
    store = state.context["store"]
    run = state.context["run"]
    questions = state.context.get("questions")
    if questions is None:
        questions = list(options.questions)[: options.limit] if options.questions is not None else load_real_binary_questions(limit=options.limit)
        if not questions:
            raise ValueError("selected corpus did not yield any questions")
        state.context["questions"] = questions
    store.write_jsonl(run, "questions.jsonl", [question.model_dump(mode="json") for question in questions])
    return {"question_count": len(questions), "corpus_id": options.corpus_id}


def forecast_node(*, state: Any, **_: Any) -> dict[str, Any]:
    options = state.context["options"]
    store = state.context["store"]
    run = state.context["run"]
    questions = state.context.get("questions")
    if not questions:
        raise ValueError("forecast node requires questions")
    provider = state.context.get("provider")
    if provider is None:
        provider = build_provider(
            options.provider,
            base_url=options.base_url,
            model=options.model,
            api_key=options.api_key,
        )
        state.context["provider"] = provider
    records = tuple(_run_forecast_stage(options, store=store, run=run, questions=list(questions), provider=provider))
    state.context["records"] = records
    return {"record_count": len(records), "provider": options.provider}


def score_node(*, state: Any, **_: Any) -> dict[str, Any]:
    store = state.context["store"]
    run = state.context["run"]
    records = tuple(state.context.get("records", ()))
    if not records:
        raise ValueError("score node requires forecast records")
    eval_payload = _write_eval_payload(store, run=run, records=records)
    state.context["eval_payload"] = eval_payload
    return {
        "total_evaluations": eval_payload["total_evaluations"],
        "brier_score": eval_payload["summary_statistics"].get("brier_score"),
    }


def backtest_node(*, state: Any, **_: Any) -> dict[str, Any]:
    store = state.context["store"]
    run = state.context["run"]
    records = tuple(state.context.get("records", ()))
    if not records:
        raise ValueError("backtest node requires forecast records")
    train_payload, training_samples = _write_train_payload(store, run=run, records=records)
    state.context["train_payload"] = train_payload
    state.context["training_samples"] = training_samples
    return {
        "total_evaluations": train_payload["total_evaluations"],
        "training_samples": training_samples,
        "brier_score": train_payload["summary_statistics"].get("brier_score"),
    }


def report_node(*, state: Any, **_: Any) -> dict[str, Any]:
    options = state.context["options"]
    store = state.context["store"]
    run = state.context["run"]
    provider = state.context.get("provider")
    if provider is None:
        raise ValueError("report node requires a provider snapshot")
    provider_name = str(state.context.get("resolved_provider_name", options.provider))
    store.write_json(run, "provider.json", provider_snapshot(provider, provider_name, base_url=options.base_url))
    report_path = None
    if options.write_report:
        report_path = render_html_report(run.run_dir)
        run.artifacts["report.html"] = str(report_path)
    return {"report_path": str(report_path) if report_path is not None else None}


def question_context_node(*, state: Any, **_: Any) -> dict[str, Any]:
    questions = state.context.get("questions")
    if not questions:
        raise ValueError("question context node requires loaded questions")
    contexts = {
        question.id: {
            "title": question.title,
            "description": question.description,
            "resolution_criteria": question.resolution_criteria,
            "tags": list(question.metadata.tags),
            "snapshot_time": question.metadata.snapshot_time.isoformat(),
        }
        for question in questions
    }
    state.context["question_contexts"] = contexts
    return {"question_count": len(contexts), "question_ids": list(contexts)}


def provider_free_candidate_node(*, state: Any, config: dict[str, Any] | None = None, node_name: str, **_: Any) -> dict[str, Any]:
    return _candidate_forecast_node(
        state=state,
        config={"provider": "mock", **(config or {})},
        node_name=node_name,
    )


def candidate_forecast_node(*, state: Any, config: dict[str, Any] | None = None, node_name: str, **_: Any) -> dict[str, Any]:
    return _candidate_forecast_node(state=state, config=config or {}, node_name=node_name)


def time_series_baseline_node(*, state: Any, node_name: str, **_: Any) -> dict[str, Any]:
    questions = state.context.get("questions")
    if not questions:
        raise ValueError("time-series baseline node requires loaded questions")
    records = tuple(_baseline_record(question, node_name=node_name) for question in questions)
    state.context.setdefault("candidate_records", {})[node_name] = records
    return {"candidate_count": len(records), "provider": "time-series-baseline"}


def aggregate_candidate_forecasts_node(
    *,
    state: Any,
    config: dict[str, Any] | None = None,
    upstream: dict[str, Any] | None = None,
    **_: Any,
) -> dict[str, Any]:
    config = config or {}
    upstream = upstream or {}
    options = state.context["options"]
    store = state.context["store"]
    run = state.context["run"]
    candidate_records = state.context.get("candidate_records", {})
    if not candidate_records:
        raise ValueError("aggregate node requires candidate forecast collections")
    contributor_names = [name for name in upstream if name in candidate_records] or list(candidate_records)
    if not contributor_names:
        raise ValueError("aggregate node could not resolve candidate contributors")
    weights = {name: float(value) for name, value in config.get("weights", {}).items()}
    aggregated = []
    candidate_lists = [candidate_records[name] for name in contributor_names]
    for question_records in zip(*candidate_lists):
        base_record = question_records[0]
        probabilities = []
        weight_values = []
        for contributor_name, record in zip(contributor_names, question_records):
            probabilities.append(record.output.probability)
            weight_values.append(weights.get(contributor_name, 1.0))
        probability = _weighted_mean(probabilities, weight_values)
        reasoning = "Aggregated from " + ", ".join(
            f"{name}={record.output.probability:.3f}" for name, record in zip(contributor_names, question_records)
        )
        output = base_record.output.model_copy(
            update={
                "probability": probability,
                "reasoning": reasoning,
                "structural_trace": list(base_record.output.structural_trace) + ["ensemble_aggregate"],
                "calibration_metrics": {
                    "aggregation_method": config.get("strategy", "weighted-mean"),
                    "contributors": contributor_names,
                },
            }
        )
        aggregated.append(
            base_record.model_copy(
                update={
                    "output": output,
                    "provider_metadata": {
                        "provider": "ensemble-aggregate",
                        "contributors": contributor_names,
                    },
                }
            )
        )
    state.context["records"] = tuple(aggregated)
    resolved_provider_name = options.provider
    if "primary_candidate" not in contributor_names:
        resolved_provider_name = "mock"
    state.context["resolved_provider_name"] = resolved_provider_name
    if state.context.get("provider") is None:
        state.context["provider"] = build_provider(
            resolved_provider_name,
            base_url=options.base_url,
            model=options.model,
            api_key=options.api_key,
        )
    store.write_jsonl(run, "forecasts.jsonl", [record.model_dump(mode="json") for record in aggregated])
    store.append_event(
        run,
        "forecast_written",
        records=len(aggregated),
        artifact="forecasts.jsonl",
        corpus_id=options.corpus_id,
        contributors=contributor_names,
    )
    return {"record_count": len(aggregated), "contributors": contributor_names}


def runtime_router_node(*, state: Any, config: dict[str, Any] | None = None, **_: Any) -> dict[str, str]:
    config = config or {}
    options = state.context.get("options")
    preferred = str(config.get("preferred_route", "real"))
    fallback = str(config.get("fallback_route", "fallback"))
    if options is None:
        return {"route": fallback}
    if options.provider == "mock":
        return {"route": fallback}
    if options.provider == "local-llm" and config.get("require_healthy", True):
        status = local_llm_status(base_url=options.base_url)
        if not status["healthy"]:
            return {"route": fallback}
    return {"route": preferred}


def human_gate_placeholder_node(*, state: Any, config: dict[str, Any] | None = None, **_: Any) -> dict[str, Any]:
    config = config or {}
    prompt = str(config.get("prompt", "Human approval required before continuing."))
    provider = state.context.get("human_provider")
    if provider is None:
        return {"prompt": prompt, "response": None, "status": "skipped"}
    response = provider.get_human_input(prompt)
    return {"prompt": prompt, "response": response, "status": "completed"}


def competition_submission_node(
    *,
    state: Any,
    config: dict[str, Any] | None = None,
    upstream: dict[str, Any] | None = None,
    **_: Any,
) -> dict[str, Any]:
    config = config or {}
    upstream = upstream or {}
    records = tuple(state.context.get("records", ()))
    if not records:
        raise ValueError("competition submission node requires forecast records")
    pack_name = str(config.get("competition_pack", "")).strip()
    if not pack_name:
        raise ValueError("competition submission node requires config.competition_pack")
    pack = CompetitionPackRegistry().load(pack_name)
    store = state.context["store"]
    run = state.context["run"]
    payload = competition_submission_payload(
        pack,
        records,
        run_id=run.run_id,
        config=config,
        review_status=upstream.get("review_gate"),
    )
    artifact_name = str(config.get("artifact_name", pack.submission_artifact))
    store.write_json(run, artifact_name, payload)
    store.append_event(
        run,
        "competition_submission_prepared",
        competition=pack.name,
        artifact=artifact_name,
        dry_run=pack.dry_run_only,
        forecast_count=len(records),
    )
    state.context["competition_submission"] = payload
    return {"competition": pack.name, "artifact": artifact_name, "forecast_count": len(records), "mode": payload["mode"]}


def aggregate_node(*, state: Any, config: dict[str, Any] | None = None, upstream: dict[str, Any] | None = None, **_: Any) -> Any:
    config = config or {}
    upstream = upstream or {}
    mode = config.get("mode", "collect")
    if mode == "sum":
        total = 0.0
        for payload in upstream.values():
            if isinstance(payload, (int, float)):
                total += float(payload)
            elif isinstance(payload, dict):
                value = payload.get(config.get("value_field", "value"), 0)
                total += float(value)
        return {"value": total}
    return {"items": upstream}


def _candidate_forecast_node(*, state: Any, config: dict[str, Any], node_name: str) -> dict[str, Any]:
    options = state.context["options"]
    questions = state.context.get("questions")
    if not questions:
        raise ValueError("candidate forecast node requires loaded questions")
    provider_name = str(config.get("provider", options.provider))
    provider = build_provider(
        provider_name,
        base_url=config.get("base_url", options.base_url),
        model=config.get("model", options.model),
        api_key=config.get("api_key", options.api_key),
    )
    records = tuple(
        run_real_question_e2e(
            limit=len(questions),
            questions=questions,
            corpus_id=options.corpus_id,
            provider=provider,
            base_url=config.get("base_url", options.base_url),
            model=config.get("model", options.model),
            api_key=config.get("api_key", options.api_key),
            max_tokens=int(config.get("max_tokens", options.max_tokens)),
            artifact_dir=state.context["run"].run_dir / "logs" / node_name,
            write_artifacts=False,
        )
    )
    state.context.setdefault("candidate_records", {})[node_name] = records
    return {"candidate_count": len(records), "provider": provider_name}


def _baseline_record(question: Any, *, node_name: str) -> ForecastHarnessRecord:
    probability = _baseline_probability(question)
    reasoning = "Deterministic non-LLM baseline from question metadata and time-to-resolution heuristics."
    output = ForecastOutput(
        question_id=question.id,
        probability=probability,
        uncertainty=abs(0.5 - probability),
        reasoning=reasoning,
        logical_trace=[
            CausalNode(
                node_id=f"{question.id}:{node_name}",
                event="time_series_baseline",
                probability=probability,
                description=reasoning,
            )
        ],
        structural_trace=[node_name],
        calibration_metrics={"method": "time_series_baseline_v1"},
        metadata=MetadataBase(
            snapshot_time=question.metadata.snapshot_time,
            created_at=datetime.now(timezone.utc),
            tags=list(question.metadata.tags) + ["baseline"],
            subject_type=question.metadata.subject_type,
            source_version="time-series-baseline-v1",
            raw_data={"question_title": question.title},
        ),
    )
    return ForecastHarnessRecord(
        question_id=question.id,
        output=output,
        provider_metadata={"provider": "time-series-baseline"},
    )


def _baseline_probability(question: Any) -> float:
    base = 0.5
    fingerprint = sum(ord(char) for char in question.id) % 11
    base += (fingerprint - 5) * 0.02
    if question.resolution_criteria:
        base += 0.02
    if question.description:
        base += min(len(question.description) / 1000.0, 0.05)
    return max(0.05, min(0.95, round(base, 3)))


def _weighted_mean(values: list[float], weights: list[float]) -> float:
    if not values:
        raise ValueError("cannot aggregate an empty forecast list")
    if not any(weight > 0 for weight in weights):
        return float(fmean(values))
    numerator = sum(value * weight for value, weight in zip(values, weights))
    denominator = sum(weights)
    return numerator / denominator


__all__ = [
    "BUILTIN_WORKFLOW_NODES",
    "BuiltinWorkflowNodeDefinition",
    "aggregate_candidate_forecasts_node",
    "aggregate_node",
    "backtest_node",
    "candidate_forecast_node",
    "competition_submission_node",
    "forecast_node",
    "human_gate_placeholder_node",
    "load_questions_node",
    "list_builtin_workflow_nodes",
    "provider_free_candidate_node",
    "question_context_node",
    "report_node",
    "runtime_router_node",
    "score_node",
    "time_series_baseline_node",
]
