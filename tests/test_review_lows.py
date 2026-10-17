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

r"""Regression tests for the CLI Low batch (version, dotenv, paths, JSON safety)."""

import json
import os
import tomllib
from pathlib import Path

import pytest

from xrtm.e2e.real_questions import _ensure_ignored_artifact_path
from xrtm.product.artifacts import to_json_safe

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_version_fallback_matches_pyproject():
    import re as _re

    from xrtm import version as version_module

    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    source = (REPO_ROOT / "src" / "xrtm" / "version.py").read_text(encoding="utf-8")
    literal = _re.search(r'_FALLBACK_VERSION = "([^"]+)"', source)
    assert literal is not None
    assert literal.group(1) == data["project"]["version"]
    assert version_module.__version__ == data["project"]["version"] or version_module.__version__ == literal.group(1)


def test_artifact_paths_must_stay_under_ignored_roots(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "output").mkdir()

    _ensure_ignored_artifact_path(Path("output"))
    _ensure_ignored_artifact_path(Path("output") / "sub")

    with pytest.raises(ValueError):
        _ensure_ignored_artifact_path(Path("logs/../../etc"))
    with pytest.raises(ValueError):
        _ensure_ignored_artifact_path(Path("/tmp/elsewhere"))


def test_dotenv_parser_handles_quotes_and_comments(tmp_path, monkeypatch):
    from xrtm.cli.main import _load_dotenv

    keys = ("REVIEW_PLAIN", "REVIEW_QUOTED", "REVIEW_SINGLE", "REVIEW_EXPORT")
    for key in keys:
        monkeypatch.delenv(key, raising=False)

    env = tmp_path / ".env"
    env.write_text(
        "REVIEW_PLAIN=value # trailing comment\n"
        'REVIEW_QUOTED="kept # not a comment"\n'
        "REVIEW_SINGLE='x'\n"
        "export REVIEW_EXPORT=1\n"
        "# full line comment\n",
        encoding="utf-8",
    )
    try:
        _load_dotenv(env)
        assert os.environ["REVIEW_PLAIN"] == "value"
        assert os.environ["REVIEW_QUOTED"] == "kept # not a comment"
        assert os.environ["REVIEW_SINGLE"] == "x"
        assert os.environ["REVIEW_EXPORT"] == "1"
    finally:
        for key in keys:
            os.environ.pop(key, None)


def test_to_json_safe_stringifies_unknown_objects():
    class Opaque:
        pass

    safe = to_json_safe({"s": {3, 1, 2}, "obj": Opaque()})

    assert safe["s"] == [1, 2, 3]
    assert isinstance(safe["obj"], str)
    json.dumps(safe)  # must not raise


def test_release_contract_claims_are_real_commands():
    import subprocess
    import sys

    contract = json.loads((REPO_ROOT / "docs" / "release-command-contract.json").read_text(encoding="utf-8"))
    xrtm_exe = Path(sys.executable).parent / "xrtm"

    checked = 0
    for claim in contract["allowed_claims"]:
        if not claim.startswith("xrtm ") or "<" in claim:
            continue
        result = subprocess.run(
            [str(xrtm_exe), *claim.split()[1:], "--help"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0, f"phantom claim: {claim}\n{result.stderr}"
        checked += 1
    assert checked >= 5


def test_dotenv_strips_comments_after_quoted_values_and_bom(tmp_path, monkeypatch):
    from xrtm.cli.main import _load_dotenv

    keys = ("REVIEW_TRAILING", "REVIEW_BOM")
    for key in keys:
        monkeypatch.delenv(key, raising=False)

    env = tmp_path / ".env"
    env.write_text('\ufeffREVIEW_TRAILING="sk-abc" # a comment\nREVIEW_BOM=1\n', encoding="utf-8")
    try:
        _load_dotenv(env)
        # The documented example shape: quotes stripped, comment ignored, and
        # the BOM must not corrupt the first key.
        assert __import__("os").environ["REVIEW_TRAILING"] == "sk-abc"
        assert __import__("os").environ["REVIEW_BOM"] == "1"
    finally:
        import os as _os

        for key in keys:
            _os.environ.pop(key, None)


def test_e2e_retries_when_the_model_returns_prose():
    from xrtm.forecast.core.schemas.forecast import ForecastQuestion
    from xrtm.forecast.providers.inference.base import ModelResponse

    from xrtm.e2e import real_questions as rq

    class _ProseProvider:
        model_id = "stub"
        base_url = "stub://"

        def __init__(self):
            self.calls = 0

        def generate_content(self, prompt, **kwargs):
            self.calls += 1
            return ModelResponse(
                text="The event looks quite likely, but this response contains no JSON object at all.",
                usage={},
                metadata={},
            )

    provider = _ProseProvider()
    question = ForecastQuestion(id="q1", title="Q1")

    with pytest.raises(rq.MissingJSONError):
        rq._generate_valid_forecast_output(
            question=question,
            provider=provider,
            prompt=rq.build_real_question_prompt(question),
            corpus_id="x",
            max_tokens=64,
            temperature=0.0,
        )

    # Regression: the budget-escalation ladder + repair used to be skipped
    # because the parser raised an untyped ValueError (1 call total).
    assert provider.calls >= 3


def test_pipeline_surfaces_partial_forecast_runs(tmp_path, monkeypatch):
    from xrtm.forecast.core.schemas.forecast import ForecastOutput

    import xrtm.product.pipeline as pipeline_module
    from xrtm.e2e.real_questions import ForecastHarnessRecord
    from xrtm.product.pipeline import PipelineOptions, run_pipeline

    record = ForecastHarnessRecord(
        question_id="q1",
        output=ForecastOutput.model_validate(
            {
                "forecast_request_id": "q1",
                "probability": 0.6,
                "reasoning_trace": {"narrative": "n"},
                "metadata": {"source_version": "test"},
            }
        ),
        provider_metadata={"usage": {}},
    )
    # 3 questions requested, only 1 survived: the run must say so.
    monkeypatch.setattr(pipeline_module, "run_real_question_e2e", lambda **kwargs: [record])

    result = run_pipeline(
        PipelineOptions(provider="mock", limit=3, runs_dir=tmp_path / "runs", write_report=False)
    )

    summary = json.loads((result.run.run_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["forecast_count"] == 1
    assert any("2 of 3 questions" in warning for warning in summary["warnings"])

    events = (result.run.run_dir / "events.jsonl").read_text(encoding="utf-8")
    assert "questions_skipped" in events
