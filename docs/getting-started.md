# Getting Started with XRTM

This is the authoritative first-success path for the published
`xrtm==0.8.0` package.

You will install XRTM, choose either a CLI-led or WebUI-led first-success path,
inspect the latest run, use report/export actions, open the local WebUI shell,
make one safe workflow edit in Workbench, validate it, run it, compare the
result, and then choose the next guide that matches your job.

## 1. Install

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install xrtm==0.8.0
```

**Supported Python versions:** `>=3.11,<3.13`

## 2. Choose your first-success interface

```bash
xrtm start
```

**CLI-led first success**

`xrtm start` runs the released provider-free first-success path. It checks the
installed stack, writes a scored local run under `runs/`, and prints the next
commands for reviewing that run.

**WebUI-led first success**

```bash
xrtm web --runs-dir runs
```

Open `http://127.0.0.1:8765/start` and use **Run quickstart**. That Start page
uses the same shared product launch service as `xrtm start`, plus the same
doctor and provider-status data that the CLI surfaces.

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

## 4. Open or keep using the local WebUI shell

Launch the local WebUI:

```bash
xrtm web --runs-dir runs
```

Open `http://127.0.0.1:8765/` in your browser first.

The released WebUI is a local-only React/TypeScript app shell backed by a
Python JSON API. It gives you Overview, Start, Runs, Workflow detail,
Operations, run detail, compare, Advanced visibility, and the `/workbench`
draft flow in one browser shell.

With the default local workspace layout, reusable workflows stay in
`.xrtm/workflows` while draft values, validation snapshots, compare cache, and
resume state stay in `.xrtm/webui/app-state.db`.

Use `http://127.0.0.1:8765/start` when you want to launch first-success or
named workflow runs, `http://127.0.0.1:8765/operations` when you want profile,
monitor, or cleanup controls, and `http://127.0.0.1:8765/workbench` when you
are ready to edit. The guided workbench keeps the baseline in view, creates a
local draft, validates inline, runs a candidate, and links straight into run
detail and compare pages. Its released editor is intentionally constrained: it
can change `questions.limit` within the released bounds, toggle report writing,
and adjust supported aggregate weights. It is not an arbitrary graph, JSON, or
code editor.

## 5. Run from Start, then clone, safely edit, validate, run, and compare

From `/start` or `/workflows/<name>`:

1. run the provider-free quickstart or a bounded named workflow
2. inspect the generated run detail
3. open or regenerate the HTML report
4. export JSON or CSV evidence
5. select a baseline run when you want a compare-ready candidate

From the workbench:

1. use Overview or Runs to inspect the baseline you want to keep in view
2. clone `demo-provider-free` into a local draft
3. change `questions.limit`, the report toggle, or supported aggregate weights
4. save and validate the draft inline
5. run a candidate
6. review `/runs/<candidate-run-id>` or `/runs/<candidate-run-id>/compare/<baseline-run-id>` before choosing the next step

If you prefer the terminal, the TUI remains available for read-only review:

```bash
xrtm tui --runs-dir runs
```

## 6. Choose your next path

- **Researcher:** use the dedicated workflow on [xrtm.org](https://xrtm.org/docs/workflows/researcher-model-eval) for evaluation, compare review, and the deeper quality loop.
- **Operator:** continue with the [Operator Runbook](operator-runbook.md) for repeatable profiles, monitoring, compare/export, cleanup, and the Operations page.
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
