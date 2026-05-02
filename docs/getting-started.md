# Getting Started with XRTM

XRTM is AI for event forecasting. This guide is the shortest honest path to
first success on the published package surface.

You will verify package health, run a complete local demo, inspect the
generated artifacts, and browse the results. The default path uses the built-in
mock provider, so you do **not** need API keys or a local model server.

> Release-gated command note: the command blocks in this guide are validated
> against `docs/release-command-contract.json` so top-level docs cannot drift
> ahead of the latest published `xrtm` package surface.

## 1. Install

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install xrtm==0.3.0
```

**Supported Python versions:** `>=3.11,<3.13`

## 2. Verify package health

```bash
xrtm doctor
```

`xrtm doctor` is the released health check. Use it to confirm imports and the
installed package versions before you run a workflow.

## 3. Run the published provider-free demo

```bash
xrtm demo --provider mock --limit 1 --runs-dir runs
```

This provider-free first run:

- loads bundled questions locally
- generates deterministic forecasts without API calls
- evaluates the run with built-in scoring
- writes a complete run directory under `runs/`

## 4. Inspect the run artifacts

```bash
xrtm runs list --runs-dir runs
xrtm runs show <run-id> --runs-dir runs
xrtm artifacts inspect runs/<run-id>
xrtm report html runs/<run-id>
```

Replace `<run-id>` with the id from `xrtm runs list --runs-dir runs`.
`xrtm artifacts inspect` prints the canonical artifact inventory with on-disk
locations, and `xrtm report html runs/<run-id>` regenerates
`runs/<run-id>/report.html`.

The run directory contains the same evidence used by higher-level views:

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

## 5. Browse the results

Launch the local WebUI:

```bash
xrtm web --runs-dir runs
```

Open `http://127.0.0.1:8765` in your browser.

If you prefer the terminal, launch the TUI instead:

```bash
xrtm tui --runs-dir runs
```

## 6. What you just proved

You completed the first published XRTM event-forecasting loop:

1. **Health check**: verified the installed stack with `xrtm doctor`
2. **Forecast run**: ran a provider-free forecasting workflow without external providers
3. **Scored evidence**: verified the run and its outputs on disk
4. **Review surface**: opened the same run through WebUI or TUI

That is the core product path for newcomers today.

## Official proof-point workflows

After the first run, these release-gated workflows expand the same
event-forecasting loop:

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

Use this workflow when you want deterministic benchmark evidence and a quick
WebUI route smoke without introducing provider noise.

Treat it as the released evaluation baseline:

- `performance.json` captures repeatable runtime evidence
- the paired `runs-perf/<run-id>/run_summary.json` carries scored run metrics such as Brier and ECE
- on the provider-free path, repeated runs should stay stable enough to act as a control before you change provider/model settings

### 3. Monitoring, history, and export workflow

```bash
xrtm profile create my-local --provider mock --limit 2 --runs-dir runs
xrtm run profile my-local
xrtm monitor start --provider mock --limit 2 --runs-dir runs
xrtm runs compare <run-id-a> <run-id-b> --runs-dir runs
xrtm runs export <run-id> --runs-dir runs --output export.json
```

When you compare two runs, read the output like an evaluation gate:

- **Brier / ECE:** lower is better
- **warnings / errors:** should stay at zero
- **duration / tokens:** efficiency cost of a change
- use compare only after the two runs are meant to answer the same question set

### 4. Local-LLM advanced workflow

```bash
export XRTM_LOCAL_LLM_BASE_URL=http://localhost:8080/v1
xrtm local-llm status
xrtm demo --provider local-llm --limit 1 --max-tokens 768 --runs-dir runs-local
```

Only switch to local-LLM mode after the provider-free path above is working.

Commands that are still on the next coordinated release train—new guided-start shortcuts, corpus-validation flows, latest-run aliases, CSV export, and user-attribution flags—stay off this guide until the release contract moves forward.

## Good next steps

### Run a slightly larger local pass

```bash
xrtm demo --provider mock --limit 10 --runs-dir runs
```

### Create a reusable local profile

```bash
xrtm profile create my-local --provider mock --limit 2 --runs-dir runs
xrtm profile show my-local
xrtm run profile my-local
```

This writes `.xrtm/profiles/my-local.json` and keeps the workflow on the same
mock-provider path you just proved.

### Pick the guide that matches your role

- **Researcher / model-eval**: stay on the provider-free path, then use the dedicated workflow on [xrtm.org](https://xrtm.org/docs/workflows/researcher-model-eval) for benchmark interpretation, compare/export review, and the released quality loop.
- **Operator**: continue with the [Operator Runbook](operator-runbook.md) for monitoring, profiles, performance checks, exports, and troubleshooting.
- **Team**: read [Team Workflows](team-workflows.md) for realistic multi-user patterns and current limitations.
- **Developer / integrator**: use the [Python API Reference](python-api-reference.md) and the [integration examples](../examples/integration/), which are organized by user job and clearly separate custom patterns from shipped product workflows.

## Advanced and optional: local LLM mode

Only switch to `--provider local-llm` after the provider-free path above is
working.

Use local-LLM mode when you specifically need to evaluate a real local model
and you already have a local OpenAI-compatible endpoint available.

Typical prerequisites:
- a running local inference server such as llama.cpp, Ollama, or LocalAI
- downloaded model weights
- enough CPU/GPU resources for the model you chose
- willingness to trade the quick start for a slower, more complex setup

Minimal verification flow:

```bash
export XRTM_LOCAL_LLM_BASE_URL=http://localhost:8080/v1
xrtm local-llm status
xrtm demo --provider local-llm --limit 1 --max-tokens 768 --runs-dir runs-local
```

For deeper setup and troubleshooting, use the [Operator Runbook](operator-runbook.md).

## Quick troubleshooting

### `xrtm: command not found`

Activate the virtual environment first:

```bash
. .venv/bin/activate
```

### Installation fails on Python 3.13

This is expected. XRTM currently supports Python `>=3.11,<3.13`.

### `xrtm doctor` shows warnings

Check the warning text first. Optional components may be missing even when the
default provider-free demo path is fine.

### Local-LLM health check fails

Go back to the provider-free path, confirm the main install works, then use
the [Operator Runbook](operator-runbook.md) to debug your local endpoint.
