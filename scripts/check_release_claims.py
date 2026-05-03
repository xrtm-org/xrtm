#!/usr/bin/env python3
"""Validate release-gated command claims in top-level docs."""

from __future__ import annotations

import argparse
import json
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


def validate_scope(repo_root: Path, contract: dict, scope: str):
    allowed_claims = {normalize_claim(item) for item in contract["allowed_claims"]}
    files = contract["scopes"][scope]["files"]
    failures = []
    for relative_path in files:
        file_path = repo_root / relative_path
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
