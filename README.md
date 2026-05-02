# xRtm: local-first forecasting and model-eval workbench

[![PyPI](https://img.shields.io/pypi/v/xrtm?style=flat-square)](https://pypi.org/project/xrtm/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue?style=flat-square)](LICENSE)

**xRtm** is a local-first forecasting and model-eval workbench.

It helps researchers and evaluation teams run forecasting workflows on their own machine, inspect every run artifact, and compare results without depending on hosted APIs for the default path.

**Start here:** run `xrtm start`, inspect the generated run, browse the results in the WebUI or TUI, then pick the guide that matches your job.

## What you can prove in a few minutes

- Run a complete forecasting workflow locally with `--provider mock`
- Score the run and write reproducible artifacts under `runs/`
- Inspect outputs with CLI commands and an HTML report
- Browse the same run in the WebUI or TUI
- Move to starter profiles, team workflows, or optional local-LLM setups later

## Quick proof: local demo -> artifacts -> browser

### 1. Install

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install xrtm==0.3.0
```

Supported Python versions are `>=3.11,<3.13`.

### 2. Run the guided first command

```bash
xrtm start
```

`xrtm start` checks readiness, runs the deterministic mock-provider demo, confirms the core artifacts, and prints exact next commands. This default path is provider-free: no API keys, no cloud dependency, and no local model server required.

### 3. Inspect the run you just created

```bash
xrtm runs show latest --runs-dir runs
xrtm artifacts inspect --latest --runs-dir runs
xrtm report html --latest --runs-dir runs
```

The generated report is written to `runs/<run-id>/report.html`.
`xrtm artifacts inspect` lists the canonical files and their on-disk locations so you can confirm exactly what the first run produced.

### 4. Browse results visually

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
  monitor.json
  report.html
  logs/
```

These files are the proof surface for the product: the CLI, TUI, WebUI, and exports all work from the same run artifacts.

- `eval.json` records scoring outputs such as Brier metrics
- `events.jsonl` is the versioned event stream (`xrtm.events.v1`)
- `run_summary.json` is the compact summary contract used by higher-level views

## Official proof-point workflows

The official XRTM story is intentionally small. After `xrtm start`, keep returning to these four workflows:

### 1. Provider-free first success

```bash
xrtm start
xrtm runs show latest --runs-dir runs
xrtm artifacts inspect --latest --runs-dir runs
xrtm report html --latest --runs-dir runs
xrtm web --runs-dir runs
```

This is the canonical first proof: a full local forecasting run, scored artifacts on disk, and a browser/TUI view over the same evidence.

### 2. Benchmark and validation workflow

```bash
xrtm perf run --scenario provider-free-smoke --iterations 3 --limit 1 --runs-dir runs-perf --output performance.json
xrtm validate run --provider mock --limit 10 --iterations 2 --runs-dir runs-validation
```

Use this workflow when you need deterministic benchmark evidence and a larger corpus-backed validation pass without introducing provider noise.

### 3. Monitoring, history, and report workflow

```bash
xrtm profile starter my-local --runs-dir runs
xrtm run profile my-local
xrtm monitor start --provider mock --limit 2 --runs-dir runs
xrtm runs compare <run-id-a> <run-id-b> --runs-dir runs
xrtm runs export latest --runs-dir runs --output latest-run.json
```

This is the official operator loop for repeatable local runs, monitor state, history review, and portable report/export evidence.

### 4. Local-LLM advanced workflow

```bash
export XRTM_LOCAL_LLM_BASE_URL=http://localhost:8080/v1
xrtm local-llm status
xrtm demo --provider local-llm --limit 1 --max-tokens 768 --runs-dir runs-local
```

Only use this path after the provider-free workflow is already healthy.

## Minimal starter scaffold after your first run

When you want a reusable local workflow without inventing structure, create the starter profile:

```bash
xrtm profile starter my-local --runs-dir runs
xrtm run profile my-local
```

This creates `.xrtm/profiles/my-local.json`, keeps the workflow on the honest mock-provider path, and reuses your local `runs/` directory.

## Choose your next path

- **Researcher / model-eval user first**: read the [Getting Started Guide](docs/getting-started.md) for the full first-success flow and the benchmark/validation workflow.
- **Operator**: use the [Operator Runbook](docs/operator-runbook.md) for the monitoring/history/report workflow, repeatable profiles, and troubleshooting.
- **Team**: read [Team Workflows](docs/team-workflows.md) for honest current-team patterns built from profiles, exports, and conventions.
- **Developer / integrator**: use the [Python API Reference](docs/python-api-reference.md) and the clearly-labeled [integration examples](examples/integration/) for programmatic usage.

## Optional: local LLMs come later

If you want real local-model inference, xRtm also supports `--provider local-llm` against a local OpenAI-compatible endpoint. Treat that as a secondary path after your first provider-free run; setup takes more time and hardware. Start from the advanced section in [docs/getting-started.md](docs/getting-started.md) and the [Operator Runbook](docs/operator-runbook.md).

## Packages in the ecosystem

The top-level `xrtm` package is the product-facing workbench. It installs and coordinates these underlying packages:

| Package | Badge | Role |
| :--- | :--- | :--- |
| **xrtm-forecast** | [![PyPI](https://img.shields.io/pypi/v/xrtm-forecast?style=flat-square)](https://pypi.org/project/xrtm-forecast/) | Forecast generation and inference orchestration |
| **xrtm-data** | [![PyPI](https://img.shields.io/pypi/v/xrtm-data?style=flat-square)](https://pypi.org/project/xrtm-data/) | Data access and bundled corpus/snapshot support |
| **xrtm-eval** | [![PyPI](https://img.shields.io/pypi/v/xrtm-eval?style=flat-square)](https://pypi.org/project/xrtm-eval/) | Evaluation metrics, scoring, and calibration tooling |
| **xrtm-train** | [![PyPI](https://img.shields.io/pypi/v/xrtm-train?style=flat-square)](https://pypi.org/project/xrtm-train/) | Training and optimization pipeline components |

Maintainers should use the governance repo's [Cross-Repository Compatibility and Coordination Policy](https://github.com/xrtm-org/governance/blob/main/policies/cross-repo-compatibility-policy.md) and [Release Train Playbook](https://github.com/xrtm-org/governance/blob/main/policies/release-train-playbook.md) for coordinated changes across `data`, `forecast`, `xrtm`, and `xrtm.org`. `xrtm` should validate against explicit released or candidate upstream refs, not same-name sibling branches or hidden branch aliases. Default `push`/`pull_request` CI uses explicit `main` upstream refs; use `workflow_dispatch` to pin exact upstream refs for coordinated validation.

## Documentation

- [Getting Started Guide](docs/getting-started.md)
- [Operator Runbook](docs/operator-runbook.md)
- [Team Workflows](docs/team-workflows.md)
- [Python API Reference](docs/python-api-reference.md)
- [Integration Examples](examples/integration/)
- Full documentation: [xrtm.org](https://xrtm.org)

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
