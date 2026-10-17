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

r"""CLI start errors must be attributed correctly and never traceback."""

from unittest.mock import patch

from click.testing import CliRunner

from xrtm.cli.main import cli


def test_limit_error_does_not_suggest_api_key(tmp_path):
    result = CliRunner().invoke(cli, ["start", "--limit", "0", "--runs-dir", str(tmp_path / "runs")])

    assert "limit must be at least 1" in result.output
    assert "Set your API key" not in result.output
    assert result.exit_code == 1  # failures must not exit 0 for cron/scripts


def test_connection_error_does_not_suggest_api_key(tmp_path):
    with patch("xrtm.cli.main.launch_module.run_forecasts", side_effect=ConnectionError("connection refused")):
        result = CliRunner().invoke(cli, ["start", "--limit", "1", "--runs-dir", str(tmp_path / "runs")])

    assert "connection refused" in result.output
    assert "Set your API key" not in result.output
    assert "network connection" in result.output
    assert result.exit_code == 1


def test_missing_key_error_suggests_setting_key(tmp_path):
    with patch("xrtm.cli.main.launch_module.run_forecasts", side_effect=ValueError("OPENAI_API_KEY not set")):
        result = CliRunner().invoke(cli, ["start", "--limit", "1", "--runs-dir", str(tmp_path / "runs")])

    assert "Set your API key" in result.output
    assert result.exit_code == 1


def test_port_number_4010_is_not_mistaken_for_auth(tmp_path):
    with patch("xrtm.cli.main.launch_module.run_forecasts", side_effect=ConnectionError("connection refused to http://localhost:4010/v1")):
        result = CliRunner().invoke(cli, ["start", "--limit", "1", "--runs-dir", str(tmp_path / "runs")])

    assert "Set your API key" not in result.output
    assert "network connection" in result.output
