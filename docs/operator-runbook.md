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

## 3. Reopen the WebUI shell and guided authoring surface

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
preview/confirm. `/workbench` guides inspect → scratch/template/clone → author
shared core workflow fields plus safe node/edge/entry changes → validate → run
→ compare.
Authoring stays inside the released schema and built-in product node library.
Parallel-group and conditional-route editing remain thin/read-only, and the
surface is not an arbitrary graph, JSON, implementation, or code editor.

The terminal exposes the same shared backend through `xrtm workflow create ...`
and `xrtm workflow edit ...` when you prefer text-led authoring.

In `0.8.2`, the same released shell also exposes `/playground` for a bounded
exploratory sandbox: one custom question first, optional tiny follow-up batches
capped at 5, read-only ordered step inspection, and explicit save-back to
workflow/profile only. Keep playground runs exploratory and separate from
benchmark or release evidence by default, and keep the released runtime wording
provider-free unless wider validation is published separately.

```bash
xrtm playground --workflow demo-provider-free --question "Will the released 0.8.2 playground stay exploratory?" --workflows-dir .xrtm/workflows --runs-dir runs
```

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
- If the workbench rejects an edit, keep the change inside the released safe authoring contract: shared core workflow fields plus node/edge/entry edits within the built-in node library. Parallel-group and conditional-route edits still need the thinner path.
- If `xrtm artifacts inspect --latest` fails, confirm `runs/` still contains at least one canonical run.
- If you need the canonical install and first-run path again, return to [getting-started.md](getting-started.md).
