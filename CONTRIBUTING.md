# Contributing to xrtm

`xrtm` is the product shell for the released XRTM workflow: the CLI, canonical run artifacts, and the newcomer/operator docs path.

## Start with the right repo

| If you are changing... | Start here | Why |
| --- | --- | --- |
| released CLI flows, run artifacts, WebUI/TUI behavior, or product docs | `xrtm` | this repo owns the published product surface |
| runtime APIs, providers, orchestration internals, or code-first examples | [`forecast`](https://github.com/xrtm-org/forecast) | package behavior belongs with the runtime |
| public site navigation, repo maps, or presentation-layer docs | [`xrtm.org`](https://github.com/xrtm-org/xrtm.org) | the site mirrors accepted product/governance truth |
| schemas, compatibility rules, or contributor/review policy | [`governance`](https://github.com/xrtm-org/governance) | cross-repo standards live there |

If work spans multiple repos, land the source-of-truth change first and mirror it outward after that decision is accepted.

## Local setup

For a normal single-repo change:

```bash
uv sync
```

If you are validating coordinated sibling changes in the standard XRTM workspace, install sibling repos in editable mode so local package changes resolve together:

```bash
uv sync
uv pip install -e ../data -e ../eval -e ../forecast -e ../train
```

## Ground rules

1. Branch from `main`.
2. Use `uv` for repository automation when possible.
3. Keep release-pinned docs on the currently published package surface.
4. Use explicit upstream refs for coordinated changes. Same-name sibling branches are a convenience, not a compatibility contract.

## Where docs, tests, and policies belong

- **`xrtm`**: released product docs, CLI behavior, canonical run-artifact expectations, and product-level tests.
- **`forecast` / other package repos**: package internals, lower-level API docs, examples, and runtime/library tests.
- **`xrtm.org`**: newcomer-facing presentation, repo maps, and mirrors of accepted released behavior.
- **`governance`**: schemas, compatibility rules, release discipline, and contributor/review policy.

When in doubt: behavior and tests belong with the owning implementation repo; policy belongs in governance; public presentation belongs on the site only after the source-of-truth change is settled.

## Release-pinned docs vs next-release work

These surfaces are release-pinned:

- `README.md`
- `docs/getting-started.md`
- `docs/operator-runbook.md`
- release-safe command claims in `docs/release-command-contract.json`
- mirrored newcomer/operator pages on `xrtm.org`

Rules:

1. Only describe commands, versions, and behavior that already exist in the published package set.
2. If a useful feature exists in source but is not published yet, record it in `docs/next-release-feature-track.md` with an explicit governance status and graduation evidence.
3. Do not update release-pinned docs for a branch-only convenience until the package release, release contract, and released-stack smoke all move together.

## Published-surface changes

Treat these as stable product surfaces unless a compatibility note says otherwise:

- documented CLI commands and flags
- documented Python entrypoints
- run-artifact shapes and exported file semantics
- install/version expectations

If your change touches one of them:

1. add tests or compatibility notes for the affected surface
2. link the upstream/downstream coordination record when sibling repos are involved
3. update `xrtm.org` only after the product or governance source of truth is settled

## Validation before opening a PR

Run the normal package gate:

```bash
python scripts/check_release_claims.py --repo-root . --contract docs/release-command-contract.json --scope xrtm
uv run ruff check .
uv run mypy src/xrtm
uv run pytest tests
uv run --with build python -m build
```

If the change affects published package behavior, also record the released-artifact or downstream smoke you ran, or explain why that follow-up belongs in a coordinated sibling PR.

For coordinated release work, treat clean-room evidence as part of the release record rather than optional extra credit:

- provider-free: capture the disposable Docker lane from wheelhouse before publish and from PyPI after publish (`./workspace.sh docker-provider-free-acceptance --artifact-source wheelhouse|pypi` from the stack root, or the matching CI release-validation job artifact)
- local-LLM: capture the disposable Docker lane when provider/local-model behavior changed and compatible hardware/model access exists; otherwise write down the explicit defer reason in the PR or release note

## Cross-repo policy

Use the governance repo as the shared operating manual:

- [PR Acceptance Policy](https://github.com/xrtm-org/governance/blob/main/policies/pr-acceptance-policy.md)
- [Release Readiness Policy](https://github.com/xrtm-org/governance/blob/main/policies/release-readiness-policy.md)
- [Cross-Repository Compatibility and Coordination Policy](https://github.com/xrtm-org/governance/blob/main/policies/cross-repo-compatibility-policy.md)
- [Feature Status and Graduation Policy](https://github.com/xrtm-org/governance/blob/main/policies/feature-status-and-graduation-policy.md)
