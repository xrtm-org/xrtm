"""Local WebUI over XRTM product artifacts."""

from __future__ import annotations

import html
import json
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from xrtm.product.providers import local_llm_status
from xrtm.product.read_models import list_monitor_records, list_run_records, read_run_detail


def create_web_server(*, runs_dir: Path, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    """Create a local-only HTTP server for run artifacts."""

    handler = partial(WebUIHandler, runs_dir=runs_dir)
    return ThreadingHTTPServer((host, port), handler)


class WebUIHandler(BaseHTTPRequestHandler):
    """Serve a small local dashboard and JSON API."""

    server_version = "XRTMWebUI/0.1"

    def __init__(self, *args: Any, runs_dir: Path, **kwargs: Any) -> None:
        self.runs_dir = runs_dir
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        path = unquote(parsed.path).rstrip("/") or "/"
        try:
            if path == "/":
                self._send_html(render_index_html(self.runs_dir, query_string=parsed.query))
            elif path == "/api/runs":
                self._send_json(web_snapshot(self.runs_dir, **_filters_from_query(parsed.query)))
            elif path.startswith("/api/runs/"):
                self._send_json(run_detail(self.runs_dir, path.removeprefix("/api/runs/")))
            elif path.startswith("/runs/") and path.endswith("/report"):
                self._send_report(path.removeprefix("/runs/").removesuffix("/report"))
            elif path.startswith("/runs/"):
                self._send_html(render_run_html(self.runs_dir, path.removeprefix("/runs/")))
            else:
                self._send_text("Not found", status=HTTPStatus.NOT_FOUND)
        except FileNotFoundError as exc:
            self._send_text(str(exc), status=HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._send_text(str(exc), status=HTTPStatus.BAD_REQUEST)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        return

    def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, body: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_text(self, body: str, status: HTTPStatus) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_report(self, run_id: str) -> None:
        report = _safe_run_dir(self.runs_dir, run_id) / "report.html"
        if not report.exists():
            raise FileNotFoundError(f"{report} does not exist")
        self._send_html(report.read_text(encoding="utf-8"))


def web_snapshot(
    runs_dir: Path,
    *,
    status: str | None = None,
    provider: str | None = None,
    query: str | None = None,
) -> dict[str, Any]:
    """Return dashboard state shared by WebUI route tests and handlers."""

    return {
        "runs_dir": str(runs_dir),
        "filters": {"status": status, "provider": provider, "query": query},
        "runs": list_run_records(runs_dir, status=status, provider=provider, query=query),
        "monitors": list_monitor_records(runs_dir),
        "local_llm": local_llm_status(),
    }


def run_detail(runs_dir: Path, run_id: str) -> dict[str, Any]:
    """Return one run with available monitor and forecast summaries."""

    return read_run_detail(_safe_run_dir(runs_dir, run_id))


def render_index_html(runs_dir: Path, *, query_string: str = "") -> str:
    """Render the dashboard index page."""

    filters = _filters_from_query(query_string)
    snapshot = web_snapshot(runs_dir, **filters)
    rows = []
    for run in snapshot["runs"]:
        run_id = str(run.get("run_id"))
        summary = run.get("summary", {})
        rows.append(
            "<tr>"
            f"<td><a href='/runs/{_escape(run_id)}'>{_escape(run_id)}</a></td>"
            f"<td>{_escape(run.get('status'))}</td>"
            f"<td>{_escape(run.get('provider'))}</td>"
            f"<td>{_escape(summary.get('forecast_count'))}</td>"
            f"<td>{_escape(summary.get('warning_count'))}</td>"
            f"<td>{_escape(run.get('command'))}</td>"
            f"<td>{_escape(run.get('updated_at'))}</td>"
            "</tr>"
        )
    return _page(
        "XRTM Dashboard",
        f"""
        <section>
          <h2>Local LLM</h2>
          <p>Healthy: <strong>{_escape(snapshot['local_llm']['healthy'])}</strong></p>
          <p>Base URL: <code>{_escape(snapshot['local_llm']['base_url'])}</code></p>
        </section>
        <section>
          <h2>Runs</h2>
          <form method='get' action='/'>
            <label>Search <input name='q' value='{_escape(filters.get('query'))}'></label>
            <label>Status <input name='status' value='{_escape(filters.get('status'))}'></label>
            <label>Provider <input name='provider' value='{_escape(filters.get('provider'))}'></label>
            <button type='submit'>Filter</button>
          </form>
          <table>
            <thead><tr><th>Run</th><th>Status</th><th>Provider</th><th>Forecasts</th><th>Warnings</th><th>Command</th><th>Updated</th></tr></thead>
            <tbody>{''.join(rows)}</tbody>
          </table>
        </section>
        """,
    )


def render_run_html(runs_dir: Path, run_id: str) -> str:
    """Render one run detail page."""

    detail = run_detail(runs_dir, run_id)
    run = detail["run"]
    forecast_rows = []
    for record in detail["forecasts"]:
        output = record.get("output", record)
        forecast_rows.append(
            "<tr>"
            f"<td>{_escape(record.get('question_id') or output.get('question_id'))}</td>"
            f"<td>{_escape(output.get('probability'))}</td>"
            f"<td>{_escape(output.get('reasoning'))}</td>"
            "</tr>"
        )
    report_link = f"<p><a href='/runs/{_escape(run_id)}/report'>Open report.html</a></p>"
    return _page(
        f"XRTM Run {run_id}",
        f"""
        <p><a href='/'>Back to dashboard</a></p>
        <h2>{_escape(run.get('run_id'))}</h2>
        <p>Status: <strong>{_escape(run.get('status'))}</strong> | Provider: {_escape(run.get('provider'))}</p>
        {report_link}
        <h2>Summary</h2><pre>{_escape(json.dumps(detail['summary'], indent=2, sort_keys=True))}</pre>
        <h2>Forecasts</h2>
        <table>
          <thead><tr><th>Question</th><th>Probability</th><th>Reasoning</th></tr></thead>
          <tbody>{''.join(forecast_rows)}</tbody>
        </table>
        <h2>Eval</h2><pre>{_escape(json.dumps(detail['eval'], indent=2, sort_keys=True))}</pre>
        <h2>Train/backtest</h2><pre>{_escape(json.dumps(detail['train'], indent=2, sort_keys=True))}</pre>
        """,
    )


def _safe_run_dir(runs_dir: Path, run_id: str) -> Path:
    if "/" in run_id or "\\" in run_id or run_id in {"", ".", ".."}:
        raise ValueError("invalid run id")
    run_dir = runs_dir / run_id
    if not run_dir.is_dir():
        raise FileNotFoundError(f"{run_dir} does not exist")
    return run_dir


def _filters_from_query(query_string: str) -> dict[str, str | None]:
    parsed = parse_qs(query_string)
    return {
        "status": _first_query_value(parsed, "status"),
        "provider": _first_query_value(parsed, "provider"),
        "query": _first_query_value(parsed, "q") or _first_query_value(parsed, "query"),
    }


def _first_query_value(parsed: dict[str, list[str]], key: str) -> str | None:
    values = parsed.get(key, [])
    if not values:
        return None
    value = values[0].strip()
    return value or None


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>{_escape(title)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.5; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 0.5rem; vertical-align: top; }}
    th {{ background: #f6f8fa; text-align: left; }}
    code, pre {{ background: #f6f8fa; padding: 0.2rem 0.35rem; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>{_escape(title)}</h1>
  {body}
</body>
</html>
"""


def _escape(value: Any) -> str:
    return html.escape("" if value is None else str(value))


__all__ = [
    "create_web_server",
    "render_index_html",
    "render_run_html",
    "run_detail",
    "web_snapshot",
]
