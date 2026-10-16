# Interface parity matrix

This page is the implementation-level source of truth for CLI/WebUI parity in
`xrtm`. It follows the governance
[Interface Parity and Claim Ownership Policy](https://github.com/xrtm-org/governance/blob/main/policies/interface-parity-and-claim-ownership-policy.md).

**Current baseline: published `xrtm==0.10.6`. The release ships a CLI only.**
Every WebUI, authoring, playground, profile, monitor, batch, version, webhook,
report, artifact, workflow and benchmark lane from the 0.8.x train is
**withdrawn from release claims** until it ships again with matching Gate 1 +
Gate 2 evidence in the same package. Release-pinned docs must not mention
commands that are not in the shipped command tree; a test enforces the claims
list in `docs/release-command-contract.json`.

## Status legend

| Status | Meaning |
| --- | --- |
| `released` | Shipped in the current package and covered by release evidence. |
| `withdrawn` | Was claimed in a previous train; no longer ships and may not be referenced by release docs. |
| `future-release` | Implemented or approved for a later train, but must stay out of released claims until package/docs/gates land together. |

## Released CLI surface (`xrtm==0.10.6`)

| Command | User job | Status | Product service owner | Claim owner | Release gate |
| --- | --- | --- | --- | --- | --- |
| `xrtm --version` | Identify the installed release | `released` | `xrtm.version` | `xrtm` docs | CI smoke |
| `xrtm doctor` | Readiness/configuration check | `released` | `xrtm.product.doctor.run_doctor` | `xrtm` docs | CI smoke |
| `xrtm start` | Forecast a bounded question batch into `runs/<id>/` | `released` | `xrtm.product.pipeline.run_pipeline` via `xrtm.product.launch` | `xrtm` docs | CI mock smoke + contract claims test |
| `xrtm start --limit/--model/--base-url/--runs-dir` | Bounded overrides | `released` | same as above | `xrtm` docs | contract claims test |
| `xrtm start --provider mock` (hidden) | Zero-cost pipeline smoke | `released` | `xrtm.product.providers.build_provider` | `xrtm` docs | CI mock smoke |
| `xrtm runs show [RUN_ID] [--latest] [--runs-dir]` | Inspect a run's summary and artifacts | `released` | `xrtm.product.history.run_detail` | `xrtm` docs | contract claims test |

### Library-only services (no CLI claim)

These are importable from the Python API and covered by unit tests, but the
current release does **not** claim a CLI or WebUI surface for them:

- `xrtm.product.history.list_runs` / `compare_runs` / `export_run`
- `xrtm.product.reports.render_html_report`
- `xrtm.e2e.real_questions.run_real_question_e2e`
- `xrtm.product.pipeline.run_pipeline` options beyond `xrtm start`

They may be claimed by Python-API docs only, with no CLI-parity language.

## Withdrawn lanes (must not appear in release docs)

| Lane | Historical commands/routes | Status |
| --- | --- | --- |
| WebUI shell | `xrtm web`, `/`, `/hub`, `/start`, `/workbench`, `/studio`, `/playground`, `/observatory`, `/runs/*` API routes | `withdrawn` |
| Workflow authoring | `xrtm workflow create/validate/explain/run/list/show` | `withdrawn` |
| Playground sandbox | `xrtm playground`, `/playground` APIs | `withdrawn` |
| Profiles | `xrtm profile starter/create/list/show`, `xrtm run profile` | `withdrawn` |
| Monitors | `xrtm monitor start/list/show/run-once/pause/resume/halt/daemon` | `withdrawn` |
| Artifacts/report | `xrtm artifacts inspect/cleanup`, `xrtm report html` | `withdrawn` |
| Run history extras | `xrtm runs list/search/compare/export` | `withdrawn` (library-only services remain) |
| Validation/benchmark/perf/competition | `xrtm validate *`, `xrtm benchmark *`, `xrtm perf *`, `xrtm competition *` | `withdrawn` |
| TUI | `xrtm tui` | `withdrawn` |
| Provider extras | `xrtm providers doctor`, `xrtm local-llm status` | `withdrawn` |

## Released parity proof

The `0.10.6` release proof covers:

1. fresh install on Python 3.11 and 3.12 (`pip install xrtm==0.10.6`)
2. `xrtm doctor` reports a usable environment
3. `xrtm start --provider mock --limit 2` completes with a scored run
   directory
4. `xrtm start` against an OpenAI-compatible endpoint completes
5. `xrtm runs show --latest` renders the run summary and artifact index
6. every command in `docs/release-command-contract.json` resolves in the
   shipped command tree (enforced by `tests/test_review_lows.py`)

Future-release lanes re-enter this matrix only when the package, docs, and
gates graduate together; until then they stay `withdrawn` or `future-release`.
