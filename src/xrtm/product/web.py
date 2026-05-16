"""Local WebUI shell and JSON API over XRTM product artifacts."""

from __future__ import annotations

import json
import re
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from mimetypes import guess_type
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlencode, urlparse

from xrtm.product.read_models import list_monitor_records, list_run_records, read_run_detail
from xrtm.product.webui_state import WebUIStateStore, default_app_db_path
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

_STATIC_ROOT = Path(__file__).with_name("webui_static")
_APP_ROUTES = [
    re.compile(r"^/$"),
    re.compile(r"^/runs$"),
    re.compile(r"^/workbench$"),
    re.compile(r"^/runs/[^/]+$"),
    re.compile(r"^/runs/[^/]+/compare/[^/]+$"),
]



def create_web_server(
    *,
    runs_dir: Path,
    host: str = "127.0.0.1",
    port: int = 8765,
    workflows_dir: Path = DEFAULT_LOCAL_WORKFLOWS_DIR,
    app_db_path: Path | None = None,
) -> ThreadingHTTPServer:
    """Create a local-only HTTP server for the React app shell and JSON API."""

    state_store = WebUIStateStore(app_db_path or default_app_db_path(workflows_dir))
    state_store.ensure_schema()
    handler = partial(WebUIHandler, runs_dir=runs_dir, workflows_dir=workflows_dir, state_store=state_store)
    return ThreadingHTTPServer((host, port), handler)


