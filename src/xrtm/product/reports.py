"""Report rendering for XRTM product artifacts."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from xrtm.product.artifacts import ArtifactStore


def render_html_report(run_dir: Path) -> Path:
    """Render a static HTML report from a canonical run directory."""

    run = ArtifactStore.read_run(run_dir)
    eval_payload = _read_optional_json(run_dir / "eval.json")
    train_payload = _read_optional_json(run_dir / "train.json")
    provider_payload = _read_optional_json(run_dir / "provider.json")
    forecasts = _read_jsonl(run_dir / "forecasts.jsonl")
    rows = []
    for record in forecasts:
        output = record.get("output", record)
        rows.append(
            "<tr>"
            f"<td>{_escape(record.get('question_id') or output.get('question_id'))}</td>"
            f"<td>{_escape(output.get('probability'))}</td>"
            f"<td>{_escape(output.get('reasoning'))}</td>"
            "</tr>"
        )
    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>XRTM Run {html.escape(str(run.get("run_id", "")))}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.5; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 0.5rem; vertical-align: top; }}
    th {{ background: #f6f8fa; text-align: left; }}
    code, pre {{ background: #f6f8fa; padding: 0.2rem 0.35rem; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>XRTM Run {html.escape(str(run.get("run_id", "")))}</h1>
  <p><strong>Status:</strong> {_escape(run.get("status"))} | <strong>Provider:</strong> {_escape(run.get("provider"))}</p>
  <h2>Forecasts</h2>
  <table>
    <thead><tr><th>Question</th><th>Probability</th><th>Reasoning</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <h2>Evaluation</h2>
  <pre>{_escape(json.dumps(eval_payload, indent=2, sort_keys=True))}</pre>
  <h2>Train/backtest</h2>
  <pre>{_escape(json.dumps(train_payload, indent=2, sort_keys=True))}</pre>
  <h2>Provider</h2>
  <pre>{_escape(json.dumps(provider_payload, indent=2, sort_keys=True))}</pre>
</body>
</html>
"""
    report_path = run_dir / "report.html"
    report_path.write_text(body, encoding="utf-8")
    return report_path


def _read_optional_json(path: Path) -> Any:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _escape(value: Any) -> str:
    return html.escape("" if value is None else str(value))


__all__ = ["render_html_report"]
