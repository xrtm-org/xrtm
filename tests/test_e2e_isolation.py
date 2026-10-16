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

r"""One bad question must not discard the rest of the E2E batch."""

from xrtm.forecast.providers.inference.mock_provider import MockProvider

from xrtm.e2e import real_questions as rq


def test_e2e_skips_failing_questions_and_keeps_partial_records(monkeypatch):
    calls = {"n": 0}
    real_generate = rq._generate_valid_forecast_output

    def flaky(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise rq.ForecastOutputValidationError("bad output")
        return real_generate(**kwargs)

    monkeypatch.setattr(rq, "_generate_valid_forecast_output", flaky)

    records = rq.run_real_question_e2e(limit=2, provider=MockProvider(), write_artifacts=False)

    assert len(records) == 1
    assert calls["n"] == 2