class WebUIHandler(BaseHTTPRequestHandler):
    """Serve the React shell, legacy workbench routes, and local JSON API."""

    server_version = "XRTMWebUI/0.3"

    def __init__(
        self,
        *args: Any,
        runs_dir: Path,
        workflows_dir: Path,
        state_store: WebUIStateStore,
        **kwargs: Any,
    ) -> None:
        self.runs_dir = runs_dir
        self.workflows_dir = workflows_dir
        self.state_store = state_store
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        path = unquote(parsed.path).rstrip("/") or "/"
        try:
            if path.startswith("/static/"):
                self._send_static(path.removeprefix("/static/"))
                return
            if path == "/api/app-shell":
                self._send_json(self._app_shell_snapshot())
                return
            if path == "/api/runs":
                self._send_json(
                    {
                        "items": self.state_store.list_runs(**_filters_from_query(parsed.query)),
                        "filters": _filters_from_query(parsed.query),
                    }
                )
                return
            if path == "/api/workbench":
                query = _workbench_query(parsed.query)
                self._send_json(workbench_snapshot(self.runs_dir, self.workflows_dir, **query))
                return
            if path == "/api/workflows":
                self.state_store.refresh_indexes(runs_dir=self.runs_dir, registry=self._registry())
                self._send_json({"items": self.state_store.list_workflows()})
                return
            if path.startswith("/api/drafts/"):
                self._handle_draft_get(path)
                return
            compare_match = re.match(r"^/api/runs/([^/]+)/compare/([^/]+)$", path)
            if compare_match:
                candidate_run_id, baseline_run_id = compare_match.groups()
                self._send_json(
                    self.state_store.compare_snapshot(
                        runs_dir=self.runs_dir,
                        candidate_run_id=candidate_run_id,
                        baseline_run_id=baseline_run_id,
                    )
                )
                return
            run_match = re.match(r"^/api/runs/([^/]+)$", path)
            if run_match:
                self._send_json(
                    self.state_store.run_detail_snapshot(
                        runs_dir=self.runs_dir,
                        registry=self._registry(),
                        run_id=run_match.group(1),
                    )
                )
                return
            workflow_match = re.match(r"^/api/workflows/([^/]+)$", path)
            if workflow_match:
                self._send_json(self.state_store.workflow_detail_snapshot(self._registry(), workflow_match.group(1)))
                return
            if path.startswith("/runs/") and path.endswith("/report"):
                self._send_report(path.removeprefix("/runs/").removesuffix("/report"))
                return
            if _is_app_route(path):
                self._send_html(render_app_shell_html(initial_path=path, query_string=parsed.query))
                return
            self._send_text("Not found", status=HTTPStatus.NOT_FOUND)
        except FileNotFoundError as exc:
            self._send_text(str(exc), status=HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._send_text(str(exc), status=HTTPStatus.BAD_REQUEST)

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        path = unquote(parsed.path).rstrip("/") or "/"
        try:
            if path == "/api/drafts":
                payload = self._read_json()
                draft = self.state_store.create_draft_session(
                    registry=self._registry(),
                    runs_dir=self.runs_dir,
                    source_workflow_name=_required_json_value(payload, "source_workflow_name"),
                    baseline_run_id=_optional_json_value(payload, "baseline_run_id"),
                    draft_workflow_name=_optional_json_value(payload, "draft_workflow_name"),
                )
                self._send_json(draft, status=HTTPStatus.CREATED)
                return
            draft_validate = re.match(r"^/api/drafts/([^/]+)/validate$", path)
            if draft_validate:
                self._send_json(
                    self.state_store.validate_draft_session(
                        draft_id=draft_validate.group(1),
                        registry=self._registry(),
                        runs_dir=self.runs_dir,
                    )
                )
                return
            draft_run = re.match(r"^/api/drafts/([^/]+)/run$", path)
            if draft_run:
                self._send_json(
                    self.state_store.run_draft_session(
                        draft_id=draft_run.group(1),
                        registry=self._registry(),
                        runs_dir=self.runs_dir,
                    )
                )
                return
            if path in {"/workbench/clone", "/workbench/edit", "/workbench/validate", "/workbench/run"}:
                self._handle_legacy_form_post(path)
                return
            self._send_text("Not found", status=HTTPStatus.NOT_FOUND)
        except (WorkbenchInputError, FileExistsError, FileNotFoundError, ValueError) as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # pragma: no cover - defensive server boundary
            self._send_json({"error": f"Run failed: {exc}"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_PATCH(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        path = unquote(parsed.path).rstrip("/") or "/"
        try:
            draft_match = re.match(r"^/api/drafts/([^/]+)$", path)
            if draft_match:
                payload = self._read_json()
                values = payload.get("values") if isinstance(payload.get("values"), dict) else payload
                self._send_json(
                    self.state_store.patch_draft_session(
                        draft_id=draft_match.group(1),
                        registry=self._registry(),
                        runs_dir=self.runs_dir,
                        values=values,
                    )
                )
                return
            self._send_text("Not found", status=HTTPStatus.NOT_FOUND)
        except (WorkbenchInputError, FileNotFoundError, ValueError) as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        return

    def _app_shell_snapshot(self) -> dict[str, Any]:
        return self.state_store.app_shell_snapshot(runs_dir=self.runs_dir, registry=self._registry())

    def _registry(self):
        return workflow_registry_for(self.workflows_dir)

    def _handle_draft_get(self, path: str) -> None:
        match = re.match(r"^/api/drafts/([^/]+)$", path)
        if not match:
            self._send_text("Not found", status=HTTPStatus.NOT_FOUND)
            return
        self._send_json(
            self.state_store.get_draft_session(
                draft_id=match.group(1),
                registry=self._registry(),
                runs_dir=self.runs_dir,
            )
        )

    def _handle_legacy_form_post(self, path: str) -> None:
        form = self._read_form()
        registry = self._registry()
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
            draft = self.state_store.create_draft_session(
                registry=registry,
                runs_dir=self.runs_dir,
                source_workflow_name=target_name,
                draft_workflow_name=target_name,
            )
            self._redirect("/workbench?" + urlencode({"draft": draft["id"]}))
            return
        if path == "/workbench/edit":
            workflow_name = _required_form_value(form, "workflow_name")
            edit_values = {key: value for key, value in form.items() if key != "workflow_name"}
            updated = apply_workbench_edit(registry, workflow_name=workflow_name, values=edit_values)
            self._redirect("/workbench?" + urlencode({"workflow": updated.name}))
            return
        if path == "/workbench/validate":
            workflow_name = _required_form_value(form, "workflow_name")
            report = validate_workbench_workflow(registry, workflow_name)
            if not report["ok"]:
                raise WorkbenchInputError("; ".join(report["errors"]))
            self._redirect("/workbench?" + urlencode({"workflow": workflow_name, "validated": "true"}))
            return
        if path == "/workbench/run":
            workflow_name = _required_form_value(form, "workflow_name")
            baseline_run_ref = _optional_form_value(form, "baseline_run_ref")
            result = run_workbench_workflow(
                registry,
                workflow_name=workflow_name,
                runs_dir=self.runs_dir,
                baseline_run_ref=baseline_run_ref,
            )
            query = {"workflow": workflow_name, "run": result.run_id}
            if result.baseline_run_id:
                query["compare"] = result.baseline_run_id
            self._redirect("/workbench?" + urlencode(query))
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

    def _send_static(self, relative_path: str) -> None:
        path = (_STATIC_ROOT / relative_path).resolve()
        try:
            path.relative_to(_STATIC_ROOT.resolve())
        except ValueError as exc:
            raise ValueError("invalid static path") from exc
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"static asset does not exist: {relative_path}")
        mime_type = guess_type(path.name)[0] or "application/octet-stream"
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise WorkbenchInputError("invalid Content-Length") from exc
        if length < 0 or length > 262144:
            raise WorkbenchInputError("request payload is too large")
        if length == 0:
            return {}
        body = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise WorkbenchInputError("request body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise WorkbenchInputError("request body must be a JSON object")
        return payload

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
    """Return dashboard state shared by WebUI route tests and CLI smoke."""

    from xrtm.product.providers import local_llm_status

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
    """Render the Overview shell page."""

    return render_app_shell_html(initial_path="/", query_string=query_string)



def render_workbench_html(
    runs_dir: Path,
    workflows_dir: Path,
    *,
    query_string: str = "",
    error: str | None = None,
) -> str:
    """Render the Workbench shell page."""

    del runs_dir, workflows_dir
    return render_app_shell_html(initial_path="/workbench", query_string=query_string, error=error)



def render_run_html(runs_dir: Path, run_id: str) -> str:
    """Render the Run detail shell page."""

    del runs_dir
    return render_app_shell_html(initial_path=f"/runs/{run_id}")



def render_app_shell_html(*, initial_path: str, query_string: str = "", error: str | None = None) -> str:
    bootstrap = {
        "api_root": "/api",
        "initial_path": initial_path,
        "initial_query": query_string,
        "initial_error": error,
    }
    bootstrap_json = json.dumps(bootstrap).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang='en'>
  <head>
    <meta charset='utf-8'>
    <meta name='viewport' content='width=device-width, initial-scale=1'>
    <title>XRTM WebUI</title>
    <link rel='stylesheet' href='/static/app.css'>
  </head>
  <body>
    <div id='root'>
      <main class='boot-shell'>
        <header class='boot-header'>
          <span class='boot-badge'>XRTM WebUI</span>
          <h1>Overview · Runs · Workbench</h1>
          <p>Loading the local-first app shell…</p>
        </header>
        <noscript>This WebUI shell needs JavaScript enabled.</noscript>
      </main>
    </div>
    <script>window.__XRTM_WEBUI_BOOTSTRAP__ = {bootstrap_json};</script>
    <script src='/static/vendor/react.production.min.js'></script>
    <script src='/static/vendor/react-dom.production.min.js'></script>
    <script src='/static/app.js'></script>
  </body>
</html>
"""



def _is_app_route(path: str) -> bool:
    return any(pattern.match(path) for pattern in _APP_ROUTES)



def _safe_run_dir(runs_dir: Path, run_id: str) -> Path:
    from xrtm.product.history import resolve_run_dir

    return resolve_run_dir(runs_dir, run_id)



def _filters_from_query(query_string: str) -> dict[str, str | None]:
    parsed = parse_qs(query_string)
    return {
        "status": _single_query_value(parsed, "status"),
        "provider": _single_query_value(parsed, "provider"),
        "query": _single_query_value(parsed, "q") or _single_query_value(parsed, "query"),
    }



def _workbench_query(query_string: str) -> dict[str, str | None]:
    parsed = parse_qs(query_string)
    return {
        "run_ref": _single_query_value(parsed, "run"),
        "workflow_name": _single_query_value(parsed, "workflow"),
        "compare_ref": _single_query_value(parsed, "compare"),
    }



def _single_query_value(values: dict[str, list[str]], key: str) -> str | None:
    entries = values.get(key)
    if not entries:
        return None
    return entries[0] or None



def _required_form_value(values: dict[str, str], key: str) -> str:
    value = values.get(key, "").strip()
    if not value:
        raise WorkbenchInputError(f"{key} is required")
    return value



def _optional_form_value(values: dict[str, str], key: str) -> str | None:
    value = values.get(key, "").strip()
    return value or None



def _required_json_value(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise WorkbenchInputError(f"{key} is required")
    return value.strip()



def _optional_json_value(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise WorkbenchInputError(f"{key} must be a string when provided")
    value = value.strip()
    return value or None


__all__ = [
    "create_web_server",
    "render_app_shell_html",
    "render_index_html",
    "render_run_html",
    "render_workbench_html",
    "run_detail",
    "web_snapshot",
]
