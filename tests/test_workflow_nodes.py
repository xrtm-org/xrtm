from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from xrtm.data.corpora import load_real_binary_questions

from xrtm.product.artifacts import ArtifactStore
from xrtm.product.pipeline import PipelineOptions
from xrtm.product.workflow_nodes import (
    aggregate_candidate_forecasts_node,
    competition_submission_node,
    list_builtin_workflow_nodes,
    provider_free_candidate_node,
    runtime_router_node,
    time_series_baseline_node,
)


def test_builtin_workflow_node_catalog_covers_heterogeneous_categories() -> None:
    kinds = {node.kind for node in list_builtin_workflow_nodes()}

    assert {"tool", "model", "scorer", "aggregator", "router", "human-gate"} <= kinds


def test_provider_free_candidate_node_generates_candidate_records(tmp_path: Path) -> None:
    options = PipelineOptions(provider="mock", limit=1, runs_dir=tmp_path / "runs", command="test-provider-free-candidate")
    store = ArtifactStore(options.runs_dir)
    run = store.create_run(command=options.command, provider=options.provider, package_versions={"xrtm": "test"})
    state = SimpleNamespace(
        context={
            "options": options,
            "run": run,
            "questions": load_real_binary_questions(limit=1),
        }
    )

    summary = provider_free_candidate_node(state=state, node_name="provider_free")

    assert summary["candidate_count"] == 1
    records = state.context["candidate_records"]["provider_free"]
    assert len(records) == 1
    assert 0 <= records[0].output.probability <= 1


def test_time_series_baseline_and_aggregate_candidate_forecasts(tmp_path: Path) -> None:
    questions = load_real_binary_questions(limit=1)
    options = PipelineOptions(provider="mock", limit=1, runs_dir=tmp_path / "runs", command="test-aggregate")
    store = ArtifactStore(options.runs_dir)
    run = store.create_run(command=options.command, provider=options.provider, package_versions={"xrtm": "test"})
    state = SimpleNamespace(
        context={
            "options": options,
            "store": store,
            "run": run,
            "questions": questions,
        }
    )

    baseline_summary = time_series_baseline_node(state=state, node_name="baseline")
    baseline_records = state.context["candidate_records"]["baseline"]
    alt_records = tuple(
        record.model_copy(
            update={
                "output": record.output.model_copy(
                    update={
                        "probability": min(0.95, record.output.probability + 0.2),
                        "reasoning": "Alternative deterministic candidate.",
                    }
                )
            }
        )
        for record in baseline_records
    )
    state.context["candidate_records"]["alt"] = alt_records

    summary = aggregate_candidate_forecasts_node(
        state=state,
        config={"weights": {"baseline": 1, "alt": 3}},
        upstream={"baseline": baseline_summary, "alt": {"candidate_count": 1}},
    )

    assert summary["record_count"] == 1
    final_record = state.context["records"][0]
    assert final_record.output.probability > baseline_records[0].output.probability
    assert (run.run_dir / "forecasts.jsonl").exists()
    exported = json.loads((run.run_dir / "forecasts.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert exported["output"]["probability"] == final_record.output.probability


def test_runtime_router_prefers_fallback_for_mock_provider() -> None:
    state = SimpleNamespace(context={"options": PipelineOptions(provider="mock", command="test-router")})

    route = runtime_router_node(
        state=state,
        config={"preferred_route": "real-runtime", "fallback_route": "provider-free"},
    )

    assert route == {"route": "provider-free"}


def test_competition_submission_node_writes_redacted_bundle(tmp_path: Path) -> None:
    questions = load_real_binary_questions(limit=1)
    options = PipelineOptions(provider="mock", limit=1, runs_dir=tmp_path / "runs", command="test-competition")
    store = ArtifactStore(options.runs_dir)
    run = store.create_run(command=options.command, provider=options.provider, package_versions={"xrtm": "test"})
    state = SimpleNamespace(
        context={
            "options": options,
            "store": store,
            "run": run,
            "questions": questions,
        }
    )
    time_series_baseline_node(state=state, node_name="baseline")
    aggregate_candidate_forecasts_node(
        state=state,
        config={"weights": {"baseline": 1}},
        upstream={"baseline": {"candidate_count": 1}},
    )

    summary = competition_submission_node(
        state=state,
        config={
            "competition_pack": "metaculus-cup",
            "transport": {
                "method": "manual-upload",
                "api_key": "secret-value",
                "headers": {"Authorization": "Bearer super-secret"},
            },
        },
        upstream={"review_gate": {"status": "skipped"}},
    )

    assert summary["competition"] == "metaculus-cup"
    artifact_path = run.run_dir / "competition_submission.json"
    bundle = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert bundle["submission"]["transport"]["api_key"] == "[redacted]"
    assert bundle["submission"]["transport"]["headers"]["Authorization"] == "[redacted]"
