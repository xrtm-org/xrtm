# XRTM v0.9.1 — AI for Event Forecasting

[![PyPI](https://img.shields.io/pypi/v/xrtm?style=flat-square)](https://pypi.org/project/xrtm/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue?style=flat-square)](LICENSE)

**XRTM** runs event-forecasting workflows from the command line. Uses any OpenAI-compatible endpoint.

## Install

```bash
pip install xrtm
```

Python >=3.11,<3.14.

## Quick Start

```bash
export OPENAI_API_KEY="sk-..."
xrtm start
```

With a specific model:

```bash
xrtm start --model your-model --base-url $OPENAI_BASE_URL --limit 10
```

## Commands

| Command | What it does |
|---------|-------------|
| `xrtm start` | Run forecasts (requires OPENAI_API_KEY) |
| `xrtm doctor` | Check Python, packages, imports |
| `xrtm runs show --latest` | Inspect the most recent run |

## Run Artifacts

Each run produces these files in `runs/<run-id>/`:
`run.json`, `eval.json`, `train.json`, `forecasts.jsonl`, `report.html`, `provider.json`, `questions.jsonl`

## XRTM Ecosystem

| Package | Role |
|---------|------|
| `xrtm-data` | Schemas & question sources |
| `xrtm-eval` | Scoring (Brier, ECE, LogScore) |
| `xrtm-forecast` | Runtime engine (agents, providers, topologies) |
| `xrtm-train` | Backtesting & optimization |
| `xrtm` | Product CLI (this package) |

## License

Apache 2.0
