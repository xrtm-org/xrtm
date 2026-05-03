# XRTM: AI for event forecasting

[![PyPI](https://img.shields.io/pypi/v/xrtm?style=flat-square)](https://pypi.org/project/xrtm/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue?style=flat-square)](LICENSE)

**XRTM** is AI for event forecasting.

AI can already generate plausible answers. The bigger opportunity is
forecasting real-world events, keeping score, and learning which changes
actually help. XRTM gives you a product path for that: run a forecasting
workflow, inspect the artifacts, review the scores, compare runs, and only
claim improvement when a meaningful change earns it.

**Start here:** run `xrtm doctor`, then `xrtm demo --provider mock --limit 1 --runs-dir runs`, inspect the generated run, and browse it in the WebUI or TUI.

Top-level command blocks in this README, `docs/getting-started.md`, and
`docs/operator-runbook.md` are release-gated to the published package surface
recorded in `docs/release-command-contract.json`. Branch-only CLI additions stay
out of these pages until the matching coordinated release updates that contract
and the released-stack smoke.

## Choose the package boundary quickly

- Start with **`xrtm`** when you want the product-first, provider-free, released workflow: CLI, canonical run artifacts, WebUI/TUI, and the quickest honest first success.
- Start with **`xrtm-forecast`** when you are embedding forecasting directly in code, building a service, or composing custom orchestration around the runtime APIs.
- If you need both, prove the run once with `xrtm`, then move into the [integration examples](examples/integration/) and [Python API Reference](docs/python-api-reference.md).

## What you can prove in a few minutes

- Verify the published package health with `xrtm doctor`
- Run your first provider-free event-forecasting loop with `xrtm demo --provider mock --limit 1 --runs-dir runs`
- Inspect the canonical run directory with `xrtm runs list`, `xrtm runs show <run-id> --runs-dir runs`, `xrtm artifacts inspect runs/<run-id>`, and `xrtm report html runs/<run-id>`
- Browse the same evidence in the WebUI or TUI
- Expand into benchmarking, monitoring, history, JSON export, or optional local-LLM setups later

## Quick proof: install -> provider-free demo -> inspect -> browser

### 1. Install

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install xrtm==0.3.0
```

Supported Python versions are `>=3.11,<3.13`.

### 2. Verify package health

```bash
xrtm doctor
```

`xrtm doctor` is the released package-health check: it verifies imports and reports the installed stack versions before you run a workflow.

### 3. Run the published provider-free demo

```bash
xrtm demo --provider mock --limit 1 --runs-dir runs
```

This default path is provider-free: no API keys, no cloud dependency, and no local model server required.

### 4. Inspect the run you just created

```bash
xrtm runs list --runs-dir runs
xrtm runs show <run-id> --runs-dir runs
xrtm artifacts inspect runs/<run-id>
xrtm report html runs/<run-id>
```

Use the run id from `xrtm runs list --runs-dir runs`. The regenerated report is written to `runs/<run-id>/report.html`.

### 5. Browse results visually

```bash
xrtm web --runs-dir runs
xrtm tui --runs-dir runs
```

- WebUI: open `http://127.0.0.1:8765`
- TUI: browse runs and summaries in the terminal

## What a run contains

A successful run writes a canonical directory under `runs/<run-id>/`:

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

These files are the proof surface for the product: the CLI, TUI, WebUI, and exports all work from the same run artifacts.

- `eval.json` records scoring outputs such as Brier metrics
- `events.jsonl` is the versioned event stream (`xrtm.events.v1`)
- `run_summary.json` is the compact summary contract used by higher-level views
- `monitor.json` appears only for real monitor runs created with `xrtm monitor start`

## Official proof-point workflows

The story is simple: XRTM is AI for event forecasting. These release-gated
workflows are the published proof behind that claim today:

### 1. Provider-free first success

```bash
xrtm doctor
xrtm demo --provider mock --limit 1 --runs-dir runs
xrtm runs list --runs-dir runs
xrtm runs show <run-id> --runs-dir runs
xrtm artifacts inspect runs/<run-id>
xrtm report html runs/<run-id>
xrtm web --runs-dir runs
```

### 2. Benchmark and performance workflow

```bash
xrtm perf run --scenario provider-free-smoke --iterations 3 --limit 1 --runs-dir runs-perf --output performance.json
xrtm web --runs-dir runs --smoke
```

Read `performance.json` as your reproducible baseline artifact:

- mean and p95 runtime tell you whether the workflow stays within budget
- the paired `runs-perf/<run-id>/run_summary.json` carries the same scored Brier/ECE surface used by compare/export
- repeated provider-free runs should stay stable enough to act as a control before you try a different provider or model

### 3. Monitoring, history, and export workflow

```bash
xrtm profile create local-mock --provider mock --limit 2 --runs-dir runs
xrtm run profile local-mock
xrtm monitor start --provider mock --limit 2 --runs-dir runs
xrtm runs compare <run-id-a> <run-id-b> --runs-dir runs
xrtm runs export <run-id> --runs-dir runs --output export.json
```

This is the released compare/learn loop:

- first use repeated mock runs as a stable control and to learn how the compare surface reads
- if two provider-free runs are unchanged, treat that as evidence that the baseline is deterministic by design, not as product stagnation
- only call something an improvement after a meaningful provider, model, or prompt/runtime change lowers Brier/ECE without adding warnings/errors or unacceptable runtime/tokens
- export the winning run when you want notebook or spreadsheet follow-up

### 4. Local-LLM advanced workflow

```bash
export XRTM_LOCAL_LLM_BASE_URL=http://localhost:8080/v1
xrtm local-llm status
xrtm demo --provider local-llm --limit 1 --max-tokens 768 --runs-dir runs-local
```

## What belongs in the default path vs deeper paths

- **Default released path:** provider-free first success, deterministic benchmark evidence, compare/export literacy, WebUI/TUI review, and explicit artifact inspection.
- **What it honestly proves:** you can create a scored baseline, compare runs, and decide whether a later change helped.
- **What it does not prove by itself:** visible forecast-quality improvement from repeated mock runs. The mock provider is deterministic, so repeated runs are supposed to stay stable.
- **Deeper paths:** local-LLM evaluation plus the replay/calibration work in `xrtm-forecast` and `xrtm-train` are where stronger improvement claims belong once you are intentionally changing the system.

Commands that are still on the next coordinated release train—new guided-start shortcuts, corpus-validation flows, latest-run aliases, CSV export, and user-attribution flags—intentionally stay out of these top-level docs until the release contract moves forward.

## Minimal reusable profile after your first run

When you want a reusable local workflow without inventing structure, create a
profile explicitly:

```bash
xrtm profile create my-local --provider mock --limit 2 --runs-dir runs
xrtm run profile my-local
```

This creates `.xrtm/profiles/my-local.json`, keeps the workflow on the honest mock-provider path, and reuses your local `runs/` directory.

## Choose your next path

- **Researcher / model-eval**: finish the [Getting Started Guide](docs/getting-started.md), then use the dedicated researcher workflow on [xrtm.org](https://xrtm.org/docs/workflows/researcher-model-eval) for benchmark interpretation, compare/export review, and the released quality loop.
- **Operator**: use the [Operator Runbook](docs/operator-runbook.md) for profiles, monitoring, history review, JSON exports, and troubleshooting.
- **Team**: read [Team Workflows](docs/team-workflows.md) for honest current-team patterns built from profiles, exports, and conventions.
- **Developer / integrator**: start with `xrtm` if you still need the released provider-free proof path; switch to the [Python API Reference](docs/python-api-reference.md) and [integration examples](examples/integration/) once you are embedding forecasting directly in code.

## Optional later: local LLMs

If you want real local-model inference, XRTM also supports `--provider local-llm` against a local OpenAI-compatible endpoint. Treat that as a secondary path after your first provider-free run; setup takes more time and hardware. Start from the advanced section in [docs/getting-started.md](docs/getting-started.md) and the [Operator Runbook](docs/operator-runbook.md).

## Packages in the ecosystem

The top-level `xrtm` package is the product shell for the event-forecasting
system. It installs and coordinates these underlying packages:

| Package | Badge | Role |
| :--- | :--- | :--- |
| **xrtm-forecast** | [![PyPI](https://img.shields.io/pypi/v/xrtm-forecast?style=flat-square)](https://pypi.org/project/xrtm-forecast/) | Forecast generation and inference orchestration |
| **xrtm-data** | [![PyPI](https://img.shields.io/pypi/v/xrtm-data?style=flat-square)](https://pypi.org/project/xrtm-data/) | Data access and bundled corpus/snapshot support |
| **xrtm-eval** | [![PyPI](https://img.shields.io/pypi/v/xrtm-eval?style=flat-square)](https://pypi.org/project/xrtm-eval/) | Evaluation metrics, scoring, and calibration tooling |
| **xrtm-train** | [![PyPI](https://img.shields.io/pypi/v/xrtm-train?style=flat-square)](https://pypi.org/project/xrtm-train/) | Training and optimization pipeline components |

Maintainers should use the governance repo's [Cross-Repository Compatibility and Coordination Policy](https://github.com/xrtm-org/governance/blob/main/policies/cross-repo-compatibility-policy.md) and [Release Readiness Policy](https://github.com/xrtm-org/governance/blob/main/policies/release-readiness-policy.md) for coordinated changes across `data`, `forecast`, `xrtm`, and `xrtm.org`. The release-gated command contract lives in `docs/release-command-contract.json`; update it only after the matching published package release exists and the released-stack smoke has passed against that version.

## Documentation

- [Getting Started Guide](docs/getting-started.md)
- [Operator Runbook](docs/operator-runbook.md)
- [Team Workflows](docs/team-workflows.md)
- [Python API Reference](docs/python-api-reference.md)
- [Integration Examples](examples/integration/)
- Full documentation: [xrtm.org](https://xrtm.org)

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
