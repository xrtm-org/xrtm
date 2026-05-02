# XRTM Operator Runbook

This runbook covers the supported operating path for the top-level `xrtm`
product shell once the first event-forecasting loop from `getting-started.md`
is already working.

For merge, cross-repo coordination, release-train operation, and release gate requirements, see the governance repo's PR acceptance policy, cross-repo compatibility policy, release train playbook, and release readiness policy:

- `../../governance/policies/pr-acceptance-policy.md`
- `../../governance/policies/cross-repo-compatibility-policy.md`
- `../../governance/policies/release-train-playbook.md`
- `../../governance/policies/release-readiness-policy.md`

**For multi-user and institutional team workflows**, see `team-workflows.md`.

## Supported environment

Use Python `>=3.11,<3.13`.

Python 3.13 is not currently supported because the full dependency stack has not been validated there. The published packages intentionally reject unsupported Python versions.

For coordinated, unpublished upstream changes, rerun the `xrtm` CI workflow with `workflow_dispatch` and explicit `data_ref`, `eval_ref`, `forecast_ref`, and `train_ref` inputs. Record the exact refs and workflow run URL in the linked coordination issue or PR family rather than relying on same-name sibling branches.

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

## Official proof-point set

After the first proof from `getting-started.md`, XRTM expands through four
workflows:

1. **Provider-free first success** via `xrtm start`
2. **Benchmark and validation workflow** via `xrtm perf run` and `xrtm validate run`
3. **Monitoring, history, and report workflow** via profiles, monitor commands, compare/export, and HTML reports
4. **Local-LLM advanced workflow** via `xrtm local-llm status` and `xrtm demo --provider local-llm`

This runbook primarily sharpens workflows 2-4.

## Workflow profiles

Profiles save repeatable local workflow settings so you do not have to retype provider, corpus limit, token budget, model, and run directory options.

```bash
xrtm profile starter my-local --runs-dir runs
xrtm run profile my-local
```

Use `profile starter` right after `xrtm start` when you want the lightest reusable local scaffold. It creates the default `.xrtm/profiles/<name>.json`, keeps `provider=mock`, sets `limit=5`, and ensures the target runs directory exists.

For full control, use the regular profile command:

```bash
xrtm profile create local-mock --provider mock --limit 2 --runs-dir runs
xrtm profile list
xrtm profile show local-mock
xrtm run profile local-mock
```

Profiles are stored under `.xrtm/profiles` by default. Use `--profiles-dir` when you want project-specific or test-specific profile storage.

### User attribution

Use `--user` to tag runs with analyst or team member attribution. This helps track which person or workflow initiated a run when reviewing history or comparing results across desks:

```bash
xrtm demo --provider mock --limit 2 --runs-dir runs --user alice
xrtm run pipeline --provider mock --limit 5 --user bob
xrtm profile create team-profile --provider mock --limit 10 --user team-alpha
```

User attribution appears in:
- `run.json` metadata
- CSV exports (`user` column)
- JSON exports (`run.user` field)
- Run search (searchable via `xrtm runs search <username>`)

User attribution is optional and backward-compatible. Runs without `--user` will have `user: null` in artifacts.

## Provider-free smoke

Use provider-free mode for deterministic validation and CI-safe smoke tests:

```bash
xrtm demo --provider mock --limit 2 --runs-dir runs
xrtm web --runs-dir runs --smoke
```

Provider-free mode does not call hosted APIs.

## Local LLM smoke

⚠️ **Prerequisites**: Run this workflow only after completing local-llm server setup and health verification.

**When to use**: Testing real LLM behavior locally, privacy-sensitive deployments, or offline operation.

**Setup time**: 30-60 minutes for first-time setup (model download, server configuration).

### Step 1: Verify Prerequisites

Before running local-llm mode, ensure:

1. **Local inference server is running** (llama.cpp, Ollama, LocalAI, etc.)
2. **Model weights are downloaded** (multi-GB GGUF files)
3. **GPU has sufficient VRAM** (4GB+ for Q4 quantized 7B models)
4. **Server is OpenAI-compatible** (supports `/v1/chat/completions` endpoint)

### Step 2: Health Check

```bash
export XRTM_LOCAL_LLM_BASE_URL=http://localhost:8080/v1
xrtm local-llm status
```

**Expected output**:
```
✓ Endpoint: http://localhost:8080/v1
✓ Health check: PASS
✓ Models available: 1
```

