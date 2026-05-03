# coding=utf-8
# Copyright 2026 XRTM Team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the large-scale validation harness."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest
from xrtm.data.corpora import CorpusSplitter, CorpusTier, SplitConfig, get_corpus

import xrtm.product.validation as validation_module
from xrtm.product.validation import (
    ValidationOptions,
    ValidationSafetyError,
    list_validation_corpora,
    prepare_validation_corpus,
    run_validation,
)


def test_list_validation_corpora() -> None:
    """Test corpus listing with various filters."""
    # List all corpora
    all_corpora = list_validation_corpora()
    assert len(all_corpora) >= 1
    assert any(c["corpus_id"] == "xrtm-real-binary-v1" for c in all_corpora)

    # List only release-gate approved
    approved = list_validation_corpora(release_gate_only=True)
    assert len(approved) >= 1
    for corpus in approved:
        assert corpus["release_gate_approved"] is True
        assert corpus["tier"] == "tier-1"

    # List Tier 1 only
    tier1 = list_validation_corpora(tier=CorpusTier.TIER_1)
    assert len(tier1) >= 1
    for corpus in tier1:
        assert corpus["tier"] == "tier-1"


def test_validation_run_basic() -> None:
    """Test basic validation run with minimal configuration."""
    options = ValidationOptions(
        corpus_id="xrtm-real-binary-v1",
        provider="mock",
        limit=2,
        iterations=1,
        output_dir=Path(".cache/validation-tests"),
        write_artifacts=False,
    )

    report = run_validation(options)

    assert report["schema_version"] == "xrtm.validation.v1"
    assert report["corpus"]["corpus_id"] == "xrtm-real-binary-v1"
    assert report["corpus"]["tier"] == "tier-1"
    assert report["configuration"]["limit"] == 2
    assert report["configuration"]["iterations"] == 1
    assert report["configuration"]["runs_dir"] == "runs-validation"
    assert report["configuration"]["output_dir"] == ".cache/validation-tests"
    assert report["summary"]["total_forecasts"] == 2
    assert report["summary"]["total_duration_seconds"] > 0
    assert len(report["iterations"]) == 1
    assert report["evaluation"]["mean_eval_ece"] is not None
    assert report["evaluation"]["best_eval_run_id"] == report["iterations"][0]["run_id"]


def test_validation_run_multiple_iterations() -> None:
    """Test validation with multiple iterations."""
    options = ValidationOptions(
        corpus_id="xrtm-real-binary-v1",
        provider="mock",
        limit=1,
        iterations=3,
        output_dir=Path(".cache/validation-tests"),
        write_artifacts=False,
    )

    report = run_validation(options)

    assert len(report["iterations"]) == 3
    assert report["summary"]["total_forecasts"] == 3
    assert report["summary"]["mean_iteration_seconds"] > 0

    # Check all iterations have required fields
    for iteration in report["iterations"]:
        assert "iteration" in iteration
        assert "run_id" in iteration
        assert "duration_seconds" in iteration
        assert "forecast_records" in iteration
        assert "eval_ece" in iteration
        assert "eval_reliability" in iteration


def test_validation_report_includes_compare_ready_metrics() -> None:
    """Validation reports should surface score interpretation and compare-ready ids."""
    report = run_validation(
        ValidationOptions(
            corpus_id="xrtm-real-binary-v1",
            provider="mock",
            limit=1,
            iterations=2,
            output_dir=Path(".cache/validation-tests"),
            write_artifacts=False,
        )
    )

    evaluation = report["evaluation"]
    assert evaluation["best_eval_run_id"] in {item["run_id"] for item in report["iterations"]}
    assert evaluation["worst_eval_run_id"] in {item["run_id"] for item in report["iterations"]}
    assert evaluation["eval_brier_spread"] >= 0
    assert evaluation["eval_ece_spread"] >= 0
    assert evaluation["mean_eval_reliability"] is not None
    assert evaluation["mean_eval_resolution"] is not None


def test_validation_run_uses_selected_split_question_count() -> None:
    """Validation should pass the selected split into the product pipeline."""
    source = get_corpus("xrtm-real-binary-v1")
    questions = asyncio.run(source.fetch_questions(limit=1000))
    expected_held_out = len(CorpusSplitter(SplitConfig()).split_corpus(questions)["held-out"])

    options = ValidationOptions(
        corpus_id="xrtm-real-binary-v1",
        split="held-out",
        provider="mock",
        limit=10,
        iterations=1,
        output_dir=Path(".cache/validation-tests"),
        write_artifacts=False,
    )

    report = run_validation(options)

    assert report["configuration"]["split"] == "held-out"
    assert report["configuration"]["selected_questions"] == expected_held_out
    assert report["summary"]["total_forecasts"] == expected_held_out
    assert report["configuration"]["question_pool_size"] == len(questions)
    assert report["configuration"]["split_signature"] is not None


