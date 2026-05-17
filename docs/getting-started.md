# Getting Started with XRTM

This is the authoritative first-success path for the published
`xrtm==0.8.4` package.

The `0.8.4` release promotes the bounded local Hub → Studio → Playground →
Observatory product spine on the provider-free baseline. This guide stays
claim-pinned to that released contract: no calibration dashboard, no
API/webhook control plane, no arbitrary code/plugin graph editing, no full
persistent collaborative canvas layout, and no commercial runtime claim without
separate validation.

You will install XRTM, choose either a CLI-led or WebUI-led first-success path,
inspect the latest run, use report/export actions, open the local WebUI Hub,
author one safe workflow draft in Studio or CLI, validate it, run it, trace it
through Playground, inspect evidence in Observatory, and then choose the next
guide that matches your job.

## 1. Install

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install xrtm==0.8.4
```

**Supported Python versions:** `>=3.11,<3.14`

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

The released WebUI is a polished local-only React/TypeScript app shell backed
by a Python JSON API. It gives you the same local forecasting cockpit lanes —
Hub at `/` and `/hub`, Start, Runs, Workflow detail, Operations, Studio,
Playground, Observatory, run detail, compare, Advanced visibility, and
`/workbench` compatibility — without widening the provider-free `0.8.4`
capability contract.

With the default local workspace layout, reusable workflows stay in
`.xrtm/workflows` while draft values, validation snapshots, compare cache, and
resume state stay in `.xrtm/webui/app-state.db`.

Use `http://127.0.0.1:8765/` or `http://127.0.0.1:8765/hub` for the Hub,
`http://127.0.0.1:8765/start` when you want to launch first-success or named
workflow runs, `http://127.0.0.1:8765/operations` when you want profile,
monitor, or cleanup controls, and `http://127.0.0.1:8765/studio` when you are
ready to edit. Studio keeps the baseline in view, starts a local draft from
scratch, a released starter template, or a clone, and then lets you author
shared workflow fields plus safe graph changes inside the released schema and
built-in node library. That includes metadata, questions, runtime,
artifact/scoring settings, local node dragging, palette click/drag-to-canvas
add-node, node/edge/workflow selection, edge create/remove, entry setting,
contextual inspection, and validate/save/run through the Studio APIs.
`/workbench` remains a compatibility route for existing links. Parallel-group
and conditional-route editing remain thin/read-only, and this is not an
arbitrary JSON, implementation, plugin, or code editor.

If you prefer the terminal, the same shared backend authoring layer also powers
`xrtm workflow create scratch|template|clone ...`, `xrtm workflow edit ...`,
`xrtm workflow validate ...`, `xrtm workflow explain ...`, and
`xrtm workflow run ...`.

```bash
xrtm workflow create scratch my-workflow --workflows-dir .xrtm/workflows
xrtm workflow validate my-workflow --workflows-dir .xrtm/workflows
xrtm workflow explain my-workflow --workflows-dir .xrtm/workflows
xrtm workflow run my-workflow --workflows-dir .xrtm/workflows --runs-dir runs
```

`xrtm==0.8.4` releases the bounded graph-linked Playground lane. Open
`http://127.0.0.1:8765/playground` from the same local shell when you want one
custom question first, optional tiny follow-up batches capped at 5, graph/canvas
preview, ordered node trace, executed-node highlighting, an honest fallback when
no graph trace artifact exists, and explicit save-back to workflow/profile only.
Keep those runs exploratory and separate from benchmark or release evidence by
default, and keep the released runtime wording provider-free unless wider
validation is published separately.

```bash
xrtm playground --workflow demo-provider-free --question "Will the released 0.8.4 playground stay exploratory?" --workflows-dir .xrtm/workflows --runs-dir runs
```

That released Playground command uses the provider-free baseline path and the
same shared sandbox contract as the WebUI route.

## 5. Run from Hub or Start, then author safely, validate, run, trace, and compare

From the Hub, `/start`, or `/workflows/<name>`:

1. run the provider-free quickstart or a bounded named workflow
2. inspect the generated run detail
3. open or regenerate the HTML report
4. export JSON or CSV evidence
5. select a baseline run when you want a compare-ready candidate

From Studio, with `/workbench` available as a compatibility route:

1. use Overview or Runs to inspect the baseline you want to keep in view
2. start from scratch, a starter template, or a clone of `demo-provider-free`
3. edit shared core workflow fields or safe node/edge/entry changes inside the released product schema/node library
4. save and validate the draft inline
5. run a candidate
6. review Playground graph trace linkage when the run has graph trace artifacts
7. inspect `/observatory`, `/runs/<candidate-run-id>`, or `/runs/<candidate-run-id>/compare/<baseline-run-id>` before choosing the next step

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

XRTM supports Python `>=3.11,<3.14`. If installation still fails on Python
3.13, upgrade `pip`, `setuptools`, and `wheel`, then reinstall in a fresh
virtual environment.

### Your current directory is read-only

Run the guide from a writable workspace so XRTM can create `runs/`.
