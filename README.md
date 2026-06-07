# XRTM v0.9.0 — AI for Event Forecasting

[![PyPI](https://img.shields.io/pypi/v/xrtm?style=flat-square)](https://pypi.org/project/xrtm/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue?style=flat-square)](LICENSE)

**XRTM** runs event-forecasting workflows from the command line. It uses a deterministic baseline by default (no API keys needed) and supports any OpenAI-compatible endpoint for real LLM forecasts.

## Install

```bash
pip install xrtm
```

Python >=3.11,<3.14.

## Quick Start

```bash
# Deterministic baseline (no API key)
xrtm start

# With a real LLM via any OpenAI-compatible endpoint
xrtm start --provider openai --model deepseek-v4-pro --base-url https://api.deepseek.com

# Inspect results
xrtm runs show --latest
```

## Commands

| Command | What it does |
|---------|-------------|
| `xrtm start` | Run forecasts (deterministic or real LLM) |
| `xrtm demo` | Quick 2-question deterministic demo |
| `xrtm doctor` | Check Python, packages, imports |
| `xrtm runs show --latest` | Inspect the most recent run |

## Providers

| Provider | API key needed |
|----------|---------------|
| `deterministic` (default) | None |
| `openai` / `openai-compatible` | `OPENAI_API_KEY` |

Set `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL` in your environment or `.env` file.

## Run Artifacts

Each run produces 11 artifacts in `runs/<run-id>/`:
`run.json`, `eval.json`, `train.json`, `forecasts.jsonl`, `report.html`, `blueprint.json`, `provider.json`, `questions.jsonl`, `events.jsonl`, `graph_trace.jsonl`, `run_summary.json`

## XRTM Ecosystem

| Package | Role |
|---------|------|
| `xrtm-data` | Schemas & question sources (real-binary corpus, Polymarket, Metaculus) |
| `xrtm-eval` | Scoring (Brier, ECE, LogScore) |
| `xrtm-forecast` | Runtime engine (agents, providers, topologies) |
| `xrtm-train` | Backtesting & optimization |
| `xrtm` | Product CLI (this package) |

## License

Apache 2.0