def test_validation_release_gate_mode_with_tier1() -> None:
    """Test release-gate mode accepts Tier 1 corpus."""
    options = ValidationOptions(
        corpus_id="xrtm-real-binary-v1",
        provider="mock",
        limit=1,
        iterations=1,
        output_dir=Path(".cache/validation-tests"),
        write_artifacts=False,
        release_gate_mode=True,
    )

    report = run_validation(options)

    assert report["corpus"]["release_gate_approved"] is True
    assert report["configuration"]["release_gate_mode"] is True


def test_validation_safety_limits_local_llm() -> None:
    """Test safety limits for local-llm provider."""
    with pytest.raises(ValidationSafetyError, match="Safety limit exceeded"):
        ValidationOptions(
            corpus_id="xrtm-real-binary-v1",
            provider="local-llm",
            limit=100,  # Exceeds default limit
            iterations=1,
            allow_unsafe_local_llm=False,
        )

    # Should work with override flag
    options = ValidationOptions(
        corpus_id="xrtm-real-binary-v1",
        provider="local-llm",
        limit=100,
        iterations=1,
        allow_unsafe_local_llm=True,
    )
    assert options.limit == 100


def test_validation_options_validation() -> None:
    """Test ValidationOptions input validation."""
    # Invalid limit
    with pytest.raises(ValueError, match="Invalid limit"):
        ValidationOptions(limit=0)

    # Invalid iterations
    with pytest.raises(ValueError, match="Invalid iterations"):
        ValidationOptions(iterations=0)


def test_validation_artifact_generation() -> None:
    """Test validation artifact generation."""
    options = ValidationOptions(
        corpus_id="xrtm-real-binary-v1",
        provider="mock",
        limit=1,
        iterations=1,
        output_dir=Path(".cache/validation-tests"),
        write_artifacts=True,
    )

    report = run_validation(options)

    assert "artifact_path" in report
    artifact_path = Path(report["artifact_path"])
    assert artifact_path.exists()
    assert artifact_path.suffix == ".json"
    assert "validation-xrtm-real-binary-v1" in artifact_path.name

    # Verify artifact content
    import json
    artifact_data = json.loads(artifact_path.read_text())
    assert artifact_data["schema_version"] == "xrtm.validation.v1"
    assert artifact_data["corpus"]["corpus_id"] == "xrtm-real-binary-v1"


def test_validation_artifact_generation_avoids_same_second_collisions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Repeated same-second validation runs should keep distinct artifacts."""

    class FrozenDateTime:
        @classmethod
        def now(cls, tz: timezone | None = None) -> datetime:
            return datetime(2026, 5, 2, 1, 8, 20, tzinfo=timezone.utc if tz is not None else None)

    monkeypatch.setattr(validation_module, "datetime", FrozenDateTime)
    output_dir = tmp_path / "validation-artifacts"
    options = ValidationOptions(
        corpus_id="xrtm-real-binary-v1",
        provider="mock",
        limit=1,
        iterations=1,
        output_dir=output_dir,
        write_artifacts=True,
    )

    first = run_validation(options)
    second = run_validation(options)

    first_path = Path(first["artifact_path"])
    second_path = Path(second["artifact_path"])
    assert first_path.exists()
    assert second_path.exists()
    assert first_path.name == "validation-xrtm-real-binary-v1-20260502T010820Z.json"
    assert second_path.name == "validation-xrtm-real-binary-v1-20260502T010820Z-01.json"
    assert len(list(output_dir.glob("validation-xrtm-real-binary-v1-*.json"))) == 2


def test_prepare_validation_corpus_fixture_preview(tmp_path: Path) -> None:
    """Preparing FOReCAst via the product layer should expose preview metadata."""
    report = prepare_validation_corpus(
        "forecast-v1",
        cache_root=tmp_path / "corpus-cache",
        use_hf_datasets=False,
    )

    assert report["corpus"]["corpus_id"] == "forecast-v1"
    assert report["availability"]["source_mode"] == "preview"
    assert report["availability"]["already_cached"] is True
    assert report["availability"]["record_count"] == 3


def test_validation_report_marks_forecast_preview(monkeypatch, tmp_path: Path) -> None:
    """Validation should disclose when forecast-v1 is still using the preview fixture."""
    monkeypatch.setenv("XRTM_CORPUS_CACHE", str(tmp_path / "corpus-cache"))

    with pytest.warns(UserWarning, match="preview"):
        report = run_validation(
            ValidationOptions(
                corpus_id="forecast-v1",
                provider="mock",
                limit=2,
                iterations=1,
                output_dir=tmp_path / "validation-output",
                write_artifacts=False,
            )
        )

    assert report["corpus"]["corpus_id"] == "forecast-v1"
    assert report["corpus"]["source_mode"] == "preview"
