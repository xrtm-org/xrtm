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
from xrtm.version import __version__

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_version_fallback_matches_pyproject():
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert __version__ == data["project"]["version"]


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
