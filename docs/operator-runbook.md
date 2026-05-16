# XRTM Operator Runbook

Use this page after the first success in [getting-started.md](getting-started.md).
It assumes a CLI-led or WebUI-led first-success path already worked and you now
want repeatable local runs, run review, Start/Operations follow-through,
compare/export, monitoring, and cleanup.

## 1. Save a repeatable local profile

```bash
xrtm profile starter my-local --runs-dir runs
xrtm profile show my-local
xrtm run profile my-local
```

`xrtm profile starter` creates a reusable provider-free local profile under
`.xrtm/profiles/` so you can rerun the same shape without retyping options.

The WebUI equivalent lives under `http://127.0.0.1:8765/operations`, where the
Profiles panel exposes starter/custom creation, list, detail, and run actions.

## 2. Review, compare, and export runs

```bash
xrtm runs list --runs-dir runs
xrtm runs show latest --runs-dir runs
xrtm artifacts inspect --latest --runs-dir runs
xrtm report html --latest --runs-dir runs
xrtm runs compare <run-id-a> <run-id-b> --runs-dir runs
xrtm runs export latest --runs-dir runs --output export.json
xrtm runs export latest --runs-dir runs --output export.csv --format csv
```

Use compare only when both runs answer the same question set. JSON is the
full-fidelity export; CSV is the spreadsheet-friendly summary.

The WebUI run detail page exposes the same report generation plus JSON/CSV
export actions from the browser.

## 3. Reopen the WebUI shell and guided workbench

```bash
xrtm web --runs-dir runs --workflows-dir .xrtm/workflows
```

Open `http://127.0.0.1:8765/` to revisit the Overview, Start, Runs, Workflow
detail, Operations, run detail, compare, and Workbench surfaces in the same
local shell.

The browser UI stays local-only: a Python JSON API serves the React app shell,
reusable workflows stay in `.xrtm/workflows`, profiles stay in `.xrtm/profiles`,
and draft values, validation snapshots, compare cache, and resume state are
stored in `.xrtm/webui/app-state.db`.

`/start` launches quickstart, demo, and named workflow runs. `/operations`
covers profiles, monitor lifecycle, artifact inventory, and cleanup
preview/confirm. `/workbench` guides inspect → clone → safe edit → validate →
run → compare.
Safe edits stay bounded to `questions.limit`, report writing, and supported
aggregate weights. It is not an arbitrary graph, JSON, implementation, or code
editor.

Use the terminal TUI when you only need read-only review:

```bash
xrtm tui --runs-dir runs
```

## 4. Monitor and clean up a runs directory

```bash
xrtm monitor start --provider mock --limit 2 --runs-dir runs
xrtm monitor list --runs-dir runs
xrtm artifacts cleanup --runs-dir runs --keep 50
```

The mock/provider-free monitor lane is the safe default for routine operator
checks.

The WebUI Operations page exposes monitor start/list/show/run-once/pause/
resume/halt plus explicit cleanup preview and confirmation before deletion.

## 5. Reopen the read-only review surfaces

```bash
xrtm web --runs-dir runs
xrtm tui --runs-dir runs
```

Use these anytime to revisit recent runs after compare/export or monitoring
work.

## Troubleshooting after first success

- Profile commands need a writable workspace because `.xrtm/profiles/` is created locally.
- If `xrtm runs compare` is noisy or confusing, confirm both runs are meant to be compared before drawing conclusions.
- If the workbench rejects an edit, keep the change inside the released safe fields: `questions.limit`, report writing, and supported aggregate weights.
- If `xrtm artifacts inspect --latest` fails, confirm `runs/` still contains at least one canonical run.
- If you need the canonical install and first-run path again, return to [getting-started.md](getting-started.md).
