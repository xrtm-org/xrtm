# Batch Processing Example

Process multiple forecasting questions from JSON or CSV files and write lightweight batch artifacts for downstream review.

## What this example does

- Loads questions from JSON or CSV
- Runs one forecast per question
- Continues past individual failures
- Writes `forecasts.jsonl`, `errors.jsonl`, and `summary.json` for the batch

This is a **programmatic integration example**, not the canonical product pipeline. If you need full XRTM run directories with eval/train/report artifacts, use the top-level `xrtm demo` or `xrtm run pipeline` commands instead. See the [Getting Started Guide](../../../docs/getting-started.md) for the first shipped workflow and the [Operator Runbook](../../../docs/operator-runbook.md) for the full CLI pipeline and artifact lifecycle.

## Quick Start

### 1. Install dependencies

For JSON input:

```bash
pip install xrtm
```

For CSV input:

```bash
pip install xrtm pandas
```

### 2. Run the example in provider-free mode

```bash
python run_batch.py --provider mock --input sample_questions.json
```

### 3. Run with another provider

```bash
export GEMINI_API_KEY="your-key"
python run_batch.py --provider gemini --model gemini-2.0-flash --input sample_questions.json
```

## Input formats

### JSON

```json
[
  {
    "id": "q1",
    "question": "Will unemployment exceed 5% in 2027?",
    "resolution_date": "2027-12-31",
    "metadata": {"category": "economics"}
  }
]
```

### CSV

```csv
id,question,resolution_date,category
q1,"Will unemployment exceed 5% in 2027?",2027-12-31,economics
```

## Output structure

```text
batch-runs/
  batch-20260501-123045/
    summary.json
    forecasts.jsonl
    errors.jsonl
```

## Notes

- Processing is **sequential** in the current example.
- CSV support requires `pandas`.
- Batch directories use timestamp stems and add `-01`, `-02`, ... if multiple runs start in the same second.
- The script writes **batch-level JSONL artifacts**, not canonical `runs/<run-id>/` product artifacts.

## Extending it

Common next steps:

- fetch questions from a database before calling `process_batch()`
- add provider-specific retry/backoff logic around `_process_question()`
- parallelize processing for remote providers if your rate limits allow it

## Related docs

- [Integration Examples index](../) — choose a pattern by user job
- [Getting Started Guide](../../../docs/getting-started.md) — first shipped local run and canonical artifacts
- [Python API Reference](../../../docs/python-api-reference.md) — library surfaces used by custom wrappers
- [Operator Runbook](../../../docs/operator-runbook.md) — provider setup and product CLI workflows

## Related examples

- [FastAPI Service](../fastapi-service/)
- [Scheduled Monitor](../scheduled-monitor/)
- [Data Export](../data-export/)