If health check fails, see the [Troubleshooting](#local-llm-issues) section.

### Step 3: Run Local-LLM Demo

Run local LLM mode only when the health check passes:

```bash
xrtm demo --provider local-llm --limit 1 --max-tokens 768 --runs-dir runs-local
```

**Expected runtime**: 10-90 seconds depending on hardware and token budget.

**Token budget guidance**:
- Testing: `--max-tokens 768`
- Production: `--max-tokens 2048`
- Maximum: Check your model's context length (usually 4096-8192)

If the demo fails, the issue is typically:
- GPU out of memory (reduce model size or token budget)
- Context length exceeded (reduce `--max-tokens`)
- Model output invalid (use larger or less-quantized model)

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

`xrtm artifacts inspect` prints the canonical artifact inventory with present/missing status and on-disk locations, which is useful for first-run review and troubleshooting.

Browse run history without reading JSON files directly:

```bash
xrtm runs list --runs-dir runs
xrtm runs search mock --runs-dir runs
xrtm runs show <run-id> --runs-dir runs
xrtm runs compare <run-id-a> <run-id-b> --runs-dir runs
xrtm runs export <run-id> --runs-dir runs --output export.json
xrtm runs export <run-id> --runs-dir runs --output export.csv --format csv
```

`runs compare` focuses on operationally important summary fields such as status, provider, forecast count, duration, token totals, Brier scores, warnings, and errors. `runs export` writes portable exports in JSON or CSV format. JSON format provides one complete bundle with run metadata, summary, events, forecasts, eval/train payloads, provider metadata, and monitor state when available. CSV format flattens forecasts into spreadsheet-friendly rows, combining run-level metadata with each forecast for convenient analysis in Excel, Pandas, or R.

If you need a reusable Python ETL layer, SQLite/Parquet outputs, or multi-run transforms beyond the built-in CLI export, see the [Data Export integration pattern](../examples/integration/data-export/).

Apply the local retention policy:

```bash
xrtm artifacts cleanup --runs-dir runs --keep 50
xrtm artifacts cleanup --runs-dir runs --keep 50 --delete
```

The command is dry-run by default. Use `--delete` only after checking the listed candidates.

## Monitoring, history, and report workflow

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

If you need custom cron/systemd scheduling, bespoke Markdown reports, or your own notification hooks, see the [Scheduled Monitor integration pattern](../examples/integration/scheduled-monitor/). That example is separate from the shipped `xrtm monitor ...` lifecycle above.

History and report review stay on the same canonical run artifacts:

```bash
xrtm runs list --runs-dir runs
xrtm runs compare <run-id-a> <run-id-b> --runs-dir runs
xrtm runs export latest --runs-dir runs --output latest-run.json
xrtm report html --latest --runs-dir runs
```

Treat this monitor/history/report loop as one proof point: the same local run evidence powers review, export, and operational monitoring.

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
  --output performance.json
```

The report uses the `xrtm.performance.v1` schema and includes per-iteration run ids, durations, forecast counts, Brier scores, total/mean/max/p95 duration, forecasts per second, and budget status.

### Default Performance Budgets

Each scenario has default budgets for regression detection:

- **provider-free-smoke** (limit=10):
  - Mean iteration: 50ms
  - P95 iteration: 100ms
- **provider-free-scale** (limit=100):
  - Mean iteration: 500ms
  - P95 iteration: 1000ms
- **local-llm-smoke**: No default budget (hardware-dependent)

Override budgets explicitly when needed:

```bash
xrtm perf run \
  --scenario provider-free-smoke \
  --iterations 5 \
  --limit 10 \
  --runs-dir runs-perf \
  --output performance.json \
  --max-mean-seconds 0.040 \
  --max-p95-seconds 0.080 \
  --fail-on-budget
```

The `--fail-on-budget` flag causes the command to exit with a non-zero status if budgets are exceeded, suitable for CI gates.

### Scenarios:

- `provider-free-smoke`: deterministic provider-free benchmark for regular local/CI use.
- `provider-free-scale`: deterministic provider-free benchmark for larger limits or iteration counts.
- `local-llm-smoke`: local OpenAI-compatible endpoint benchmark; use only when the local model server is healthy.

Budget gates warn by default. Add `--fail-on-budget` when using the command as a hard release gate:

```bash
xrtm perf run --scenario provider-free-smoke --iterations 3 --limit 1 --runs-dir runs-perf --output performance.json --max-mean-seconds 10 --fail-on-budget
```

Performance runs intentionally use local relative paths for `--runs-dir` and `--output`; absolute paths and `..` traversal are rejected. The harness also caps `--iterations` at 100 and `--limit` at 1000 to prevent accidental resource exhaustion.

Smoke mode for automation:

```bash
xrtm web --runs-dir runs --smoke
```

### Benchmark corpus policy

The current performance scenarios use the `xrtm-real-binary-v1` corpus, a minimal deterministic fixture embedded in `xrtm-data`. For comprehensive release-gate benchmarks, XRTM will adopt **ForecastBench** as the primary Tier 1 source.

**Source classification:**
- **Tier 1 (Release-gate approved)**: ForecastBench (preferred), xrtm-real-binary-v1 (seed corpus)
- **Tier 2 (Evaluation-only)**: FOReCAst (research/non-commercial license, requires approval for release claims)
- **Tier 3 (Optional supplemental)**: Metaculus snapshots (not required for release gates), Polymarket (pending review)

See `data/docs/benchmark-corpus-policy.md` for detailed licensing, provenance, and implementation requirements.

## Large-Scale Validation

The validation harness provides corpus-aware benchmarking with tier/license enforcement and split support:

```bash
# List available corpora
xrtm validate list-corpora
xrtm validate list-corpora --release-gate-only

# Prepare the external FOReCAst cache for large offline sweeps
xrtm validate prepare-corpus --corpus-id forecast-v1

# Deterministic preview only (useful for CI/docs, not large-scale counts)
xrtm validate prepare-corpus --corpus-id forecast-v1 --fixture-preview --refresh

# Run validation with default corpus (Tier 1, safe for CI)
xrtm validate run --provider mock --limit 10 --iterations 2 --runs-dir runs-validation

# Run with specific corpus and split
xrtm validate run \
  --corpus-id xrtm-real-binary-v1 \
  --split train \
  --provider mock \
  --limit 50 \
  --iterations 5 \
  --output-dir .cache/validation

# Release-gate mode (enforces Tier 1 corpus requirement)
xrtm validate run \
  --corpus-id xrtm-real-binary-v1 \
  --release-gate-mode \
  --provider mock \
  --limit 100 \
  --iterations 10
```

**Source modes:**

- `bundled` = embedded corpus shipped with XRTM
- `preview` = deterministic fixture preview for an external corpus
- `external-cache` = full external dataset cached locally for offline reuse

`forecast-v1` is registered as Tier 2 and evaluation-only. If you run it without preparing the cache first, XRTM falls back to the small deterministic preview and tells you so in the validation output.

**Validation artifacts:**

Each validation run produces a structured JSON artifact using the `xrtm.validation.v1` schema:

```json
{
  "schema_version": "xrtm.validation.v1",
  "corpus": {
    "corpus_id": "xrtm-real-binary-v1",
    "tier": "tier-1",
    "license": "apache-2.0",
    "release_gate_approved": true
  },
  "summary": {
    "total_duration_seconds": 12.5,
    "total_forecasts": 100,
    "forecasts_per_second": 8.0,
    "mean_iteration_seconds": 2.5,
    "p95_iteration_seconds": 2.8
  }
}
```

**Performance expectations:**

Provider-free validation runs achieve ~250-300 forecasts/second on typical hardware. Actual throughput depends on:
- Limit size (larger batches amortize overhead)
- Iteration count (package version caching helps multi-iteration runs)
- Artifact writing (disable with `--no-write-artifacts` for pure benchmarking)
- Question complexity (affects evaluation and backtest runtime)

For performance regression monitoring, use the dedicated `xrtm perf` command with default budgets rather than the validation harness.

**Local-LLM stress testing:**

Local-LLM validation is bounded by default for safety. Use explicit opt-in for unbounded runs:

```bash
# Safe default (limit capped at 10)
xrtm validate run --provider local-llm --limit 10

# Unbounded mode (USE WITH CAUTION)
xrtm validate run \
  --provider local-llm \
  --limit 500 \
  --allow-unsafe-local-llm \
  --base-url http://localhost:8080/v1
```

**Corpus registry integration:**

The validation harness uses the corpus registry infrastructure for:
- Tier and license classification
- Release-gate approval filtering
- Split-aware validation (train/eval/held-out)
- Provenance tracking

See `data/docs/corpus-infrastructure-guide.md` for corpus registry API and importer details.

## Troubleshooting

### Provider Setup Issues

#### Choosing Between Mock and Local-LLM

**Problem**: Not sure which provider to use?

**Decision guide**:
- **Use `--provider mock`** (provider-free mode) when:
  - Learning XRTM
  - Writing tests or CI/CD pipelines
  - Benchmarking performance
  - You need deterministic results
  - You want to start immediately with zero setup

- **Use `--provider local-llm`** when:
  - Testing real LLM reasoning behavior
  - Privacy-sensitive deployments
  - Offline operation requirements
  - You have already set up a local inference server

**Recommendation**: Start with `--provider mock`. Only switch to `local-llm` when you need real LLM behavior and have completed the server setup.

### Installation Issues

#### `xrtm` does not install on Python 3.13

This is expected. Use Python 3.11 or 3.12.

### Local-LLM Issues

#### `xrtm local-llm status` reports unavailable

**Symptom**:
```
✗ Endpoint health check failed
```

**Root cause checklist**:
1. **Server not running**
   - Check: `ps aux | grep llama-server` or equivalent
   - Fix: Start your local model server first

2. **Wrong base URL**
   - Check: `echo $XRTM_LOCAL_LLM_BASE_URL`
   - Fix: Ensure URL ends with `/v1` and matches server port
   ```bash
   export XRTM_LOCAL_LLM_BASE_URL=http://localhost:8080/v1
   ```

3. **Server still loading model**
   - Check: Server logs for "HTTP server listening" message
   - Fix: Wait 10-60 seconds for model loading to complete

4. **Network/firewall issue**
   - Check: `curl http://localhost:8080/health`
   - Fix: Verify localhost is accessible, check firewall rules

**Quick diagnostic**:
```bash
# Test basic connectivity
curl http://localhost:8080/health

# Test OpenAI-compatible endpoint
curl http://localhost:8080/v1/models

# Test with XRTM
xrtm local-llm status --base-url http://localhost:8080/v1
```

All three should succeed for local-llm mode to work.

#### Provider-free smoke passes but local LLM smoke fails

**Symptom**: `xrtm demo --provider mock` works, but `xrtm demo --provider local-llm` fails.

**Diagnosis**: This is a local model/server issue, not an XRTM product issue.

**Verification steps**:
1. Check endpoint health:
   ```bash
   xrtm local-llm status
   ```
   
2. Verify GPU availability:
   ```bash
   nvidia-smi
   ```
   
3. Check token budget vs model context:
   - Most models: 4096-8192 token max context
   - Your request: Check `--max-tokens` value
   - Fix: Reduce token budget if exceeding context

4. Check GPU memory:
   - 7B Q4 model: ~4-6GB VRAM needed
   - 13B Q4 model: ~8-10GB VRAM needed
   - Fix: Use smaller/more quantized model or reduce batch size

**Common fixes**:
```bash
# Reduce token budget
xrtm demo --provider local-llm --limit 1 --max-tokens 512

# Check server logs for OOM or context length errors
# Restart server with fewer GPU layers if OOM
```

#### Local-LLM runs are extremely slow

**Symptom**: Each forecast takes 5+ minutes (expected: 10-90 seconds).

**Causes and solutions**:
1. **GPU not being used**: Server started without `--n-gpu-layers`
   ```bash
   nvidia-smi  # Should show GPU utilization during forecast
   ```
   Fix: Restart server with GPU acceleration enabled

2. **Model too large for VRAM**: Falls back to CPU
   Fix: Use more aggressive quantization (Q4) or smaller model

3. **Token budget unnecessarily high**
   Fix: Start with `--max-tokens 768`, increase only if needed

**Performance expectations** (RTX 3090, Qwen 7B Q4):
- 768 tokens: 10-30 seconds per forecast
- 2048 tokens: 30-90 seconds per forecast

If significantly slower, GPU is likely not in use.

### Run Artifact Issues

#### A run directory cannot be inspected

`xrtm artifacts inspect` requires `run.json`. If it is missing, the directory is not a canonical XRTM run artifact.

**Cause**: Run failed before `run.json` was written.

**Fix**: Delete incomplete directory and run again. Check warnings/errors in terminal output.
