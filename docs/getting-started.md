# Getting Started with XRTM

This is the authoritative first-success path for the published
`xrtm==0.3.3` package.

You will install XRTM, run `xrtm start`, inspect the latest run, open the WebUI
or TUI, and then choose the next guide that matches your job.

## 1. Install

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install xrtm==0.3.3
```

**Supported Python versions:** `>=3.11,<3.13`

## 2. Run the guided first command

```bash
xrtm start
```

`xrtm start` runs the released provider-free first-success path. It checks the
installed stack, writes a scored local run under `runs/`, and prints the next
commands for reviewing that run.

## 3. Inspect the latest run

Use the latest-run commands that `xrtm start` prints:

```bash
xrtm runs show latest --runs-dir runs
xrtm artifacts inspect --latest --runs-dir runs
xrtm report html --latest --runs-dir runs
```

After that review, the main files to recognize are `run.json`,
`run_summary.json`, `eval.json`, and `report.html` inside the newest
`runs/<run-id>/` directory.

## 4. Open the same run in the WebUI or TUI

Launch the WebUI:

```bash
xrtm web --runs-dir runs
```

Open `http://127.0.0.1:8765` in your browser.

If you prefer the terminal, launch the TUI instead:

```bash
xrtm tui --runs-dir runs
```

## 5. Choose your next path

- **Researcher:** use the dedicated workflow on [xrtm.org](https://xrtm.org/docs/workflows/researcher-model-eval) for evaluation, compare review, and the deeper quality loop.
- **Operator:** continue with the [Operator Runbook](operator-runbook.md) for repeatable profiles, monitoring, compare/export, and cleanup.
- **Developer:** move to the [Python API Reference](python-api-reference.md) and [integration examples](../examples/integration/) when you want to embed XRTM in code.

## Quick troubleshooting

### `xrtm: command not found`

Activate the virtual environment first:

```bash
. .venv/bin/activate
```

### Installation fails on Python 3.13

This is expected. XRTM currently supports Python `>=3.11,<3.13`.

### Your current directory is read-only

Run the guide from a writable workspace so XRTM can create `runs/`.
