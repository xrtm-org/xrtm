# XRTM Operator Runbook

Use this page after the first success in [getting-started.md](getting-started.md).
It assumes `xrtm start` already worked and you now want repeatable local runs,
run review, editable workbench follow-through, compare/export, monitoring, and
cleanup.

## 1. Save a repeatable local profile

```bash
xrtm profile starter my-local --runs-dir runs
xrtm profile show my-local
xrtm run profile my-local
```

`xrtm profile starter` creates a reusable provider-free local profile under
`.xrtm/profiles/` so you can rerun the same shape without retyping options.

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

## 3. Reopen and steer the workflow workbench

```bash
xrtm web --runs-dir runs --workflows-dir .xrtm/workflows
```

Open `http://127.0.0.1:8765/workbench` to review the workflow canvas for recent
runs. The released workbench can clone a workflow into `.xrtm/workflows`, apply
bounded safe edits, validate the edited workflow, run it, and compare the new run
against a baseline. It is not an arbitrary graph, JSON, implementation, or code
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
