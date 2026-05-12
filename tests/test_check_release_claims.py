from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "check_release_claims.py"
    spec = importlib.util.spec_from_file_location("check_release_claims", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_contract(
    *,
    cloud_api_support_claimed: bool,
    commercial_profiles: list[str],
    categories: list[str] | None = None,
) -> dict:
    categories = categories or ["openai-compatible-endpoint", "coding-agent-cli-contract"]
    contract = {
        "release_version": "0.3.1",
        "allowed_claims": ["xrtm doctor"],
        "scopes": {"xrtm": {"files": ["README.md"]}},
        "runtime_validation": {
            "xrtm": {
                "baseline_mode": "provider-free",
                "first_class_categories": categories,
                "openai_compatible_profiles": {
                    "local": ["local-llm"],
                    "commercial": commercial_profiles,
                },
                "coding_agent_cli_profiles": [],
                "cloud_api_support_claimed": cloud_api_support_claimed,
            }
        },
    }
    return contract


def test_validate_scope_accepts_provider_free_baseline_with_local_profile_only(tmp_path) -> None:
    module = _load_module()
    (tmp_path / "README.md").write_text("`xrtm doctor`\n", encoding="utf-8")

    failures = module.validate_scope(
        tmp_path,
        _write_contract(cloud_api_support_claimed=False, commercial_profiles=[]),
        "xrtm",
    )

    assert failures == []


def test_validate_scope_rejects_provider_free_as_first_class_category(tmp_path) -> None:
    module = _load_module()
    (tmp_path / "README.md").write_text("`xrtm doctor`\n", encoding="utf-8")

    failures = module.validate_scope(
        tmp_path,
        _write_contract(
            cloud_api_support_claimed=False,
            commercial_profiles=[],
            categories=["openai-compatible-endpoint", "provider-free"],
        ),
        "xrtm",
    )

    assert any("first_class_categories" in failure[2] for failure in failures)


def test_validate_scope_requires_commercial_profile_when_docs_claim_cloud_api_support(tmp_path) -> None:
    module = _load_module()
    (tmp_path / "README.md").write_text("XRTM supports the OpenAI API for hosted runs.\n", encoding="utf-8")

    failures = module.validate_scope(
        tmp_path,
        _write_contract(cloud_api_support_claimed=True, commercial_profiles=[]),
        "xrtm",
    )

    assert any("commercial OpenAI-compatible profile" in failure[2] for failure in failures)
    assert any("Commercial OpenAI-compatible Gate 2 validation surface" in failure[2] for failure in failures)


def test_validate_scope_rejects_untracked_cloud_api_claims(tmp_path) -> None:
    module = _load_module()
    (tmp_path / "README.md").write_text("Set OPENAI_API_KEY before using the OpenAI API path.\n", encoding="utf-8")

    failures = module.validate_scope(
        tmp_path,
        _write_contract(cloud_api_support_claimed=False, commercial_profiles=[]),
        "xrtm",
    )

    assert any("docs advertise cloud/API support" in failure[2] for failure in failures)


def test_validate_scope_ignores_policy_note_about_future_cloud_api_claims(tmp_path) -> None:
    module = _load_module()
    (tmp_path / "README.md").write_text(
        "If this page advertises cloud/API support, release validation must\n"
        "also include at least one commercial OpenAI-compatible profile.\n"
        "`xrtm doctor`\n",
        encoding="utf-8",
    )

    failures = module.validate_scope(
        tmp_path,
        _write_contract(cloud_api_support_claimed=False, commercial_profiles=[]),
        "xrtm",
    )

    assert failures == []
