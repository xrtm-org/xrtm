#!/usr/bin/env python3
"""Validate release-gated command claims and runtime-validation metadata."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PREFIXES = (
    ". .venv/bin/activate",
    "export XRTM_LOCAL_LLM_BASE_URL=",
    "forecast --version",
    "pip install xrtm",
    "python3.11 -m venv ",
    "xrtm ",
    "xrtm-data --version",
    "xrtm-forecast --version",
    "xrtm-train --version",
)
RELEASE_CATEGORIES = (
    "openai-compatible-endpoint",
    "coding-agent-cli-contract",
)
LOCAL_OPENAI_COMPATIBLE_PROFILES = {"local-llm"}
CLOUD_API_CLAIM_PATTERNS = (
    re.compile(r"\b(OpenAI API|Azure OpenAI|Groq|OpenRouter|Together AI|Fireworks AI)\b"),
    re.compile(r"\bcommercial OpenAI-compatible\b", re.IGNORECASE),
    re.compile(r"\bhosted OpenAI-compatible\b", re.IGNORECASE),
    re.compile(r"\bcloud API\b", re.IGNORECASE),
    re.compile(r"\bOPENAI_API_KEY\b"),
)


def normalize_claim(text: str) -> str:
    return " ".join(text.strip().rstrip("\\").rstrip(",").split())


def is_command_claim(text: str) -> bool:
    return any(text.startswith(prefix) for prefix in PREFIXES)


def extract_standalone_claim(text: str) -> str | None:
    cleaned = text.strip()
    cleaned = cleaned.lstrip("-*0123456789.) ").lstrip("'\"")
    if cleaned.startswith("`"):
        if cleaned.count("`") < 2:
            return None
        claim, remainder = cleaned[1:].split("`", 1)
        if remainder.strip():
            return None
        cleaned = claim
    else:
        cleaned = cleaned.rstrip("'\"`,")
    claim = normalize_claim(cleaned)
    if is_command_claim(claim):
        return claim
    return None


def iter_claims(path: Path):
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        candidates = []
        stripped = raw_line.strip()
        if stripped.startswith("command:"):
            candidates.append(stripped.split("command:", 1)[1].strip())
        else:
            candidates.append(stripped)

        for candidate in candidates:
            claim = extract_standalone_claim(candidate)
            if claim:
                yield line_number, claim


def load_contract(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_scope_paths(repo_root: Path, contract: dict, scope: str):
    for relative_path in contract["scopes"][scope]["files"]:
        yield relative_path, repo_root / relative_path


def iter_cloud_api_claims(repo_root: Path, contract: dict, scope: str):
    for relative_path, file_path in iter_scope_paths(repo_root, contract, scope):
        if not file_path.exists():
            continue
        lines = file_path.read_text(encoding="utf-8").splitlines()
        for index, raw_line in enumerate(lines):
            line_number = index + 1
            previous_line = lines[index - 1] if index else ""
            if "If this page advertises cloud/API support" in raw_line:
                continue
            if "If this page advertises cloud/API support" in previous_line:
                continue
            for pattern in CLOUD_API_CLAIM_PATTERNS:
                if pattern.search(raw_line):
                    yield relative_path, line_number, raw_line.strip()
                    break


def runtime_validation_config(contract: dict, scope: str) -> dict:
    runtime_validation = contract.get("runtime_validation", {})
    return runtime_validation.get(scope, {})


def has_commercial_openai_profile(profiles: list[str]) -> bool:
    return any(profile.casefold() not in LOCAL_OPENAI_COMPATIBLE_PROFILES for profile in profiles)


def workflow_supports_commercial_gate(repo_root: Path) -> bool:
    workflow_path = repo_root / ".github" / "workflows" / "ci.yml"
    if not workflow_path.exists():
        return False
    workflow_text = workflow_path.read_text(encoding="utf-8")
    return "commercial-openai-compatible" in workflow_text or "Commercial OpenAI-compatible" in workflow_text


def validate_runtime_validation(repo_root: Path, contract: dict, scope: str):
    config = runtime_validation_config(contract, scope)
    if not config:
        return [
            (
                str(Path("docs/release-command-contract.json")),
                0,
                f"missing runtime_validation entry for scope {scope!r}",
            )
        ]

    failures = []
    categories = config.get("first_class_categories", [])
    if categories != list(RELEASE_CATEGORIES):
        failures.append(
            (
                "docs/release-command-contract.json",
                0,
                "runtime_validation first_class_categories must be exactly ['openai-compatible-endpoint', 'coding-agent-cli-contract']",
            )
        )

    if config.get("baseline_mode") != "provider-free":
        failures.append(
            (
                "docs/release-command-contract.json",
                0,
                "runtime_validation baseline_mode must stay 'provider-free'",
            )
        )

    openai_profiles = config.get("openai_compatible_profiles", {})
    local_profiles = openai_profiles.get("local", [])
    commercial_profiles = openai_profiles.get("commercial", [])
    if "local-llm" not in local_profiles:
        failures.append(
            (
                "docs/release-command-contract.json",
                0,
                "runtime_validation must classify local-llm under openai_compatible_profiles.local",
            )
        )

    prohibited_profiles = set(categories) | set(local_profiles) | set(commercial_profiles)
    if "provider-free" in prohibited_profiles:
        failures.append(
            (
                "docs/release-command-contract.json",
                0,
                "provider-free is a baseline/testing mode and must not appear as a first-class category or profile",
            )
        )

    docs_claims = list(iter_cloud_api_claims(repo_root, contract, scope))
    cloud_api_support_claimed = bool(config.get("cloud_api_support_claimed"))
    if docs_claims and not cloud_api_support_claimed:
        relative_path, line_number, claim = docs_claims[0]
        failures.append(
            (
                relative_path,
                line_number,
                f"docs advertise cloud/API support but runtime_validation.cloud_api_support_claimed is false: {claim}",
            )
        )
    if cloud_api_support_claimed and not docs_claims:
        failures.append(
            (
                "docs/release-command-contract.json",
                0,
                "runtime_validation.cloud_api_support_claimed is true but no scoped release doc currently advertises cloud/API support",
            )
        )
    if cloud_api_support_claimed and not has_commercial_openai_profile(commercial_profiles):
        failures.append(
            (
                "docs/release-command-contract.json",
                0,
                "cloud/API claims require at least one commercial OpenAI-compatible profile in runtime_validation.openai_compatible_profiles.commercial",
            )
        )
    if cloud_api_support_claimed and not workflow_supports_commercial_gate(repo_root):
        failures.append(
            (
                ".github/workflows/ci.yml",
                0,
                "cloud/API claims require a Commercial OpenAI-compatible Gate 2 validation surface in CI",
            )
        )
    return failures


def validate_scope(repo_root: Path, contract: dict, scope: str):
    allowed_claims = {normalize_claim(item) for item in contract["allowed_claims"]}
    failures = list(validate_runtime_validation(repo_root, contract, scope))
    for relative_path, file_path in iter_scope_paths(repo_root, contract, scope):
        if not file_path.exists():
            failures.append((relative_path, 0, "missing file"))
            continue
        for line_number, claim in iter_claims(file_path):
            if claim not in allowed_claims:
                failures.append((relative_path, line_number, claim))
    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--contract", type=Path, default=Path("docs/release-command-contract.json"))
    parser.add_argument("--scope", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    contract = load_contract(args.contract)
    if args.scope not in contract["scopes"]:
        print(f"Unknown scope: {args.scope}", file=sys.stderr)
        return 2
    failures = validate_scope(args.repo_root, contract, args.scope)
    if failures:
        print(
            f"Release command-claim check failed for scope {args.scope!r} against xrtm {contract['release_version']}",
            file=sys.stderr,
        )
        for relative_path, line_number, claim in failures:
            location = relative_path if line_number == 0 else f"{relative_path}:{line_number}"
            print(f"  {location}: {claim}", file=sys.stderr)
        return 1
    print(f"Release command-claim check passed for scope {args.scope!r} against xrtm {contract['release_version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
