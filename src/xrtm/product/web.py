"""Local WebUI over XRTM product artifacts."""

from __future__ import annotations

import html
import json
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlencode, urlparse

from xrtm.product.providers import local_llm_status
from xrtm.product.read_models import list_monitor_records, list_run_records, read_run_detail
from xrtm.product.workbench import (
    WorkbenchInputError,
    apply_workbench_edit,
    clone_workflow_for_edit,
    run_workbench_workflow,
    validate_workbench_workflow,
    workbench_snapshot,
    workflow_registry_for,
)
from xrtm.product.workflows import DEFAULT_LOCAL_WORKFLOWS_DIR


def create_web_server(
    *,
    runs_dir: Path,
    host: str = "127.0.0.1",
    port: int = 8765,
    workflows_dir: Path = DEFAULT_LOCAL_WORKFLOWS_DIR,
) -> ThreadingHTTPServer:
    """Create a local-only HTTP server for run artifacts and the workflow workbench."""

    handler = partial(WebUIHandler, runs_dir=runs_dir, workflows_dir=workflows_dir)
    return ThreadingHTTPServer((host, port), handler)


class WebUIHandler(BaseHTTPRequestHandler):
    """Serve a small local dashboard, workflow workbench, and JSON API."""

    server_version = "XRTMWebUI/0.2"

    def __init__(self, *args: Any, runs_dir: Path, workflows_dir: Path, **kwargs: Any) -> None:
        self.runs_dir = runs_dir
        self.workflows_dir = workflows_dir
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        path = unquote(parsed.path).rstrip("/") or "/"
        try:
            if path == "/":
                self._send_html(render_index_html(self.runs_dir, query_string=parsed.query))
            elif path == "/workbench":
                self._send_html(render_workbench_html(self.runs_dir, self.workflows_dir, query_string=parsed.query))
            elif path == "/api/runs":
                self._send_json(web_snapshot(self.runs_dir, **_filters_from_query(parsed.query)))
            elif path == "/api/workbench":
                query = _workbench_query(parsed.query)
                self._send_json(workbench_snapshot(self.runs_dir, self.workflows_dir, **query))
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

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        path = unquote(parsed.path).rstrip("/") or "/"
        try:
            form = self._read_form()
            registry = workflow_registry_for(self.workflows_dir)
            if path == "/workbench/clone":
                source_name = _required_form_value(form, "source_name")
                target_name = _required_form_value(form, "target_name")
                overwrite = _optional_form_value(form, "overwrite") in {"true", "on", "1"}
                clone_workflow_for_edit(
                    registry,
                    source_name=source_name,
                    target_name=target_name,
                    overwrite=overwrite,
                )
                self._redirect(
                    "/workbench?" + urlencode({"workflow": target_name, "message": f"Cloned {source_name} to {target_name}."})
                )
            elif path == "/workbench/edit":
                workflow_name = _required_form_value(form, "workflow_name")
                edit_values = {key: value for key, value in form.items() if key != "workflow_name"}
                updated = apply_workbench_edit(registry, workflow_name=workflow_name, values=edit_values)
                self._redirect(
                    "/workbench?"
                    + urlencode({"workflow": updated.name, "message": f"Saved safe edits for {updated.name}."})
                )
            elif path == "/workbench/validate":
                workflow_name = _required_form_value(form, "workflow_name")
                report = validate_workbench_workflow(registry, workflow_name)
                if not report["ok"]:
                    raise WorkbenchInputError("; ".join(report["errors"]))
                self._redirect(
                    "/workbench?" + urlencode({"workflow": workflow_name, "message": f"Workflow valid: {workflow_name}."})
                )
            elif path == "/workbench/run":
                workflow_name = _required_form_value(form, "workflow_name")
                baseline_run_ref = _optional_form_value(form, "baseline_run_ref")
                result = run_workbench_workflow(
                    registry,
                    workflow_name=workflow_name,
                    runs_dir=self.runs_dir,
                    baseline_run_ref=baseline_run_ref,
                )
                query = {"workflow": workflow_name, "run": result.run_id, "message": f"Ran {workflow_name}: {result.run_id}."}
                if result.baseline_run_id:
                    query["compare"] = result.baseline_run_id
                self._redirect("/workbench?" + urlencode(query))
            else:
                self._send_text("Not found", status=HTTPStatus.NOT_FOUND)
        except (WorkbenchInputError, FileExistsError, FileNotFoundError, ValueError) as exc:
            self._send_html(
                render_workbench_html(self.runs_dir, self.workflows_dir, query_string="", error=str(exc)),
                status=HTTPStatus.BAD_REQUEST,
            )
        except Exception as exc:  # pragma: no cover - defensive server boundary
            self._send_html(
                render_workbench_html(self.runs_dir, self.workflows_dir, query_string="", error=f"Run failed: {exc}"),
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

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

    def _redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_report(self, run_id: str) -> None:
        report = _safe_run_dir(self.runs_dir, run_id) / "report.html"
        if not report.exists():
            raise FileNotFoundError(f"{report} does not exist")
        self._send_html(report.read_text(encoding="utf-8"))

    def _read_form(self) -> dict[str, str]:
        content_type = self.headers.get("Content-Type", "")
        if "application/x-www-form-urlencoded" not in content_type:
            raise WorkbenchInputError("POST requests must use application/x-www-form-urlencoded")
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise WorkbenchInputError("missing Content-Length")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise WorkbenchInputError("invalid Content-Length") from exc
        if length < 0 or length > 65536:
            raise WorkbenchInputError("form payload is too large")
        payload = self.rfile.read(length).decode("utf-8")
        parsed = parse_qs(payload, keep_blank_values=True)
        values: dict[str, str] = {}
        for key, entries in parsed.items():
            if len(entries) != 1:
                raise WorkbenchInputError(f"duplicate form field: {key}")
            values[key] = entries[0]
        return values


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
        workflow = run.get("workflow", {})
        rows.append(
            "<tr>"
            f"<td><a href='/runs/{_escape(run_id)}'>{_escape(run_id)}</a></td>"
            f"<td>{_escape(_workflow_label(workflow))}</td>"
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
        <nav><a href='/workbench'>Open editable workflow workbench</a></nav>
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
            <thead><tr><th>Run</th><th>Workflow</th><th>Status</th><th>Provider</th><th>Forecasts</th><th>Warnings</th><th>Command</th><th>Updated</th></tr></thead>
            <tbody>{''.join(rows)}</tbody>
          </table>
        </section>
        """,
    )


def render_workbench_html(
    runs_dir: Path,
    workflows_dir: Path = DEFAULT_LOCAL_WORKFLOWS_DIR,
    *,
    query_string: str = "",
    error: str | None = None,
) -> str:
    """Render the editable workflow canvas/workbench page."""

    query = _workbench_query(query_string)
    message = _first_query_value(parse_qs(query_string), "message")
    snapshot = workbench_snapshot(runs_dir, workflows_dir, **query)
    return _page(
        "XRTM Workflow Workbench",
        f"""
        <p><a href='/'>Back to dashboard</a></p>
        {_notice('error', error or snapshot.get('workflow_error') or snapshot.get('compare_error'))}
        {_notice('message', message)}
        <section class='grid'>
          <div>{_render_run_picker(snapshot)}</div>
          <div>{_render_workflow_picker(snapshot)}</div>
        </section>
        <section>
          <h2>Workflow canvas</h2>
          {_render_canvas(snapshot['canvas'])}
          {_render_node_table(snapshot['canvas'])}
        </section>
        <section class='grid'>
          <div>{_render_clone_form(snapshot)}</div>
          <div>{_render_safe_edit_form(snapshot)}</div>
        </section>
        <section class='grid'>
          <div>{_render_validate_form(snapshot)}</div>
          <div>{_render_run_form(snapshot)}</div>
        </section>
        {_render_compare(snapshot)}
        <section>
          <h2>Intentional MVP limits</h2>
          <ul>{''.join(f'<li>{_escape(item)}</li>' for item in (snapshot.get('safe_edit') or {}).get('limitations', []))}</ul>
        </section>
        """,
    )


def render_run_html(runs_dir: Path, run_id: str) -> str:
    """Render one run detail page."""

    detail = run_detail(runs_dir, run_id)
    run = detail["run"]
    workflow = detail.get("workflow", {})
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
    workflow_block = ""
    if workflow:
        workflow_block = f"<h2>Workflow</h2><pre>{_escape(json.dumps(workflow, indent=2, sort_keys=True))}</pre>"
    graph_trace_block = ""
    if detail.get("graph_trace"):
        graph_trace_block = (
            "<h2>Graph trace</h2><pre>"
            f"{_escape(json.dumps(detail['graph_trace'][:12], indent=2, sort_keys=True))}"
            "</pre>"
        )
    competition_block = ""
    if detail.get("competition_submission"):
        competition_block = (
            "<h2>Competition dry-run bundle</h2><pre>"
            f"{_escape(json.dumps(detail['competition_submission'], indent=2, sort_keys=True))}"
            "</pre>"
        )
    return _page(
        f"XRTM Run {run_id}",
        f"""
        <p><a href='/'>Back to dashboard</a> | <a href='/workbench?run={_escape(run_id)}'>Open in workbench</a></p>
        <h2>{_escape(run.get('run_id'))}</h2>
        <p>Status: <strong>{_escape(run.get('status'))}</strong> | Provider: {_escape(run.get('provider'))}</p>
        {report_link}
        {workflow_block}
        <h2>Summary</h2><pre>{_escape(json.dumps(detail['summary'], indent=2, sort_keys=True))}</pre>
        <h2>Forecasts</h2>
        <table>
          <thead><tr><th>Question</th><th>Probability</th><th>Reasoning</th></tr></thead>
          <tbody>{''.join(forecast_rows)}</tbody>
        </table>
        <h2>Eval</h2><pre>{_escape(json.dumps(detail['eval'], indent=2, sort_keys=True))}</pre>
        <h2>Train/backtest</h2><pre>{_escape(json.dumps(detail['train'], indent=2, sort_keys=True))}</pre>
        {graph_trace_block}
        {competition_block}
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


def _workbench_query(query_string: str) -> dict[str, str | None]:
    parsed = parse_qs(query_string)
    return {
        "run_ref": _first_query_value(parsed, "run"),
        "workflow_name": _first_query_value(parsed, "workflow"),
        "compare_ref": _first_query_value(parsed, "compare"),
    }


def _first_query_value(parsed: dict[str, list[str]], key: str) -> str | None:
    values = parsed.get(key, [])
    if not values:
        return None
    value = values[0].strip()
    return value or None


def _required_form_value(form: dict[str, str], key: str) -> str:
    value = form.get(key, "").strip()
    if not value:
        raise WorkbenchInputError(f"{key} is required")
    return value


def _optional_form_value(form: dict[str, str], key: str) -> str | None:
    value = form.get(key, "").strip()
    return value or None


def _render_run_picker(snapshot: dict[str, Any]) -> str:
    options = []
    selected = snapshot.get("selected_run_ref")
    for run in snapshot["runs"]:
        run_id = str(run.get("run_id"))
        marker = " selected" if run_id == selected else ""
        options.append(f"<option value='{_escape(run_id)}'{marker}>{_escape(run_id)} ({_escape(run.get('status'))})</option>")
    if not options:
        options.append("<option value=''>No runs yet</option>")
    selected_run = snapshot.get("selected_run") or {}
    summary = selected_run.get("summary", {}) if isinstance(selected_run, dict) else {}
    return f"""
    <h2>1. Inspect run</h2>
    <form method='get' action='/workbench'>
      <input type='hidden' name='workflow' value='{_escape(snapshot.get('selected_workflow_name'))}'>
      <label>Run <select name='run'>{''.join(options)}</select></label>
      <button type='submit'>Inspect</button>
    </form>
    <p>Latest/selected status: <strong>{_escape((selected_run.get('run') or {}).get('status') if selected_run else 'none')}</strong></p>
    <p>Forecasts: {_escape(summary.get('forecast_count'))} | Warnings: {_escape(summary.get('warning_count'))}</p>
    """


def _render_workflow_picker(snapshot: dict[str, Any]) -> str:
    selected = snapshot.get("selected_workflow_name")
    options = []
    for workflow in snapshot["workflows"]:
        name = str(workflow["name"])
        marker = " selected" if name == selected else ""
        options.append(f"<option value='{_escape(name)}'{marker}>{_escape(name)} [{_escape(workflow['source'])}]</option>")
    if not options:
        options.append("<option value=''>No workflows found</option>")
    source = snapshot.get("selected_workflow_source") or {}
    return f"""
    <h2>Workflow</h2>
    <form method='get' action='/workbench'>
      <input type='hidden' name='run' value='{_escape(snapshot.get('selected_run_ref'))}'>
      <label>Workflow <select name='workflow'>{''.join(options)}</select></label>
      <button type='submit'>Open</button>
    </form>
    <p>Source: <strong>{_escape(source.get('source', 'n/a'))}</strong> <code>{_escape(source.get('path', ''))}</code></p>
    """


def _render_clone_form(snapshot: dict[str, Any]) -> str:
    selected = snapshot.get("selected_workflow_name") or ""
    default_target = f"{selected}-editable" if selected else "my-workflow"
    options = []
    for workflow in snapshot["workflows"]:
        name = str(workflow["name"])
        marker = " selected" if name == selected else ""
        options.append(f"<option value='{_escape(name)}'{marker}>{_escape(name)}</option>")
    return f"""
    <h2>2. Clone workflow</h2>
    <form method='post' action='/workbench/clone'>
      <label>Source <select name='source_name'>{''.join(options)}</select></label>
      <label>Local name <input name='target_name' value='{_escape(default_target)}' pattern='[A-Za-z0-9_.-]+' required></label>
      <label><input type='checkbox' name='overwrite' value='true'> overwrite existing local workflow</label>
      <button type='submit'>Clone into .xrtm/workflows</button>
    </form>
    """


def _render_safe_edit_form(snapshot: dict[str, Any]) -> str:
    model = snapshot.get("safe_edit")
    workflow_name = snapshot.get("selected_workflow_name") or ""
    if not model:
        return "<h2>3. Safe edit</h2><p>Select a workflow first.</p>"
    write_report = model["artifacts_write_report"]
    report_options = "".join(
        [
            f"<option value='true'{' selected' if write_report else ''}>write report.html</option>",
            f"<option value='false'{' selected' if not write_report else ''}>skip report.html</option>",
        ]
    )
    weight_controls = []
    for editor in model["aggregate_weight_editors"]:
        controls = [f"<h3>Aggregate weights: {_escape(editor['node'])}</h3>"]
        for contributor in editor["contributors"]:
            controls.append(
                f"<label>{_escape(contributor['name'])} "
                f"<input type='range' name='weight:{_escape(editor['node'])}:{_escape(contributor['name'])}' min='0' max='100' "
                f"value='{_escape(contributor['percent'])}' oninput='this.nextElementSibling.value=this.value'>"
                f"<output>{_escape(contributor['percent'])}</output>%</label>"
            )
        weight_controls.append("".join(controls))
    return f"""
    <h2>3. Safe edit</h2>
    <form method='post' action='/workbench/edit'>
      <input type='hidden' name='workflow_name' value='{_escape(workflow_name)}'>
      <label>questions.limit <input type='number' name='questions_limit' min='1' max='{_escape(model['questions_limit']['max'])}' value='{_escape(model['questions_limit']['value'])}' required></label>
      <label>artifacts.write_report <select name='artifacts_write_report'>{report_options}</select></label>
      {''.join(weight_controls) or '<p>No aggregate weight sliders are available for this workflow.</p>'}
      <button type='submit'>Save constrained edit</button>
    </form>
    """


def _render_validate_form(snapshot: dict[str, Any]) -> str:
    workflow_name = snapshot.get("selected_workflow_name") or ""
    validation = snapshot.get("validation") or {}
    status = "valid" if validation.get("ok") else "invalid"
    errors = "".join(f"<li>{_escape(error)}</li>" for error in validation.get("errors", []))
    return f"""
    <h2>4. Validate</h2>
    <p>Current validation: <strong>{_escape(status)}</strong></p>
    <ul>{errors}</ul>
    <form method='post' action='/workbench/validate'>
      <input type='hidden' name='workflow_name' value='{_escape(workflow_name)}'>
      <button type='submit'>Validate workflow</button>
    </form>
    """


def _render_run_form(snapshot: dict[str, Any]) -> str:
    workflow_name = snapshot.get("selected_workflow_name") or ""
    baseline = snapshot.get("selected_run_ref") or ""
    disabled = " disabled" if not workflow_name else ""
    return f"""
    <h2>5. Run edited workflow</h2>
    <form method='post' action='/workbench/run'>
      <input type='hidden' name='workflow_name' value='{_escape(workflow_name)}'>
      <input type='hidden' name='baseline_run_ref' value='{_escape(baseline)}'>
      <p>Baseline for compare: <code>{_escape(baseline or 'none')}</code></p>
      <button type='submit'{disabled}>Validate, run, and compare</button>
    </form>
    """


def _render_canvas(canvas: dict[str, Any]) -> str:
    nodes = canvas.get("nodes", [])
    if not nodes:
        return "<p>No workflow graph available.</p>"
    by_name = {node["name"]: node for node in nodes}
    width = max((int(node["x"]) for node in nodes), default=0) + 210
    height = max((int(node["y"]) for node in nodes), default=0) + 105
    edge_lines = []
    for edge in canvas.get("edges", []):
        source = by_name.get(edge.get("from"))
        target = by_name.get(edge.get("to"))
        if not source or not target:
            continue
        x1 = int(source["x"]) + 170
        y1 = int(source["y"]) + 38
        x2 = int(target["x"])
        y2 = int(target["y"]) + 38
        label = edge.get("label")
        edge_lines.append(f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' stroke='#8c959f' marker-end='url(#arrow)' />")
        if label:
            edge_lines.append(f"<text x='{(x1 + x2) // 2}' y='{(y1 + y2) // 2 - 4}' font-size='11'>{_escape(label)}</text>")
    node_cards = []
    for node in nodes:
        status_class = _status_class(node.get("status"))
        node_cards.append(
            f"<g class='node {status_class}'>"
            f"<rect x='{_escape(node['x'])}' y='{_escape(node['y'])}' width='170' height='76' rx='10'></rect>"
            f"<text x='{int(node['x']) + 10}' y='{int(node['y']) + 22}' font-weight='700'>{_escape(node['name'])}</text>"
            f"<text x='{int(node['x']) + 10}' y='{int(node['y']) + 43}'>{_escape(node['kind'])}</text>"
            f"<text x='{int(node['x']) + 10}' y='{int(node['y']) + 63}'>{_escape(node['status'])}</text>"
            "</g>"
        )
    return f"""
    <div class='canvas-wrap'>
      <svg viewBox='0 0 {width} {height}' role='img' aria-label='Workflow graph canvas'>
        <defs><marker id='arrow' markerWidth='10' markerHeight='10' refX='8' refY='3' orient='auto'><path d='M0,0 L0,6 L9,3 z' fill='#8c959f' /></marker></defs>
        {''.join(edge_lines)}
        {''.join(node_cards)}
      </svg>
    </div>
    """


def _render_node_table(canvas: dict[str, Any]) -> str:
    rows = []
    for node in canvas.get("nodes", []):
        rows.append(
            "<tr>"
            f"<td>{_escape(node.get('name'))}</td>"
            f"<td>{_escape(node.get('kind'))}</td>"
            f"<td>{_escape(node.get('status'))}</td>"
            f"<td>{_escape(node.get('implementation'))}</td>"
            f"<td>{_escape(node.get('description'))}</td>"
            "</tr>"
        )
    return f"""
    <table>
      <thead><tr><th>Node</th><th>Kind</th><th>Run status</th><th>Implementation</th><th>Description</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    """


def _render_compare(snapshot: dict[str, Any]) -> str:
    rows = []
    for row in snapshot.get("compare_rows", []):
        rows.append(
            "<tr>"
            f"<td>{_escape(row.get('metric'))}</td>"
            f"<td>{_escape(row.get('left'))}</td>"
            f"<td>{_escape(row.get('right'))}</td>"
            f"<td>{_escape(row.get('interpretation'))}</td>"
            "</tr>"
        )
    if not rows:
        return "<section><h2>6. Compare outputs</h2><p>Run an edited workflow with a selected baseline run to compare outputs.</p></section>"
    return f"""
    <section>
      <h2>6. Compare outputs</h2>
      <p>Baseline: <code>{_escape(snapshot.get('compare_ref'))}</code> vs selected run <code>{_escape(snapshot.get('selected_run_ref'))}</code></p>
      <table>
        <thead><tr><th>Metric</th><th>Baseline</th><th>Edited run</th><th>Interpretation</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </section>
    """


def _notice(kind: str, text: str | None) -> str:
    if not text:
        return ""
    return f"<div class='notice {kind}'>{_escape(text)}</div>"


def _status_class(status: Any) -> str:
    text = str(status or "not-run")
    if text == "completed":
        return "completed"
    if text == "failed":
        return "failed"
    return "pending"


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>{_escape(title)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.5; color: #24292f; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
    th, td {{ border: 1px solid #ddd; padding: 0.5rem; vertical-align: top; }}
    th {{ background: #f6f8fa; text-align: left; }}
    code, pre {{ background: #f6f8fa; padding: 0.2rem 0.35rem; border-radius: 4px; }}
    label {{ display: block; margin: 0.5rem 0; }}
    input, select, button {{ font: inherit; margin-left: 0.25rem; }}
    button {{ padding: 0.35rem 0.6rem; }}
    section {{ margin: 1.5rem 0; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1rem; }}
    .grid > div {{ border: 1px solid #d0d7de; border-radius: 8px; padding: 1rem; }}
    .notice {{ border-radius: 8px; padding: 0.75rem 1rem; margin: 1rem 0; }}
    .notice.error {{ border: 1px solid #cf222e; background: #ffebe9; }}
    .notice.message {{ border: 1px solid #1a7f37; background: #dafbe1; }}
    .canvas-wrap {{ overflow-x: auto; border: 1px solid #d0d7de; border-radius: 8px; background: #f6f8fa; }}
    svg {{ min-width: 720px; width: 100%; height: auto; }}
    .node rect {{ stroke-width: 2; fill: #fff; }}
    .node.completed rect {{ stroke: #1a7f37; }}
    .node.failed rect {{ stroke: #cf222e; }}
    .node.pending rect {{ stroke: #8c959f; }}
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


def _workflow_label(workflow: dict[str, Any]) -> str:
    if not workflow:
        return "n/a"
    name = workflow.get("name") or workflow.get("title") or "workflow"
    kind = workflow.get("kind")
    if kind:
        return f"{name} [{kind}]"
    return str(name)


__all__ = [
    "create_web_server",
    "render_index_html",
    "render_run_html",
    "render_workbench_html",
    "run_detail",
    "web_snapshot",
]
