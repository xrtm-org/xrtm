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

r"""Tests for provider resolution (defaults must be usable)."""

import pytest

from xrtm.product.providers import (
    DEFAULT_OPENAI_BASE_URL,
    DEFAULT_OPENAI_MODEL,
    MOCK_PROVIDER_NAME,
    build_provider,
)


def test_mock_provider_needs_no_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = build_provider(MOCK_PROVIDER_NAME, base_url=None, model=None, api_key=None)
    assert provider is not None


def test_defaults_fill_model_and_base_url(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    captured = {}

    def fake_get_provider(config):
        captured["config"] = config
        return object()

    monkeypatch.setattr("xrtm.product.providers.ModelFactory.get_provider", fake_get_provider)

    build_provider("openai", base_url=None, model=None, api_key=None)

    assert captured["config"].model_id == DEFAULT_OPENAI_MODEL
    assert captured["config"].base_url == DEFAULT_OPENAI_BASE_URL


def test_explicit_values_and_env_override_defaults(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "env-model")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")

    captured = {}

    def fake_get_provider(config):
        captured["config"] = config
        return object()

    monkeypatch.setattr("xrtm.product.providers.ModelFactory.get_provider", fake_get_provider)

    build_provider("openai", base_url="https://explicit.test/v1", model="explicit-model", api_key=None)

    assert captured["config"].model_id == "explicit-model"
    assert captured["config"].base_url == "https://explicit.test/v1"

    build_provider("openai", base_url=None, model=None, api_key=None)
    assert captured["config"].model_id == "env-model"
    assert captured["config"].base_url == "https://example.test/v1"


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        build_provider("openai", base_url=None, model=None, api_key=None)
