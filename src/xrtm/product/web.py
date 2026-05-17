"""Local WebUI shell and JSON API over XRTM product artifacts."""

from __future__ import annotations

import json
import re
import tempfile
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from mimetypes import guess_type
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlencode, urlparse

from xrtm.product import launch as launch_module
from xrtm.product.artifacts import ArtifactStore
from xrtm.product.doctor import doctor_snapshot
from xrtm.product.history import export_run
from xrtm.product.monitoring import list_monitors, load_monitor, run_monitor_once, set_monitor_status, start_monitor
from xrtm.product.observability import MonitorThresholds
from xrtm.product.pipeline import PipelineResult
from xrtm.product.profiles import DEFAULT_PROFILES_DIR, ProfileStore, WorkflowProfile, starter_profile
from xrtm.product.providers import (
    CODING_AGENT_CLI_CATEGORY,
    OPENAI_COMPATIBLE_CATEGORY,
    PROVIDER_FREE_VALIDATION_MODE,
    local_llm_status,
    provider_runtime_metadata,
)
from xrtm.product.read_models import list_monitor_records, list_run_records, read_run_detail
from xrtm.product.reports import render_html_report
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
from xrtm.version import __version__

_STATIC_ROOT = Path(__file__).with_name("webui_static")
_APP_ROUTES = [
    re.compile(r"^/$"),
    re.compile(r"^/start$"),
    re.compile(r"^/runs$"),
    re.compile(r"^/playground$"),
    re.compile(r"^/operations$"),
    re.compile(r"^/advanced$"),
    re.compile(r"^/workbench$"),
    re.compile(r"^/workflows/[^/]+$"),
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
            if path == "/api/health":
                self._send_json(doctor_snapshot(runs_dir=self.runs_dir))
                return
            if path == "/api/providers/status":
                self._send_json(_provider_status_snapshot())
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
            if path == "/api/playground":
                self._send_json(self.state_store.playground_snapshot(runs_dir=self.runs_dir, registry=self._registry()))
                return
            if path == "/api/authoring/catalog":
                self._send_json(self.state_store.authoring_catalog(registry=self._registry()))
                return
            if path == "/api/profiles":
                self._send_json(
                    {
                        "root": str(self._profiles_dir()),
                        "items": [_profile_payload(profile) for profile in ProfileStore(self._profiles_dir()).list_profiles()],
                    }
                )
                return
            if path == "/api/monitors":
                self._send_json({"items": list_monitors(self.runs_dir)})
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
            export_match = re.match(r"^/api/runs/([^/]+)/export$", path)
            if export_match:
                self._send_run_export(export_match.group(1), parsed.query)
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
            artifacts_match = re.match(r"^/api/artifacts/([^/]+)$", path)
            if artifacts_match:
                self._send_json(_artifact_snapshot(self.runs_dir, artifacts_match.group(1)))
                return
            monitor_match = re.match(r"^/api/monitors/([^/]+)$", path)
            if monitor_match:
                self._send_json(_monitor_snapshot(self.runs_dir, monitor_match.group(1)))
                return
            workflow_explain_match = re.match(r"^/api/workflows/([^/]+)/explain$", path)
            if workflow_explain_match:
                self._send_json(
                    {
                        "workflow_name": workflow_explain_match.group(1),
                        "explanation": launch_module.explain_registered_workflow(
                            workflow_explain_match.group(1),
                            workflows_dir=self.workflows_dir,
                        ),
                    }
                )
                return
            profile_match = re.match(r"^/api/profiles/([^/]+)$", path)
            if profile_match:
                profile = ProfileStore(self._profiles_dir()).load(profile_match.group(1))
                self._send_json(
                    {
                        "path": str(ProfileStore(self._profiles_dir()).path_for(profile.name)),
                        "profile": _profile_payload(profile),
                    }
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
            if path == "/api/start":
                payload = self._read_json()
                result = launch_module.run_start_quickstart(
                    limit=_optional_json_int(payload, "limit", default=launch_module.DEFAULT_DEMO_LIMIT),
                    runs_dir=self.runs_dir,
                    user=_optional_json_value(payload, "user"),
                )
                self._send_json(_run_result_payload(result), status=HTTPStatus.CREATED)
                return
            if path == "/api/runs":
                payload = self._read_json()
                workflow_name = _optional_json_value(payload, "workflow_name")
                baseline_run_id = _optional_json_value(payload, "baseline_run_id")
                if workflow_name:
                    result = launch_module.run_registered_workflow(
                        workflow_name,
                        workflows_dir=self.workflows_dir,
                        runs_dir=self.runs_dir,
                        limit=_optional_json_int(payload, "limit"),
                        provider=_optional_json_value(payload, "provider"),
                        base_url=_optional_json_value(payload, "base_url"),
                        model=_optional_json_value(payload, "model"),
                        api_key=_optional_json_value(payload, "api_key"),
                        max_tokens=_optional_json_int(payload, "max_tokens"),
                        write_report=_optional_json_bool(payload, "write_report", default=True),
                        user=_optional_json_value(payload, "user"),
                    )
                    self._send_json(_run_result_payload(result, baseline_run_id=baseline_run_id), status=HTTPStatus.CREATED)
                    return
                provider = _optional_json_value(payload, "provider") or "mock"
                result = launch_module.run_demo_workflow(
                    provider=provider,
                    limit=_optional_json_int(payload, "limit", default=launch_module.DEFAULT_DEMO_LIMIT),
                    runs_dir=self.runs_dir,
                    base_url=_optional_json_value(payload, "base_url"),
                    model=_optional_json_value(payload, "model"),
                    api_key=_optional_json_value(payload, "api_key"),
                    max_tokens=_optional_json_int(payload, "max_tokens", default=launch_module.DEFAULT_MAX_TOKENS),
                    write_report=_optional_json_bool(payload, "write_report", default=True),
                    user=_optional_json_value(payload, "user"),
                    command="xrtm demo",
                    name="demo-provider-free" if provider == "mock" else "demo-local-llm",
                    title="XRTM Demo",
                    description="Bounded product demo over the released real-binary corpus.",
                )
                self._send_json(_run_result_payload(result, baseline_run_id=baseline_run_id), status=HTTPStatus.CREATED)
                return
            if path == "/api/drafts":
                payload = self._read_json()
                draft = self.state_store.create_draft_session(
                    registry=self._registry(),
                    runs_dir=self.runs_dir,
                    source_workflow_name=_optional_json_value(payload, "source_workflow_name"),
                    baseline_run_id=_optional_json_value(payload, "baseline_run_id"),
                    draft_workflow_name=_optional_json_value(payload, "draft_workflow_name"),
                    creation_mode=_optional_json_value(payload, "creation_mode") or "clone",
                    template_id=_optional_json_value(payload, "template_id"),
                    title=_optional_json_value(payload, "title"),
                    description=_optional_json_value(payload, "description"),
                )
                self._send_json(draft, status=HTTPStatus.CREATED)
                return
            if path == "/api/playground/run":
                payload = self._read_json()
                self._send_json(
                    self.state_store.run_playground_session(
                        registry=self._registry(),
                        runs_dir=self.runs_dir,
                        values=payload,
                    ),
                    status=HTTPStatus.CREATED,
                )
                return
            playground_workflow_save = re.match(r"^/api/playground/runs/([^/]+)/save-workflow$", path)
            if playground_workflow_save:
                payload = self._read_json()
                result = launch_module.save_sandbox_workflow(
                    _safe_run_dir(self.runs_dir, playground_workflow_save.group(1)),
                    workflow_name=_optional_json_value(payload, "workflow_name"),
                    workflows_dir=self.workflows_dir,
                    overwrite=_optional_json_bool(payload, "overwrite", default=False),
                )
                self._send_json(result, status=HTTPStatus.CREATED)
                return
            playground_profile_save = re.match(r"^/api/playground/runs/([^/]+)/save-profile$", path)
            if playground_profile_save:
                payload = self._read_json()
                result = launch_module.save_sandbox_profile(
                    _safe_run_dir(self.runs_dir, playground_profile_save.group(1)),
                    profile_name=_required_json_value(payload, "profile_name"),
                    profiles_dir=self._profiles_dir(),
                    workflows_dir=self.workflows_dir,
                    workflow_name=_optional_json_value(payload, "workflow_name"),
                    overwrite=_optional_json_bool(payload, "overwrite", default=False),
                )
                self._send_json(result, status=HTTPStatus.CREATED)
                return
            if path == "/api/profiles":
                payload = self._read_json()
                store = ProfileStore(self._profiles_dir())
                name = _required_json_value(payload, "name")
                if _optional_json_value(payload, "template") == "starter":
                    profile = starter_profile(name, runs_dir=self.runs_dir, user=_optional_json_value(payload, "user"))
                else:
                    profile = WorkflowProfile(
                        name=name,
                        workflow_name=_optional_json_value(payload, "workflow_name"),
                        provider=_optional_json_value(payload, "provider") or "mock",
                        limit=_optional_json_int(payload, "limit", default=launch_module.DEFAULT_DEMO_LIMIT),
                        runs_dir=str(_optional_json_path(payload, "runs_dir") or self.runs_dir),
                        base_url=_optional_json_value(payload, "base_url"),
                        model=_optional_json_value(payload, "model"),
                        max_tokens=_optional_json_int(payload, "max_tokens", default=launch_module.DEFAULT_MAX_TOKENS),
                        write_report=_optional_json_bool(payload, "write_report", default=True),
                        user=_optional_json_value(payload, "user"),
                    )
                path_written = store.create(profile, overwrite=_optional_json_bool(payload, "overwrite", default=False))
                self._send_json({"path": str(path_written), "profile": _profile_payload(profile)}, status=HTTPStatus.CREATED)
                return
            if path == "/api/monitors":
                payload = self._read_json()
                run = start_monitor(
                    runs_dir=self.runs_dir,
                    limit=_optional_json_int(payload, "limit", default=launch_module.DEFAULT_DEMO_LIMIT),
                    provider=_optional_json_value(payload, "provider") or "mock",
                    base_url=_optional_json_value(payload, "base_url"),
                    model=_optional_json_value(payload, "model"),
                    api_key=_optional_json_value(payload, "api_key"),
                    thresholds=MonitorThresholds.from_payload(payload.get("thresholds"))
                    if payload.get("thresholds") is not None
                    else None,
                )
                self._send_json(_monitor_snapshot(self.runs_dir, run.run_id), status=HTTPStatus.CREATED)
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
            run_report = re.match(r"^/api/runs/([^/]+)/report$", path)
            if run_report:
                report_path = render_html_report(_safe_run_dir(self.runs_dir, run_report.group(1)))
                self._send_json(
                    {
                        "run_id": run_report.group(1),
                        "report_path": str(report_path),
                        "href": f"/runs/{run_report.group(1)}/report",
                    }
                )
                return
            profile_run = re.match(r"^/api/profiles/([^/]+)/run$", path)
            if profile_run:
                result = launch_module.run_saved_profile(profile_run.group(1), profiles_dir=self._profiles_dir())
                self._send_json(_run_result_payload(result), status=HTTPStatus.CREATED)
                return
            monitor_run_once = re.match(r"^/api/monitors/([^/]+)/run-once$", path)
            if monitor_run_once:
                payload = self._read_json()
                monitor = run_monitor_once(
                    run_dir=_safe_run_dir(self.runs_dir, monitor_run_once.group(1)),
                    provider=_optional_json_value(payload, "provider"),
                    base_url=_optional_json_value(payload, "base_url"),
                    model=_optional_json_value(payload, "model"),
                    api_key=_optional_json_value(payload, "api_key"),
                    max_tokens=_optional_json_int(payload, "max_tokens", default=launch_module.DEFAULT_MAX_TOKENS),
                )
                self._send_json({"run_id": monitor_run_once.group(1), "monitor": monitor})
                return
            monitor_status = re.match(r"^/api/monitors/([^/]+)/(pause|resume|halt)$", path)
            if monitor_status:
                status = {"pause": "paused", "resume": "running", "halt": "halted"}[monitor_status.group(2)]
                monitor = set_monitor_status(_safe_run_dir(self.runs_dir, monitor_status.group(1)), status)
                self._send_json({"run_id": monitor_status.group(1), "monitor": monitor})
                return
            if path == "/api/artifacts/cleanup-preview":
                payload = self._read_json()
                keep = _optional_json_int(payload, "keep", default=5)
                assert keep is not None
                self._send_json(_cleanup_payload(keep, ArtifactStore.cleanup_runs(runs_dir=self.runs_dir, keep=keep, dry_run=True)))
                return
            if path == "/api/artifacts/cleanup":
                payload = self._read_json()
                if _optional_json_value(payload, "confirm") != "delete":
                    raise WorkbenchInputError("confirm must be 'delete'")
                keep = _optional_json_int(payload, "keep", default=5)
                assert keep is not None
                candidates = ArtifactStore.cleanup_runs(runs_dir=self.runs_dir, keep=keep, dry_run=True)
                ArtifactStore.cleanup_runs(runs_dir=self.runs_dir, keep=keep, dry_run=False)
                self._send_json(_cleanup_payload(keep, candidates))
                return
            workflow_validate = re.match(r"^/api/workflows/([^/]+)/validate$", path)
            if workflow_validate:
                blueprint = launch_module.validate_registered_workflow(
                    workflow_validate.group(1),
                    workflows_dir=self.workflows_dir,
                )
                self._send_json(
                    {
                        "ok": True,
                        "workflow_name": blueprint.name,
                        "schema_version": blueprint.schema_version,
                        "title": blueprint.title,
                    }
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
            if path == "/api/playground":
                payload = self._read_json()
                self._send_json(
                    self.state_store.update_playground_session(
                        registry=self._registry(),
                        runs_dir=self.runs_dir,
                        values=payload,
                    )
                )
                return
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

    def _profiles_dir(self) -> Path:
        return _profiles_dir_from_workflows(self.workflows_dir)

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

    def _send_bytes(
        self,
        body: bytes,
        *,
        content_type: str,
        filename: str | None = None,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(body)

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

    def _send_run_export(self, run_id: str, query_string: str) -> None:
        export_format = _export_format_from_query(query_string)
        with tempfile.TemporaryDirectory(prefix="xrtm-webui-export-") as temp_dir:
            output_path = Path(temp_dir) / f"{run_id}.{export_format}"
            export_run(_safe_run_dir(self.runs_dir, run_id), output_path, format=export_format)
            content_type = "text/csv; charset=utf-8" if export_format == "csv" else "application/json; charset=utf-8"
            self._send_bytes(output_path.read_bytes(), content_type=content_type, filename=output_path.name)

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
          <div class='boot-copy-stack'>
            <div class='boot-title-group'>
              <span class='boot-badge'>XRTM WebUI</span>
              <span class='version-pill'>v{__version__}</span>
              <span class='shell-trust-pill'>Local-only shell</span>
            </div>
            <h1>Local forecasting cockpit</h1>
            <p class='shell-copy'>Loading the local-first app shell…</p>
          </div>
          <div class='boot-nav-stack'>
            <span class='boot-badge'>Primary lanes</span>
            <p class='boot-route-strip'>Overview · Start · Runs · Playground · Operations · Workbench</p>
          </div>
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


def _profiles_dir_from_workflows(workflows_dir: Path) -> Path:
    resolved = workflows_dir if workflows_dir.is_absolute() else Path.cwd() / workflows_dir
    if resolved.name == "workflows":
        return resolved.parent / "profiles"
    if resolved == Path.cwd():
        return resolved / DEFAULT_PROFILES_DIR
    return resolved.parent / "profiles"


def _profile_payload(profile: WorkflowProfile) -> dict[str, Any]:
    return profile.to_json_dict()


def _run_result_payload(result: PipelineResult, *, baseline_run_id: str | None = None) -> dict[str, Any]:
    run_id = getattr(result, "run_id", result.run.run_id)
    payload = {
        "run_id": run_id,
        "run_dir": str(result.run.run_dir),
        "status": result.run.status,
        "provider": result.run.provider,
        "command": result.run.command,
        "href": f"/runs/{run_id}",
        "report_href": f"/runs/{run_id}/report",
        "report_available": (result.run.run_dir / "report.html").exists(),
    }
    if baseline_run_id:
        payload["compare"] = {
            "baseline_run_id": baseline_run_id,
            "candidate_run_id": run_id,
            "href": f"/runs/{run_id}/compare/{baseline_run_id}",
        }
    return payload


def _monitor_snapshot(runs_dir: Path, run_id: str) -> dict[str, Any]:
    run_dir = _safe_run_dir(runs_dir, run_id)
    detail = read_run_detail(run_dir)
    return {
        "run_id": run_id,
        "run": detail.get("run", {}),
        "summary": detail.get("summary", {}),
        "monitor": load_monitor(run_dir),
        "events": detail.get("events", []),
        "questions": detail.get("questions", []),
        "forecasts": detail.get("forecasts", []),
    }


def _artifact_snapshot(runs_dir: Path, run_id: str) -> dict[str, Any]:
    run_dir = _safe_run_dir(runs_dir, run_id)
    detail = read_run_detail(run_dir)
    run = detail.get("run", {})
    artifact_rows = []
    for name, location in sorted((run.get("artifacts") or {}).items()):
        path = Path(location)
        artifact_rows.append(
            {
                "name": name,
                "path": str(path),
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() and path.is_file() else None,
            }
        )
    return {
        "run_id": run_id,
        "run": run,
        "summary": detail.get("summary", {}),
        "artifact_count": len(artifact_rows),
        "artifacts": artifact_rows,
    }


def _cleanup_payload(keep: int, candidates: list[Path]) -> dict[str, Any]:
    return {
        "keep": keep,
        "count": len(candidates),
        "items": [{"run_id": candidate.name, "path": str(candidate)} for candidate in candidates],
    }


def _provider_status_snapshot() -> dict[str, Any]:
    return {
        "first_class_categories": [OPENAI_COMPATIBLE_CATEGORY, CODING_AGENT_CLI_CATEGORY],
        "provider_free": {
            "label": "Provider-free deterministic baseline",
            "runtime": provider_runtime_metadata("mock"),
            "validation_mode": PROVIDER_FREE_VALIDATION_MODE,
            "ready": True,
        },
        "local_llm": local_llm_status(),
    }


def _export_format_from_query(query_string: str) -> str:
    parsed = parse_qs(query_string)
    export_format = _single_query_value(parsed, "format") or "json"
    if export_format not in {"json", "csv"}:
        raise ValueError("export format must be 'json' or 'csv'")
    return export_format



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


def _optional_json_int(payload: dict[str, Any], key: str, *, default: int | None = None) -> int | None:
    value = payload.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        raise WorkbenchInputError(f"{key} must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise WorkbenchInputError(f"{key} must be an integer") from exc


def _optional_json_bool(payload: dict[str, Any], key: str, *, default: bool) -> bool:
    value = payload.get(key)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise WorkbenchInputError(f"{key} must be a boolean")
    return value


def _optional_json_path(payload: dict[str, Any], key: str) -> Path | None:
    value = _optional_json_value(payload, key)
    return Path(value) if value else None


__all__ = [
    "create_web_server",
    "render_app_shell_html",
    "render_index_html",
    "render_run_html",
    "render_workbench_html",
    "run_detail",
    "web_snapshot",
]
