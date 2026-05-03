# Integration Examples

This directory contains **integration patterns** built on top of shipped XRTM APIs, CLI commands, and run artifacts.

These examples are **not additional built-in product features**. They show how to compose today's package into your own scripts, services, and automation.

**Quick chooser:** start with `xrtm` for the released, provider-free product workflow; start with `xrtm-forecast` and these examples when you are embedding forecasting directly in your own code.

## Start with the product if your job is...

- **Get your first successful local run**: use the [Getting Started Guide](../../docs/getting-started.md).
- **Learn the canonical XRTM pipeline and run artifacts**: start with the [Getting Started Guide](../../docs/getting-started.md) and the [Operator Runbook](../../docs/operator-runbook.md).
- **Configure providers, local LLMs, monitor lifecycle, compare/export review, or performance workflows**: use the [Operator Runbook](../../docs/operator-runbook.md).

## Choose an example by job to be done

| Your job | Start here | Shipped XRTM surface to know about | What the example actually demonstrates |
| --- | --- | --- | --- |
| I need my **first local run** and want to inspect real artifacts | [Getting Started Guide](../../docs/getting-started.md) | released `xrtm demo --provider mock --limit 1 --runs-dir runs`, explicit run-id inspect/report commands, canonical `runs/<run-id>/` artifacts | This is a product workflow, not an integration example |
| I want to **review two runs, export the winner, and do deeper analysis** | [Data Export](./data-export/) | `xrtm runs compare`, `xrtm runs export`, canonical artifact directories | Downstream ETL and notebook/SQLite analysis after the product compare gate identifies a run worth keeping |
| I want to **reuse XRTM inside a script or batch job** with my own question list | [Batch Processing](./batch-processing/) | Forecast APIs, mock-provider smoke path | Reading CSV/JSON input and writing lightweight batch artifacts |
| I need to **embed forecasting behind an HTTP API** for another application | [FastAPI Service](./fastapi-service/) | Python package APIs used inside your own service | A sample FastAPI wrapper with request validation and in-memory history |
| I want to **schedule recurring forecasts or custom notifications** | [Scheduled Monitor](./scheduled-monitor/) | Built-in `xrtm monitor ...` workflow in the [Operator Runbook](../../docs/operator-runbook.md) | A lightweight Python scheduling/reporting pattern with SQLite trend history |
| I need to **export canonical run artifacts** into analytics or BI tooling | [Data Export](./data-export/) | Canonical run directories and `xrtm runs export` in the [Operator Runbook](../../docs/operator-runbook.md) | Custom ETL around shipped artifacts, including CSV/JSON/SQLite/Parquet outputs |

## Builder-oriented patterns

### [Batch Processing](./batch-processing/)

Use this when you already have questions in CSV or JSON and want a simple Python entry point for repeated runs.

- Best for: reused scripts, cron jobs, or research ingestion
- Not the canonical product pipeline: it writes example-specific batch artifacts
- Product docs to read alongside it: [Getting Started](../../docs/getting-started.md), [Operator Runbook](../../docs/operator-runbook.md)

### [FastAPI Service](./fastapi-service/)

Use this when another app needs an HTTP interface in front of XRTM.

- Best for: builder integrations, internal tools, or service prototypes
- Not a shipped XRTM server: it is sample FastAPI application code
- Product docs to read alongside it: [Python API Reference](../../docs/python-api-reference.md), [Operator Runbook](../../docs/operator-runbook.md)

## Workflow and operator patterns

Use the product-shell compare gate first when you are trying to prove
"improvement over time" honestly. These examples are for what comes after that:
custom exports, services, schedulers, and scripts layered on top of canonical
run artifacts.

### [Scheduled Monitor](./scheduled-monitor/)

Use this when you need custom scheduling, custom report generation, or notification hooks in Python.

- Best for: cron/systemd jobs and bespoke alert/report flows
- If you want the shipped monitor lifecycle, use `xrtm monitor ...` from the [Operator Runbook](../../docs/operator-runbook.md)
- The example writes lightweight SQLite and Markdown outputs rather than product monitor artifacts

### [Data Export](./data-export/)

Use this when canonical XRTM runs already exist and you need to reshape them for downstream analysis.

- Best for: pandas, SQLite, BI, or warehouse ingestion
- If the built-in CLI export is enough, start with `xrtm runs export` in the [Operator Runbook](../../docs/operator-runbook.md)
- The example shows how to build a reusable Python ETL layer on top of shipped run artifacts

## What every example includes

- Working code
- A focused README with setup instructions
- A provider-free path when practical
- Notes about where the example differs from shipped product workflows

Example smoke path:

```bash
cd batch-processing/
python run_batch.py --provider mock --input sample_questions.json
```

## Provider support

All examples are intended to be understandable and testable with the **mock provider** where the individual example supports it.

Some examples also accept other provider/model combinations supported by your installed `xrtm-forecast` stack, such as local OpenAI-compatible endpoints or hosted providers configured through model IDs. Provider configuration itself is documented in the [Operator Runbook](../../docs/operator-runbook.md).

## Related documentation

- [Getting Started Guide](../../docs/getting-started.md) - first local run and canonical artifacts
- [Python API Reference](../../docs/python-api-reference.md) - library surfaces used by custom integrations
- [Operator Runbook](../../docs/operator-runbook.md) - provider setup, monitor lifecycle, exports, validation, and troubleshooting

## Contributing

To add a new integration example:
1. Create a new subdirectory with a descriptive name
2. Include a `README.md` that explains the user job it addresses
3. State clearly whether it wraps a shipped product surface or demonstrates a custom pattern
4. Provide working code with setup instructions
5. Add the example to the job matrix above
6. Verify a provider-free or otherwise documented smoke path
