# XRTM Operator Runbook

This runbook covers the supported local-first operating path for the top-level `xrtm` product shell.

## Supported environment

Use Python `>=3.11,<3.13`.

Python 3.13 is not currently supported because the full dependency stack has not been validated there. The published packages intentionally reject unsupported Python versions.

## Install

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install xrtm==0.3.0
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

## Workflow profiles

Profiles save repeatable local workflow settings so you do not have to retype provider, corpus limit, token budget, model, and run directory options.

```bash
xrtm profile create local-mock --provider mock --limit 2 --runs-dir runs
xrtm profile list
xrtm profile show local-mock
xrtm run profile local-mock
```

Profiles are stored under `.xrtm/profiles` by default. Use `--profiles-dir` when you want project-specific or test-specific profile storage.

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
  run_summary.json
  monitor.json
  report.html
  logs/
```

`events.jsonl` uses the `xrtm.events.v1` schema. Each event includes `schema_version`, `event_id`, `timestamp`, `event_type`, and event-specific fields. Current event types include:

- `run_started`
- `provider_request_started`
- `provider_request_completed`
- `forecast_written`
- `eval_completed`
- `train_completed`
- `monitor_status_changed`
- `warning`
- `error`

`run_summary.json` uses the `xrtm.run-summary.v1` schema for pipeline runs. It includes duration, provider latency when available, token counts, warning/error counts, forecast count, and eval/train summary metrics.

Inspect and report:

```bash
xrtm artifacts inspect runs/<run-id>
xrtm report html runs/<run-id>
```

Browse run history without reading JSON files directly:

```bash
xrtm runs list --runs-dir runs
xrtm runs search mock --runs-dir runs
xrtm runs show <run-id> --runs-dir runs
xrtm runs compare <run-id-a> <run-id-b> --runs-dir runs
xrtm runs export <run-id> --runs-dir runs --output export.json
```

`runs compare` focuses on operationally important summary fields such as status, provider, forecast count, duration, token totals, Brier scores, warnings, and errors. `runs export` writes one portable JSON bundle with run metadata, summary, events, forecasts, eval/train payloads, provider metadata, and monitor state when available.

Apply the local retention policy:

```bash
xrtm artifacts cleanup --runs-dir runs --keep 50
xrtm artifacts cleanup --runs-dir runs --keep 50 --delete
```

The command is dry-run by default. Use `--delete` only after checking the listed candidates.

## Monitor lifecycle

Create and update a monitor:

```bash
xrtm monitor start --provider mock --limit 2 --runs-dir runs
xrtm monitor list --runs-dir runs
xrtm monitor show runs/<run-id>
xrtm monitor run-once runs/<run-id>
xrtm monitor daemon runs/<run-id> --cycles 3 --interval-seconds 60
xrtm monitor pause runs/<run-id>
xrtm monitor resume runs/<run-id>
xrtm monitor halt runs/<run-id>
```

Monitoring is artifact-backed and local. `monitor.json` uses the `xrtm.monitor.v1` schema and supports lifecycle states:

- `created`
- `running`
- `paused`
- `degraded`
- `failed`
- `halted`

Thresholds are configured when a monitor is created:

```bash
xrtm monitor start --provider mock --limit 2 --probability-delta 0.10 --confidence-shift 0.20
```

If an update crosses a configured probability or confidence threshold, the monitor becomes `degraded`, watch-level warnings are persisted, and matching `warning` events are appended to `events.jsonl`.

## TUI and WebUI

Terminal cockpit:

```bash
xrtm tui --runs-dir runs
```

Local WebUI:

```bash
xrtm web --runs-dir runs
```

The WebUI and `/api/runs` endpoint support simple filtering with `status`, `provider`, and `q` query parameters, for example:

```text
http://127.0.0.1:8765/?provider=mock&q=202604
http://127.0.0.1:8765/api/runs?status=completed
```

## Performance and scale checks

Use the deterministic provider-free performance harness for CI-safe local regression checks:

```bash
xrtm perf run \
  --scenario provider-free-smoke \
  --iterations 3 \
  --limit 1 \
  --runs-dir runs-perf \
  --output performance.json \
  --max-mean-seconds 10 \
  --max-p95-seconds 15
```

The report uses the `xrtm.performance.v1` schema and includes per-iteration run ids, durations, forecast counts, Brier scores, total/mean/max/p95 duration, forecasts per second, and budget status.

Scenarios:

- `provider-free-smoke`: deterministic provider-free benchmark for regular local/CI use.
- `provider-free-scale`: deterministic provider-free benchmark for larger limits or iteration counts.
- `local-llm-smoke`: local OpenAI-compatible endpoint benchmark; use only when the local model server is healthy.

Budget gates warn by default. Add `--fail-on-budget` when using the command as a hard release gate:

```bash
xrtm perf run --scenario provider-free-smoke --iterations 3 --limit 1 --max-mean-seconds 10 --fail-on-budget
```

Performance runs intentionally use local relative paths for `--runs-dir` and `--output`; absolute paths and `..` traversal are rejected. The harness also caps `--iterations` at 100 and `--limit` at 1000 to prevent accidental resource exhaustion.

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
