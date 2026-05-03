# Scheduled Monitor Example

Run recurring forecasts on a simple schedule and keep a lightweight SQLite trend history.

## What this example does

- loads a fixed question set from `questions.json`
- runs forecasts in provider-free mode or with another configured provider
- stores historical confidence values in `trends.db`
- writes one Markdown report per run
- updates a `latest` symlink for quick inspection

This example is intentionally lightweight. It is separate from the product-shell `xrtm monitor ...` workflow documented in the [Operator Runbook](../../../docs/operator-runbook.md).

## Quick Start

### 1. Install dependencies

```bash
pip install xrtm
```

For scheduled mode:

```bash
pip install xrtm schedule
```

### 2. Run once

```bash
python monitor.py --provider mock --questions-file questions.json --run-once
```

### 3. Run on a schedule

Supported schedule strings in the current script:

- `every hour`
- `every day at 09:00`

Example:

```bash
python monitor.py --provider mock --questions-file questions.json --schedule "every day at 09:00"
```

## Output structure

```text
monitor-runs/
  trends.db
  run-20260501-090000/
    forecasts.jsonl
    report.md
  latest -> run-20260501-090000
```

## Trend storage

Each forecast cycle appends confidence history to `trends.db`, which makes it easy to review movement over time:

```bash
sqlite3 monitor-runs/trends.db "SELECT question_id, confidence, timestamp FROM forecasts ORDER BY timestamp DESC LIMIT 10"
```

## Notes

- Scheduled mode requires the `schedule` package.
- Run directories use timestamp stems and add `-01`, `-02`, ... if overlapping runs start in the same second.
- The current script writes **Markdown reports** only.
- Question configuration supports `track_trend`; additional keys are ignored by the script.

## Deployment ideas

- run `--run-once` from cron for simple automation
- run the scheduled process under `systemd` for a long-lived service
- extend `run_once()` to send Slack, email, or webhook notifications after each report

## Related docs

- [Integration Examples index](../) — choose a pattern by user job
- [Operator Runbook](../../../docs/operator-runbook.md) — shipped `xrtm monitor ...` lifecycle and provider configuration
- [Python API Reference](../../../docs/python-api-reference.md) — forecast APIs used by custom scheduling/reporting code

## Related examples

- [Batch Processing](../batch-processing/)
- [Data Export](../data-export/)
- [FastAPI Service](../fastapi-service/)
