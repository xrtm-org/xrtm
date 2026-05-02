# Getting Started with XRTM

XRTM is AI for event forecasting. This guide is the shortest honest path to
first success.

You will run a complete local demo, inspect the generated artifacts, and browse
the results. The default path uses the built-in mock provider, so you do **not**
need API keys or a local model server.

## 1. Install

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install xrtm==0.3.0
```

**Supported Python versions:** `>=3.11,<3.13`

## 2. Run the guided first command

```bash
xrtm start
```

`xrtm start` verifies readiness, runs the deterministic mock-provider demo, confirms the key artifacts, and prints exact next commands.

On success, the final quickstart output explicitly shows:
- what just succeeded
- the run id
- the artifact location
- the report location
- exact latest-run follow-up commands

Treat that final panel as proof that XRTM completed a full local run and wrote the canonical evidence to disk.

This provider-free first run:
- loads bundled questions locally
- generates deterministic forecasts without API calls
- evaluates the run with built-in scoring
- writes a complete run directory under `runs/`

## 3. Inspect the run artifacts

```bash
xrtm runs show latest --runs-dir runs
xrtm artifacts inspect --latest --runs-dir runs
xrtm report html --latest --runs-dir runs
```

`xrtm artifacts inspect` prints the canonical artifact inventory with on-disk locations, so you can verify exactly what the first run wrote.

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

## 4. Browse the results

Launch the local WebUI:

```bash
xrtm web --runs-dir runs
```

Open `http://127.0.0.1:8765` in your browser.

If you prefer the terminal, launch the TUI instead:

```bash
xrtm tui --runs-dir runs
```

## 5. What you just proved

You completed the first XRTM event-forecasting loop:

1. **Forecast run**: ran a forecasting workflow without external providers
2. **Scored evidence**: verified the run and its outputs on disk
3. **Review surface**: opened the same run through WebUI or TUI

That is the core product path for newcomers.

## Official proof-point workflows

After the first run, these four workflows expand the same event-forecasting
loop:

### 1. Provider-free first success

```bash
xrtm start
xrtm runs show latest --runs-dir runs
xrtm artifacts inspect --latest --runs-dir runs
xrtm report html --latest --runs-dir runs
xrtm web --runs-dir runs
```

### 2. Benchmark and validation workflow

```bash
xrtm perf run --scenario provider-free-smoke --iterations 3 --limit 1 --runs-dir runs-perf --output performance.json
xrtm validate run --provider mock --limit 10 --iterations 2 --runs-dir runs-validation
```

Use this workflow when you want deterministic benchmark evidence first, then a larger provider-free validation sweep.

### 3. Monitoring, history, and report workflow

```bash
xrtm profile starter my-local --runs-dir runs
xrtm run profile my-local
xrtm monitor start --provider mock --limit 2 --runs-dir runs
xrtm runs compare <run-id-a> <run-id-b> --runs-dir runs
xrtm runs export latest --runs-dir runs --output latest-run.json
```

### 4. Local-LLM advanced workflow

```bash
export XRTM_LOCAL_LLM_BASE_URL=http://localhost:8080/v1
xrtm local-llm status
xrtm demo --provider local-llm --limit 1 --max-tokens 768 --runs-dir runs-local
```

Only switch to local-LLM mode after the provider-free path above is working.

## Good next steps

### Run a slightly larger local pass

```bash
xrtm demo --provider mock --limit 10
```

### Scaffold a reusable local profile

```bash
xrtm profile starter my-local --runs-dir runs
xrtm run profile my-local
```

This starter scaffold creates `.xrtm/profiles/my-local.json`, ensures the local `runs/` workspace exists, and keeps the workflow on the same mock-provider path you just proved with `xrtm start`.

### Pick the guide that matches your role

- **Researcher / model-eval**: stay on the provider-free path and use the [Operator Runbook](operator-runbook.md) for the benchmark/validation workflow and comparisons.
- **Operator**: continue with the [Operator Runbook](operator-runbook.md) for the monitoring/history/report workflow, profiles, performance, exports, and troubleshooting.
- **Team**: read [Team Workflows](team-workflows.md) for realistic multi-user patterns and current limitations.
- **Developer / integrator**: use the [Python API Reference](python-api-reference.md) and the [integration examples](../examples/integration/), which are organized by user job and clearly separate custom patterns from shipped product workflows.

## Advanced and optional: local LLM mode

Only switch to `--provider local-llm` after the provider-free path above is working.

Use local-LLM mode when you specifically need to evaluate a real local model and you already have a local OpenAI-compatible endpoint available.

Typical prerequisites:
- a running local inference server such as llama.cpp, Ollama, or LocalAI
- downloaded model weights
- enough CPU/GPU resources for the model you chose
- willingness to trade the 5-minute quick start for a slower, more complex setup

Minimal verification flow:

```bash
export XRTM_LOCAL_LLM_BASE_URL=http://localhost:8080/v1
xrtm local-llm status
xrtm demo --provider local-llm --limit 1 --max-tokens 768
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

Check the warning text first. Optional components may be missing even when the default local demo path is fine.

### Local-LLM health check fails

Go back to the provider-free path, confirm the main install works, then use the [Operator Runbook](operator-runbook.md) to debug your local endpoint.
