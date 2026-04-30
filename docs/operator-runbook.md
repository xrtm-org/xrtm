# XRTM Operator Runbook

This runbook covers the supported local-first operating path for the top-level `xrtm` product shell.

## Supported environment

Use Python `>=3.11,<3.13`.

Python 3.13 is not currently supported because the full dependency stack has not been validated there. The published packages intentionally reject unsupported Python versions.

## Install

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install xrtm==0.2.1
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

## Provider-free smoke

Use provider-free mode for deterministic validation and CI-safe smoke tests:

```bash
xrtm demo --provider mock --limit 2 --runs-dir runs
xrtm web --runs-dir runs --smoke
```

Provider-free mode does not call hosted APIs.

## Local LLM smoke

Run local LLM mode only when an OpenAI-compatible endpoint is available, such as llama.cpp:

```bash
export XRTM_LOCAL_LLM_BASE_URL=http://localhost:8080/v1
xrtm local-llm status
xrtm demo --provider local-llm --limit 1 --max-tokens 768 --runs-dir runs-local
```

If `xrtm local-llm status` reports the endpoint as unavailable, start or fix the local model server before running the demo.

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
  monitor.json
  report.html
  logs/
```

Inspect and report:

```bash
xrtm artifacts inspect runs/<run-id>
xrtm report html runs/<run-id>
```

## Monitor lifecycle

Create and update a monitor:

```bash
xrtm monitor start --provider mock --limit 2 --runs-dir runs
xrtm monitor list --runs-dir runs
xrtm monitor show runs/<run-id>
xrtm monitor run-once runs/<run-id>
xrtm monitor pause runs/<run-id>
xrtm monitor resume runs/<run-id>
xrtm monitor halt runs/<run-id>
```

Current monitoring is artifact-backed and local. A future monitor daemon will add scheduling, thresholds, alerting, and retention policy.

## TUI and WebUI

Terminal cockpit:

```bash
xrtm tui --runs-dir runs
```

Local WebUI:

```bash
xrtm web --runs-dir runs
```

Smoke mode for automation:

```bash
xrtm web --runs-dir runs --smoke
```

## Troubleshooting

### `xrtm` does not install on Python 3.13

This is expected. Use Python 3.11 or 3.12.

### `xrtm local-llm status` is unavailable

Check that the local model server is running and that `XRTM_LOCAL_LLM_BASE_URL` points to its OpenAI-compatible `/v1` endpoint.

### A run directory cannot be inspected

`xrtm artifacts inspect` requires `run.json`. If it is missing, the directory is not a canonical XRTM run artifact.

### Provider-free smoke passes but local LLM smoke fails

Treat this as a local model/server issue unless the provider code changed. Verify endpoint health, context length, token budget, and GPU memory before debugging XRTM product code.

