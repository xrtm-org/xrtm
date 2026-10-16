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

r"""Product honesty tests: no fabricated scores, accurate readiness copy."""

import io

from rich.console import Console

from xrtm.product.doctor import _print_readiness_summary
from xrtm.product.pipeline import _eval_payload, _evaluate_resolved_forecasts


class _EmptyReport:
    metric_name = "Brier"
    mean_score = 0.0
    total_evaluations = 0
    summary_statistics = {}
    reliability_bins = []
    slices = {}


class _RealReport:
    metric_name = "Brier"
    mean_score = 0.04
    total_evaluations = 2
    summary_statistics = {"brier_score": 0.04}
    reliability_bins = []
    slices = {}


def test_pending_report_claims_no_score(monkeypatch):
    monkeypatch.setattr(
        "xrtm.product.pipeline.evaluate_forecast_records_with_backtest_runner",
        lambda records: _EmptyReport(),
    )
    payload = _eval_payload(_evaluate_resolved_forecasts(()))
    assert payload["mean_score"] is None
    assert payload["total_evaluations"] == 0
    assert payload["summary_statistics"]["status"] == "pending_resolution"


def test_real_report_passes_through(monkeypatch):
    monkeypatch.setattr(
        "xrtm.product.pipeline.evaluate_forecast_records_with_backtest_runner",
        lambda records: _RealReport(),
    )
    payload = _eval_payload(_evaluate_resolved_forecasts(()))
    assert payload["mean_score"] == 0.04
    assert payload["total_evaluations"] == 2


def test_evaluator_failure_is_reported_not_faked(monkeypatch):
    def _boom(records):
        raise RuntimeError("no data")

    monkeypatch.setattr("xrtm.product.pipeline.evaluate_forecast_records_with_backtest_runner", _boom)
    payload = _eval_payload(_evaluate_resolved_forecasts(()))
    assert payload["mean_score"] is None
    assert payload["summary_statistics"]["status"] == "evaluation_failed"


def test_doctor_readiness_copy_is_accurate(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    stream = io.StringIO()
    console = Console(file=stream, width=200)
    _print_readiness_summary(console, True)
    output = stream.getvalue()
    assert "OPENAI_API_KEY is not set" in output
