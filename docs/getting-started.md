# Getting Started with XRTM

This is the authoritative first-success path for the published
`xrtm==0.7.0` package.

You will install XRTM, run `xrtm start`, inspect the latest run, open the
editable workflow workbench, make one safe workflow edit, validate it, run it,
compare the result, and then choose the next guide that matches your job.

## 1. Install

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install xrtm==0.7.0
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

## 4. Open the editable workflow workbench

Launch the local WebUI workbench:

```bash
xrtm web --runs-dir runs
```

Open `http://127.0.0.1:8765/workbench` in your browser.

The workbench shows the latest run, the workflow canvas, validation status, and
safe editing controls. Its released editor is intentionally constrained: it can
clone a workflow into `.xrtm/workflows`, change `questions.limit` within the
released bounds, toggle report writing, adjust supported aggregate weights, then
validate and run the edited workflow.

## 5. Clone, safely edit, validate, run, and compare

From the workbench:

1. clone `demo-provider-free` into a local workflow
2. change `questions.limit` or the report toggle
3. validate the workflow
4. run it
5. compare it with the first run

If you prefer the terminal, the TUI remains available for read-only review:

```bash
xrtm tui --runs-dir runs
```

## 6. Choose your next path

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
