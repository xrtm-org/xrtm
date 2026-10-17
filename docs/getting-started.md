# Getting Started with XRTM

This is the authoritative first-success path for the published `xrtm==0.10.8`
package. It is claim-pinned to the commands that actually exist in this release:
`xrtm start`, `xrtm doctor`, `xrtm runs show`, and `xrtm --version`. Anything
else is explicitly out of scope for release-pinned docs.

`xrtm` is the command-line front end for the XRTM forecasting stack
(`xrtm-forecast`, `xrtm-data`, `xrtm-eval`, `xrtm-train`). It forecasts
questions with an OpenAI-compatible LLM, scores them where ground truth is
available, and writes a self-contained run directory you can inspect.

## 1. Install

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install xrtm==0.10.8
```

**Supported Python versions:** `>=3.11,<3.13` (bounded by `xrtm-train`).

## 2. Configure

Set your API key and (optionally) an OpenAI-compatible endpoint and model:

```bash
export OPENAI_API_KEY=sk-...
# Optional:
export OPENAI_BASE_URL="https://api.deepseek.com"
export OPENAI_MODEL="deepseek-v4-flash"
```

Instead of exporting, you can create a `.env` file in the working directory.
The loader is deliberately small and well-defined:

```dotenv
# full-line comments are ignored
OPENAI_API_KEY="sk-..."        # matching quotes are stripped
OPENAI_BASE_URL=https://api.deepseek.com  # trailing " #" comments are stripped
export OPENAI_MODEL=deepseek-v4-flash
```

Supported: `KEY=value`, an optional `export` prefix, matching single/double
quotes, and trailing comments. Not supported: multi-line values, interpolation,
escape sequences. Existing environment variables always win over `.env`.

## 3. Verify readiness

```bash
xrtm doctor
```

`doctor` reports whether the environment, dependency stack, and provider
configuration look usable before you spend a single token.

## 4. First run

```bash
xrtm start
```

This runs the default pipeline (up to 5 questions from the bundled real-binary
corpus), forecasts each with your configured model, scores what can be scored,
and writes a run directory under `runs/`. `xrtm start` prints the run id and the
next commands when it finishes.

Useful variations:

```bash
xrtm start --limit 2
xrtm start --runs-dir runs
xrtm start --model deepseek-v4-pro --base-url https://api.deepseek.com
```

For a zero-cost smoke test that exercises the full pipeline without an API key,
the hidden `--provider` flag still accepts the built-in mock:

```bash
xrtm start --provider mock --limit 2
```

## 5. Inspect the run

```bash
xrtm runs show --latest
xrtm runs show <run-id> --runs-dir runs
```

Each `runs/<run-id>/` directory is self-describing:

| File | Contents |
|---|---|
| `run.json` | run identity, status, timing, artifact index |
| `run_summary.json` | aggregate summary (eval/train payloads, `forecast_count`) |
| `questions.jsonl` | the questions that were forecast |
| `forecasts.jsonl` | one record per forecast (probability, CI, parse status, usage) |
| `eval.json` | evaluation payload when ground truth was available |
| `train.json` | training/backtest payload when it was produced |
| `provider.json` | provider + model actually used |
| `events.jsonl` | ordered pipeline events |

## 6. Choose your next path

- **Researcher:** read the [Python API Reference](python-api-reference.md) to
  embed `xrtm-forecast` agents directly and score with `xrtm-eval`.
- **Operator:** continue with the [Operator Runbook](operator-runbook.md) for
  scheduling, artifacts, and troubleshooting.
- **Integrator:** see [`examples/`](../examples/) for end-to-end scripts.

## Quick troubleshooting

### `xrtm: command not found`

Activate the virtual environment first:

```bash
. .venv/bin/activate
```

### `Error: OPENAI_API_KEY not set`

`xrtm start` prints the exact export lines to add when the key is missing. A
connection or validation failure prints an input/network hint instead — the two
causes are never conflated.

### Installation fails on Python 3.13

This release supports `>=3.11,<3.13`. Use Python 3.11 or 3.12.

### Your current directory is read-only

Run the guide from a writable workspace so XRTM can create `runs/`.
