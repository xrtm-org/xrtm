# XRTM Operator Runbook

This runbook covers the supported operating path for the published top-level
`xrtm` product shell once the first provider-free demo from
`getting-started.md` is already working.

For merge, cross-repo coordination, and release publication gates, see the
governance repo's PR acceptance policy, cross-repo compatibility policy, and
release readiness policy:

- `../../governance/policies/pr-acceptance-policy.md`
- `../../governance/policies/cross-repo-compatibility-policy.md`
- `../../governance/policies/release-readiness-policy.md`

**For multi-user and institutional team workflows**, see `team-workflows.md`.

## Release-gated top-level surface

This runbook is validated against `docs/release-command-contract.json` by
`scripts/check_release_claims.py`. Corpus-validation flows and user-attribution
flags remain intentionally unreleased, but guided start helpers, latest-run
aliases, and CSV export are now part of the published surface.

Maintainer note: when this page graduates new published behavior, release
readiness also requires provider-free clean-room acceptance from release
artifacts. Local-LLM-related promotions additionally need local-LLM clean-room
evidence when the change touches local-model execution and compatible runner
infrastructure is available.

## Supported environment

Use Python `>=3.11,<3.13`.

Python 3.13 is not currently supported because the full dependency stack has
not been validated there. The published packages intentionally reject
unsupported Python versions.

## Install

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install xrtm==0.3.1
```

Verify the installed stack:

```bash
xrtm --version
xrtm-data --version
forecast --version
xrtm-forecast --version
xrtm-train --version
xrtm doctor
```

## Official proof-point set

After the first proof from `getting-started.md`, XRTM expands through four
published workflows:

1. **Provider-free first success** via `xrtm start`
2. **Benchmark and performance workflow** via `xrtm perf run`
3. **Monitoring, history, and export workflow** via profiles, monitor commands, compare/export, and HTML reports
4. **Local-LLM advanced workflow** via `xrtm local-llm status` and the bounded local-LLM demo command

This runbook primarily sharpens workflows 2-4.

## Workflow profiles

Profiles save repeatable local workflow settings so you do not have to retype
provider, corpus limit, token budget, model, and run directory options.

```bash
xrtm profile create local-mock --provider mock --limit 2 --runs-dir runs
xrtm profile list
xrtm profile show local-mock
xrtm run profile local-mock
```

Profiles are stored under `.xrtm/profiles` by default. Use `--profiles-dir`
when you want project-specific or test-specific profile storage.

## Provider-free smoke

Use provider-free mode for deterministic validation and CI-safe smoke tests:

```bash
xrtm start --runs-dir runs
xrtm web --runs-dir runs --smoke
```

Provider-free mode does not call hosted APIs.

## Canonical artifacts

Each run writes a directory like:

```text
runs/<run-id>/
  run.json
  questions.jsonl
  forecasts.jsonl
  eval.json
  train.json
  provider.json
  events.jsonl
  run_summary.json
  report.html
  logs/
```

`events.jsonl` uses the `xrtm.events.v1` schema. `run_summary.json` uses the
`xrtm.run-summary.v1` schema for pipeline runs. `monitor.json` is optional
monitor state: real monitor runs populate watches and thresholds, while some
profile-driven runs may carry an idle placeholder entry. Use `xrtm monitor
list` status and watch counts to distinguish actual monitors from ordinary
runs.

Inspect and report:

```bash
xrtm runs list --runs-dir runs
xrtm runs show latest --runs-dir runs
xrtm artifacts inspect --latest --runs-dir runs
xrtm report html --latest --runs-dir runs
```

`xrtm artifacts inspect` prints the canonical artifact inventory with
present/missing status and on-disk locations, which is useful for first-run
review and troubleshooting.

## Monitoring, history, and report workflow

Create and update a monitor:

```bash
xrtm monitor start --provider mock --limit 2 --runs-dir runs
xrtm monitor list --runs-dir runs
xrtm runs compare <run-id-a> <run-id-b> --runs-dir runs
xrtm runs export latest --runs-dir runs --output export.json
xrtm runs export latest --runs-dir runs --output export.csv --format csv
xrtm artifacts cleanup --runs-dir runs --keep 50
```

Treat this monitor/history/report loop as one proof point: the same local run
evidence powers review, export, and operational monitoring.

Use it as an operator decision gate:

- repeated mock runs are your stable control and should usually compare as unchanged
- unchanged compare output means the baseline is trustworthy, not that XRTM secretly improved
- only promote a candidate workflow after a meaningful change lowers Brier/ECE without introducing warnings/errors or an unacceptable runtime/tokens cost
- export the winning run when you want downstream spreadsheet or notebook review

## TUI and WebUI

Terminal cockpit:

```bash
xrtm tui --runs-dir runs
```

Local WebUI:

```bash
xrtm web --runs-dir runs
```

The WebUI and `/api/runs` endpoint support simple filtering with `status`,
`provider`, and `q` query parameters.

## Performance checks

Use the deterministic provider-free performance harness for CI-safe local
regression checks:

```bash
xrtm perf run --scenario provider-free-smoke --iterations 3 --limit 1 --runs-dir runs-perf --output performance.json
```

The report uses the `xrtm.performance.v1` schema and includes per-iteration
run ids, durations, forecast counts, Brier scores, and budget status.

That makes the performance harness the honest default baseline for later
experiments. Stronger "improved over time" claims belong to deeper paths where
you actually change provider/model/runtime behavior, such as local-LLM or the
calibration/replay tooling in the wider package stack.

## Optional later: local-LLM mode

⚠️ **Prerequisites**: Run this workflow only after completing local-LLM server
setup and health verification.

```bash
export XRTM_LOCAL_LLM_BASE_URL=http://localhost:8080/v1
xrtm local-llm status
xrtm demo --provider local-llm --limit 1 --max-tokens 768 --runs-dir runs-local
```

## Still intentionally unreleased

Corpus-aware validation flows and user attribution remain off the released
surface until their semantics and release evidence are stronger.

## Troubleshooting

- `xrtm` install fails on Python 3.13: use Python 3.11 or 3.12.
- `xrtm local-llm status` fails: treat it as a local endpoint/server issue first, then retry the local-LLM flow.
- `xrtm artifacts inspect` fails on a directory: confirm it is a canonical XRTM run with `run.json` present.
