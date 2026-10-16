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

r"""Tests for the run-history read model (export, compare, list, traversal)."""

import json
from pathlib import Path

import pytest

from xrtm.product.history import (
    compare_runs,
    export_run,
    list_runs,
    resolve_run_dir,
    run_detail,
)


def _make_run(root: Path, run_id: str, *, status="completed", provider="mock", brier=0.04) -> Path:
    run_dir = root / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": status,
                "provider": provider,
                "user": "tester",
                "command": "xrtm start",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "run_summary.json").write_text(
        json.dumps(
            {
                "status": status,
                "provider": provider,
                "total_seconds": 1.5,
                "forecast_count": 2,
                "eval_payload": {"summary_statistics": {"brier_score": brier, "ece": 0.01}},
                "train_payload": {"summary_statistics": {"brier_score": 0.05}, "training_samples": 7},
                "warnings": [],
                "errors": [],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "forecasts.jsonl").write_text(
        json.dumps({"question_id": "q1", "output": {"question_id": "q1"}}) + "\n", encoding="utf-8"
    )
    (run_dir / "questions.jsonl").write_text(json.dumps({"id": "q1", "title": "Q1"}) + "\n", encoding="utf-8")
    return run_dir


def test_run_detail_composes_documented_shape(tmp_path):
    detail = run_detail(_make_run(tmp_path, "run-1"))

    assert detail["run"]["run_id"] == "run-1"
    assert detail["summary"]["total_seconds"] == 1.5
    assert detail["forecasts"][0]["question_id"] == "q1"
    assert detail["questions"][0]["id"] == "q1"


def test_export_csv_no_longer_crashes(tmp_path):
    run_dir = _make_run(tmp_path, "run-1")

    out = export_run(run_dir, tmp_path / "export.csv", format="csv")

    assert out.is_file()
    assert "q1" in out.read_text(encoding="utf-8")


def test_compare_runs_resolves_metrics(tmp_path):
    left = _make_run(tmp_path, "run-1", brier=0.04)
    right = _make_run(tmp_path, "run-2", brier=0.09)

    rows = {row["metric"]: row for row in compare_runs(left, right)}

    assert rows["eval_brier"]["left"] == pytest.approx(0.04)
    assert rows["eval_brier"]["right"] == pytest.approx(0.09)
    assert rows["forecast_count"]["left"] == 2
    assert rows["training_samples"]["left"] == 7


def test_list_runs_filters_by_query(tmp_path):
    _make_run(tmp_path, "run-1", provider="mock")
    _make_run(tmp_path, "run-2", provider="openai")

    assert len(list_runs(tmp_path)) == 2
    assert len(list_runs(tmp_path, query="openai")) == 1
    assert [item["run_id"] for item in list_runs(tmp_path, query="run-2")] == ["run-2"]


def test_resolve_run_dir_rejects_traversal(tmp_path):
    with pytest.raises(ValueError):
        resolve_run_dir(tmp_path, "../outside")
    with pytest.raises(FileNotFoundError):
        resolve_run_dir(tmp_path, "missing-run")
