# xRtm: The Generative Forecasting Framework

[![PyPI](https://img.shields.io/pypi/v/xrtm?style=flat-square)](https://pypi.org/project/xrtm/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue?style=flat-square)](LICENSE)

**xRtm** is an open-source framework for institutional-grade generative forecasting and agentic reasoning.

## Installation

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install xrtm==0.2.1
```

This installs the complete framework, including all components below.

Supported Python versions are `>=3.11,<3.13`. Python 3.13 is intentionally excluded until the dependency stack is validated there.

---

## Product shell

The top-level `xrtm` command is the local-first product cockpit for the stack:

```bash
xrtm doctor
xrtm demo --provider mock --limit 2
xrtm artifacts inspect runs/<run-id>
xrtm report html runs/<run-id>
xrtm monitor start --provider mock --limit 2
xrtm monitor run-once runs/<run-id>
xrtm tui --runs-dir runs
xrtm web --runs-dir runs
```

The product shell writes canonical run directories under `runs/`:

```text
runs/<run-id>/
  run.json
  questions.jsonl
  forecasts.jsonl
  eval.json
  train.json
  provider.json
  events.jsonl
  monitor.json
  report.html
  logs/
```

Use `--provider local-llm` with a local OpenAI-compatible endpoint such as llama.cpp when you want a real local model path.

For installation, local LLM setup, artifact inspection, monitor lifecycle, and troubleshooting, see [`docs/operator-runbook.md`](docs/operator-runbook.md).

---

## Ecosystem

| Component | Badge | Description |
| :--- | :--- | :--- |
| **xrtm-forecast** | [![PyPI](https://img.shields.io/pypi/v/xrtm-forecast?style=flat-square)](https://pypi.org/project/xrtm-forecast/) | The Inference Engine |
| **xrtm-data** | [![PyPI](https://img.shields.io/pypi/v/xrtm-data?style=flat-square)](https://pypi.org/project/xrtm-data/) | The Snapshot Vault |
| **xrtm-eval** | [![PyPI](https://img.shields.io/pypi/v/xrtm-eval?style=flat-square)](https://pypi.org/project/xrtm-eval/) | The Judge |
| **xrtm-train** | [![PyPI](https://img.shields.io/pypi/v/xrtm-train?style=flat-square)](https://pypi.org/project/xrtm-train/) | The Training Pipeline |

---

## Documentation

Full documentation is available at **[xrtm.org](https://xrtm.org)**.

---

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
