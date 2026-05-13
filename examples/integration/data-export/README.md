# Data Export Example

Flatten canonical XRTM run artifacts into analysis-friendly CSV, JSON, SQLite, or Parquet outputs.

## What this example does

- reads canonical `runs/<run-id>/` artifacts
- joins `run.json`, `questions.jsonl`, `forecasts.jsonl`, and `eval.json`
- exports one row per forecast with run metadata
- computes per-forecast Brier scores when resolved outcomes are available

If you only need a single run export from the CLI, the current source tree also contains a built-in CSV path:

```bash
xrtm runs export <run-id> --output export.csv --format csv
```

That CSV flag is now part of the published `xrtm==0.3.3` surface. Use this example when you want a **custom data pipeline** or a reusable Python integration surface beyond the built-in one-off CLI export from the [Operator Runbook](../../../docs/operator-runbook.md).

Use exports honestly:

- first decide in the product shell whether a run is worth keeping
- unchanged mock-provider comparisons mean you are still looking at the control, not a visible improvement
- export becomes most valuable after a meaningful provider/model/runtime change earns a better compare result and you want notebook, SQL, or spreadsheet follow-up

## Quick Start

### 1. Create a sample run

```bash
xrtm demo --provider mock --limit 2 --runs-dir runs
```

### 2. Export one run to CSV

```bash
python export.py --run-id <run-id> --runs-dir runs --format csv --output forecast_data.csv
```

### 3. Export all runs to SQLite

```bash
python export.py --runs-dir runs --format sqlite --output forecasts.db
```

### 4. Load as a DataFrame

```python
from export import RunExporter

exporter = RunExporter("runs")
df = exporter.to_dataframe()
print(df.head())
```

`to_dataframe()` requires `pandas`. CSV, JSON, and SQLite export do not.

## Install dependencies

Base usage:

```bash
pip install xrtm
```

For DataFrame workflows:

```bash
pip install xrtm pandas
```

For Parquet:

```bash
pip install xrtm pandas pyarrow
```

## Output fields

Each exported record contains:

| Field | Description |
| --- | --- |
| `run_id` | Canonical XRTM run identifier |
| `question_id` | Question identifier from the corpus |
| `question_title` | Human-readable question title |
| `probability` | Forecast probability |
| `reasoning` | Forecast reasoning text |
| `recorded_at` | Forecast timestamp |
| `provider` | Provider used for the run |
| `user` | Optional user attribution |
| `resolution_time` | Resolution timestamp when available |
| `outcome` | Resolved boolean outcome when available |
| `brier_score` | Computed per-forecast Brier score when outcome exists |
| `tokens_used` | Total tokens reported by provider metadata when available |

## SQLite schema

The SQLite export writes:

- `runs` — run-level metadata and aggregate eval score
- `evaluations` — run-level eval metrics
- `forecasts` — flattened forecast rows
- rerunning the SQLite export against the same file refreshes rows for the selected runs instead of appending duplicate forecast rows

Example query:

```sql
SELECT provider, AVG(brier_score)
FROM forecasts
WHERE brier_score IS NOT NULL
GROUP BY provider;
```

## Command reference

```bash
# Export one run as JSON
python export.py --run-id <run-id> --runs-dir runs --format json --output forecasts.json

# Export newest 10 runs to SQLite
python export.py --runs-dir runs --limit 10 --format sqlite --output forecasts.db

# Export all runs to Parquet
python export.py --runs-dir runs --format parquet --output forecasts.parquet
```

## Related docs

- [Integration Examples index](../) — choose a pattern by user job
- [Getting Started Guide](../../../docs/getting-started.md) — create a canonical sample run first
- [Operator Runbook](../../../docs/operator-runbook.md) — built-in `xrtm runs export` and artifact lifecycle
- [Python API Reference](../../../docs/python-api-reference.md) — library surfaces behind custom ETL code

## Related examples

- [Batch Processing](../batch-processing/)
- [Scheduled Monitor](../scheduled-monitor/)
- [FastAPI Service](../fastapi-service/)
