"""Local-first SQLite-backed state and API read models for the WebUI shell."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from xrtm import __version__
from xrtm.product.history import compare_runs, resolve_run_dir
from xrtm.product.providers import local_llm_status
from xrtm.product.read_models import list_run_records, read_run_detail
from xrtm.product.workbench import (
    WorkbenchInputError,
    clone_workflow_for_edit,
    preview_workbench_edit,
    safe_edit_model,
    workflow_canvas,
)
from xrtm.product.workflow_runner import run_workflow_blueprint
from xrtm.product.workflows import WorkflowBlueprint, WorkflowRegistry

DEFAULT_APP_DB_NAME = "app-state.db"
COMPARE_CACHE_SCHEMA_VERSION = "xrtm.webui.compare.v2"


class WebUIStateStore:
    """Persist local app state while keeping runs and workflows file-backed."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def ensure_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS workflow_index (
                    name TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    runtime_provider TEXT NOT NULL,
                    question_limit INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    workflow_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS run_index (
                    run_id TEXT PRIMARY KEY,
                    status TEXT,
                    provider TEXT,
                    workflow_name TEXT,
                    updated_at TEXT,
                    search_text TEXT NOT NULL,
                    indexed_at TEXT NOT NULL,
                    run_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS draft_sessions (
                    id TEXT PRIMARY KEY,
                    source_workflow_name TEXT NOT NULL,
                    draft_workflow_name TEXT NOT NULL,
                    baseline_run_id TEXT,
                    status TEXT NOT NULL,
                    last_run_id TEXT,
                    revision INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS draft_values (
                    draft_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    PRIMARY KEY (draft_id, key)
                );
                CREATE TABLE IF NOT EXISTS validation_snapshots (
                    draft_id TEXT PRIMARY KEY,
                    revision INTEGER NOT NULL,
                    ok INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    validated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS compare_cache (
                    candidate_run_id TEXT NOT NULL,
                    baseline_run_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (candidate_run_id, baseline_run_id)
                );
                CREATE TABLE IF NOT EXISTS ui_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def refresh_indexes(self, *, runs_dir: Path, registry: WorkflowRegistry) -> None:
        self.ensure_schema()
        now = _utc_now()
        workflows = registry.list_workflows()
        runs = list_run_records(runs_dir)
        with self._connect() as connection:
            connection.execute("DELETE FROM workflow_index")
            connection.executemany(
                """
                INSERT INTO workflow_index (
                    name, source, title, runtime_provider, question_limit, updated_at, workflow_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        workflow.name,
                        workflow.source,
                        workflow.title,
                        workflow.runtime_provider,
                        workflow.question_limit,
                        now,
                        _json_dump(workflow.__dict__),
                    )
                    for workflow in workflows
                ],
            )
            connection.execute("DELETE FROM run_index")
            connection.executemany(
                """
                INSERT INTO run_index (
                    run_id, status, provider, workflow_name, updated_at, search_text, indexed_at, run_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        str(run.get("run_id")),
                        _string_or_none(run.get("status")),
                        _string_or_none(run.get("provider")),
                        _string_or_none(_mapping(run.get("workflow")).get("name")),
                        _string_or_none(run.get("updated_at")),
                        _run_search_text(run),
                        now,
                        _json_dump(run),
                    )
                    for run in runs
                    if run.get("run_id") is not None
                ],
            )

    def app_shell_snapshot(self, *, runs_dir: Path, registry: WorkflowRegistry) -> dict[str, Any]:
        self.refresh_indexes(runs_dir=runs_dir, registry=registry)
        runs = self.list_runs()
        workflows = self.list_workflows()
        latest_run = runs[0] if runs else None
        resume_target = self.resume_target(runs=runs)
        return {
            "app": {
                "name": "XRTM WebUI",
                "version": __version__,
                "nav": [
                    {"label": "Overview", "href": "/"},
                    {"label": "Start", "href": "/start"},
                    {"label": "Runs", "href": "/runs"},
                    {"label": "Operations", "href": "/operations"},
                    {"label": "Workbench", "href": "/workbench"},
                    {"label": "Advanced", "href": "/advanced"},
                ],
            },
            "environment": {
                "runs_dir": str(runs_dir),
                "workflows_dir": str(registry.local_roots[0]),
                "app_db": str(self.db_path),
                "local_llm": local_llm_status(),
            },
            "overview": {
                "hero": {
                    "title": "Local-first forecasting cockpit",
                    "summary": (
                        "Start first-success runs, inspect file-backed history, operate monitors, "
                        "and keep guided draft state in a local SQLite app database."
                    ),
                },
                "counts": {"runs": len(runs), "workflows": len(workflows)},
                "latest_run": latest_run,
                "resume_target": resume_target,
                "empty": not runs,
                "empty_state": {
                    "title": "Start from a flagship workflow",
                    "summary": (
                        "The shell is ready. Start a provider-free first run, inspect the result, "
                        "then clone a built-in workflow into a safe local draft when you are ready to iterate."
                    ),
                    "primary_cta": {"label": "Open Start", "href": "/start"},
                }
                if not runs
                else None,
            },
        }

    def list_runs(self, *, status: str | None = None, provider: str | None = None, query: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT run_json FROM run_index WHERE 1 = 1"
        parameters: list[Any] = []
        if status:
            sql += " AND status = ?"
            parameters.append(status)
        if provider:
            sql += " AND provider = ?"
            parameters.append(provider)
        if query:
            sql += " AND search_text LIKE ?"
            parameters.append(f"%{query.lower()}%")
        sql += " ORDER BY run_id DESC"
        with self._connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [_json_load(row["run_json"]) for row in rows]

    def list_workflows(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT workflow_json FROM workflow_index ORDER BY name").fetchall()
        return [_json_load(row["workflow_json"]) for row in rows]

    def workflow_detail_snapshot(self, registry: WorkflowRegistry, workflow_name: str) -> dict[str, Any]:
        summary = self._workflow_summary(registry, workflow_name)
        blueprint = registry.load(workflow_name)
        return {
            "workflow": summary,
            "blueprint": blueprint.to_json_dict(),
            "canvas": workflow_canvas(blueprint),
            "safe_edit": safe_edit_model(blueprint),
            "editable": summary["source"] == "local",
            "guided_actions": self._workflow_guided_actions(summary),
        }

    def run_detail_snapshot(self, *, runs_dir: Path, registry: WorkflowRegistry, run_id: str) -> dict[str, Any]:
        run_dir = resolve_run_dir(runs_dir, run_id)
        detail = read_run_detail(run_dir)
        run = _mapping(detail.get("run"))
        workflow = _mapping(detail.get("workflow"))
        summary = _mapping(detail.get("summary"))
        forecast_rows = _forecast_rows(detail)
        report = _report_state(run_dir, run_id, run)
        candidate_baselines = [item for item in self.list_runs() if item.get("run_id") != run_id][:5]
        self.set_ui_state("last_run_id", run_id)
        return {
            "run_id": run_id,
            "run": run,
            "workflow": workflow,
            "summary": summary,
            "hero": {
                "title": workflow.get("title") or run_id,
                "summary": _run_detail_summary(run=run, workflow=workflow, summary=summary, report=report),
            },
            "summary_cards": [
                {"label": "Forecasts", "value": summary.get("forecast_count", len(detail.get("forecasts", [])))},
                {"label": "Warnings", "value": summary.get("warning_count", 0)},
                {"label": "Errors", "value": summary.get("error_count", 0)},
                {"label": "Graph steps", "value": len(detail.get("graph_trace", []))},
            ],
            "metadata_groups": _run_metadata_groups(run=run, workflow=workflow, summary=summary),
            "result_groups": _run_result_groups(summary=summary),
            "forecast_table": {
                "rows": forecast_rows,
                "count": len(forecast_rows),
                "empty_state": {
                    "title": "No forecast rows available",
                    "body": "This run does not include forecast rows yet. Inspect the artifacts list for raw files.",
                },
            },
            "graph_trace": detail.get("graph_trace", []),
            "artifacts": {
                "report": report,
                "items": _artifact_items(run_dir, run),
                "summary": summary,
                "report_url": report.get("href"),
                "questions": detail.get("questions", []),
                "events": detail.get("events", []),
                "forecasts": detail.get("forecasts", []),
                "raw": {
                    key: value
                    for key, value in detail.items()
                    if key in {"eval", "train", "provider", "competition_submission"} and value
                },
            },
            "guided_actions": [
                {
                    "label": "Clone workflow",
                    "method": "POST",
                    "href": "/api/drafts",
                    "payload": {
                        "source_workflow_name": workflow.get("name") or "demo-provider-free",
                        "baseline_run_id": run_id,
                    },
                },
                {"label": "Back to workbench", "href": "/workbench"},
            ],
            "baseline_candidates": [
                {
                    "run_id": item.get("run_id"),
                    "label": _run_label(item),
                    "href": f"/runs/{run_id}/compare/{item.get('run_id')}",
                }
                for item in candidate_baselines
                if item.get("run_id") is not None
            ],
            "recommended_compare": self._recommended_compare_run(workflow_name=_string_or_none(workflow.get("name")), run_id=run_id),
        }

    def create_draft_session(
        self,
        *,
        registry: WorkflowRegistry,
        runs_dir: Path,
        source_workflow_name: str,
        baseline_run_id: str | None = None,
        draft_workflow_name: str | None = None,
    ) -> dict[str, Any]:
        self.refresh_indexes(runs_dir=runs_dir, registry=registry)
        summary = self._workflow_summary(registry, source_workflow_name)
        if baseline_run_id:
            resolve_run_dir(runs_dir, baseline_run_id)
        if summary["source"] == "local" and not draft_workflow_name:
            effective_name = source_workflow_name
        else:
            effective_name = draft_workflow_name or self._unique_draft_name(registry, source_workflow_name)
            clone_workflow_for_edit(
                registry,
                source_name=source_workflow_name,
                target_name=effective_name,
                overwrite=False,
            )
        blueprint = registry.load(effective_name)
        draft_id = f"draft-{uuid.uuid4().hex[:12]}"
        timestamp = _utc_now()
        values = _default_draft_values(blueprint)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO draft_sessions (
                    id, source_workflow_name, draft_workflow_name, baseline_run_id, status, last_run_id, revision, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_id,
                    source_workflow_name,
                    effective_name,
                    baseline_run_id,
                    "draft-ready",
                    None,
                    0,
                    timestamp,
                    timestamp,
                ),
            )
            self._replace_draft_values(connection, draft_id, values)
        self.set_ui_state("last_draft_id", draft_id)
        return self.get_draft_session(draft_id=draft_id, registry=registry, runs_dir=runs_dir)

    def get_draft_session(self, *, draft_id: str, registry: WorkflowRegistry, runs_dir: Path) -> dict[str, Any]:
        row = self._draft_row(draft_id)
        values = self._draft_values(draft_id)
        summary = self._workflow_summary(registry, row["draft_workflow_name"])
        base_blueprint = registry.load(row["draft_workflow_name"])
        preview_error: str | None = None
        preview_blueprint = base_blueprint
        try:
            preview_blueprint = preview_workbench_edit(
                registry,
                workflow_name=row["draft_workflow_name"],
                values=values,
            )
        except (WorkbenchInputError, ValueError) as exc:
            preview_error = str(exc)
        validation = self._validation_snapshot(draft_id)
        if validation is not None:
            validation["stale"] = validation.get("revision") != row["revision"]
        compare = None
        if row["last_run_id"] and row["baseline_run_id"]:
            compare = self.compare_snapshot(
                runs_dir=runs_dir,
                candidate_run_id=row["last_run_id"],
                baseline_run_id=row["baseline_run_id"],
            )
        baseline_run = self._indexed_run(row["baseline_run_id"]) if row["baseline_run_id"] else None
        last_run = self._indexed_run(row["last_run_id"]) if row["last_run_id"] else None
        base_safe_edit = safe_edit_model(base_blueprint)
        self.set_ui_state("last_draft_id", draft_id)
        return {
            "id": row["id"],
            "source_workflow_name": row["source_workflow_name"],
            "draft_workflow_name": row["draft_workflow_name"],
            "baseline_run_id": row["baseline_run_id"],
            "status": row["status"],
            "last_run_id": row["last_run_id"],
            "revision": row["revision"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "workflow": summary,
            "draft_values": values,
            "safe_edit": safe_edit_model(preview_blueprint),
            "canvas": workflow_canvas(preview_blueprint, read_run_detail(resolve_run_dir(runs_dir, row["baseline_run_id"])) if row["baseline_run_id"] else None),
            "preview_error": preview_error,
            "validation": validation,
            "baseline_run": baseline_run,
            "last_run": last_run,
            "compare": compare,
            "step_state": _step_state(
                status=row["status"],
                has_baseline=bool(row["baseline_run_id"]),
                has_last_run=bool(row["last_run_id"]),
                validation=validation,
            ),
            "guidance": {
                "summary": "Draft values live in SQLite until you validate or run. Canonical reusable workflows stay on disk.",
                "supported_edits": base_safe_edit.get("supported_edits", []),
                "limitations": base_safe_edit.get("limitations", []),
                "source_of_truth": [
                    "Built-in workflows stay read-only until you clone them into a local workflow.",
                    "Reusable local workflows remain JSON files on disk.",
                    "Draft values, validation snapshots, and resume state live in SQLite.",
                ],
                "next_step": _draft_next_step(
                    status=row["status"],
                    has_baseline=bool(row["baseline_run_id"]),
                    has_last_run=bool(row["last_run_id"]),
                    validation=validation,
                ),
            },
        }

    def patch_draft_session(
        self,
        *,
        draft_id: str,
        registry: WorkflowRegistry,
        runs_dir: Path,
        values: Mapping[str, Any],
    ) -> dict[str, Any]:
        row = self._draft_row(draft_id)
        blueprint = registry.load(row["draft_workflow_name"])
        allowed = _allowed_draft_keys(blueprint)
        unexpected = sorted(set(values) - allowed)
        if unexpected:
            raise WorkbenchInputError("unsupported edit field(s): " + ", ".join(unexpected))
        current = self._draft_values(draft_id)
        for key, value in values.items():
            current[key] = str(value)
        timestamp = _utc_now()
        with self._connect() as connection:
            self._replace_draft_values(connection, draft_id, current)
            connection.execute(
                """
                UPDATE draft_sessions
                SET status = ?, revision = revision + 1, updated_at = ?
                WHERE id = ?
                """,
                ("draft-dirty", timestamp, draft_id),
            )
        return self.get_draft_session(draft_id=draft_id, registry=registry, runs_dir=runs_dir)

    def validate_draft_session(self, *, draft_id: str, registry: WorkflowRegistry, runs_dir: Path) -> dict[str, Any]:
        row = self._draft_row(draft_id)
        values = self._draft_values(draft_id)
        timestamp = _utc_now()
        try:
            preview_workbench_edit(registry, workflow_name=row["draft_workflow_name"], values=values)
            payload = {
                "ok": True,
                "errors": [],
                "workflow": row["draft_workflow_name"],
                "revision": row["revision"],
                "validated_at": timestamp,
            }
            status = "draft-valid"
        except (WorkbenchInputError, ValueError) as exc:
            payload = {
                "ok": False,
                "errors": [str(exc)],
                "workflow": row["draft_workflow_name"],
                "revision": row["revision"],
                "validated_at": timestamp,
            }
            status = "draft-invalid"
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO validation_snapshots (draft_id, revision, ok, payload_json, validated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(draft_id) DO UPDATE SET
                    revision = excluded.revision,
                    ok = excluded.ok,
                    payload_json = excluded.payload_json,
                    validated_at = excluded.validated_at
                """,
                (draft_id, row["revision"], 1 if payload["ok"] else 0, _json_dump(payload), timestamp),
            )
            connection.execute(
                "UPDATE draft_sessions SET status = ?, updated_at = ? WHERE id = ?",
                (status, timestamp, draft_id),
            )
        return {
            "validation": payload,
            "draft": self.get_draft_session(draft_id=draft_id, registry=registry, runs_dir=runs_dir),
        }

    def run_draft_session(
        self,
        *,
        draft_id: str,
        registry: WorkflowRegistry,
        runs_dir: Path,
        user: str | None = None,
    ) -> dict[str, Any]:
        validation = self.validate_draft_session(draft_id=draft_id, registry=registry, runs_dir=runs_dir)
        if not validation["validation"]["ok"]:
            raise WorkbenchInputError("draft must validate before run")
        row = self._draft_row(draft_id)
        values = self._draft_values(draft_id)
        updated = preview_workbench_edit(registry, workflow_name=row["draft_workflow_name"], values=values)
        registry.save(updated, overwrite=True)
        result = run_workflow_blueprint(
            updated,
            command=f"xrtm web draft run {updated.name}",
            runs_dir=runs_dir,
            user=user,
        )
        self.refresh_indexes(runs_dir=runs_dir, registry=registry)
        compare = None
        status = "run-succeeded"
        if row["baseline_run_id"]:
            compare = self.compare_snapshot(
                runs_dir=runs_dir,
                candidate_run_id=result.run.run_id,
                baseline_run_id=row["baseline_run_id"],
                refresh=True,
            )
            status = "compare-ready"
        timestamp = _utc_now()
        with self._connect() as connection:
            connection.execute(
                "UPDATE draft_sessions SET status = ?, last_run_id = ?, updated_at = ? WHERE id = ?",
                (status, result.run.run_id, timestamp, draft_id),
            )
        self.set_ui_state("last_run_id", result.run.run_id)
        return {
            "run_id": result.run.run_id,
            "compare": compare,
            "draft": self.get_draft_session(draft_id=draft_id, registry=registry, runs_dir=runs_dir),
        }

    def compare_snapshot(
        self,
        *,
        runs_dir: Path,
        candidate_run_id: str,
        baseline_run_id: str,
        refresh: bool = False,
    ) -> dict[str, Any]:
        if not refresh:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT payload_json FROM compare_cache WHERE candidate_run_id = ? AND baseline_run_id = ?",
                    (candidate_run_id, baseline_run_id),
                ).fetchone()
            if row is not None:
                cached = _json_load(row["payload_json"])
                if cached.get("schema_version") == COMPARE_CACHE_SCHEMA_VERSION:
                    return cached
        baseline_dir = resolve_run_dir(runs_dir, baseline_run_id)
        candidate_dir = resolve_run_dir(runs_dir, candidate_run_id)
        rows = compare_runs(
            baseline_dir,
            candidate_dir,
        )
        decorated_rows = [_decorate_compare_row(row) for row in rows]
        baseline_detail = read_run_detail(baseline_dir)
        candidate_detail = read_run_detail(candidate_dir)
        question_rows = _compare_question_rows(
            baseline_rows=_forecast_rows(baseline_detail),
            candidate_rows=_forecast_rows(candidate_detail),
        )
        verdict = _compare_verdict(decorated_rows)
        payload = {
            "schema_version": COMPARE_CACHE_SCHEMA_VERSION,
            "candidate_run_id": candidate_run_id,
            "baseline_run_id": baseline_run_id,
            "run_pair": {
                "baseline": _compare_run_summary(run_id=baseline_run_id, detail=baseline_detail, run_dir=baseline_dir),
                "candidate": _compare_run_summary(run_id=candidate_run_id, detail=candidate_detail, run_dir=candidate_dir),
            },
            "rows": decorated_rows,
            "row_groups": _group_compare_rows(decorated_rows),
            "question_rows": question_rows,
            "verdict": verdict,
            "summary_cards": _compare_summary_cards(rows=decorated_rows, verdict=verdict, question_rows=question_rows),
            "next_actions": [
                {
                    "label": "Inspect candidate run",
                    "href": f"/runs/{candidate_run_id}",
                    "description": "Open the candidate detail page to review artifacts, metadata, and raw outputs.",
                },
                {
                    "label": "Return to the workbench",
                    "href": "/workbench",
                    "description": verdict["next_step"],
                },
                {
                    "label": "Open baseline run",
                    "href": f"/runs/{baseline_run_id}",
                    "description": "Keep the current baseline close by while you review question-level trade-offs.",
                },
            ],
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO compare_cache (candidate_run_id, baseline_run_id, payload_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(candidate_run_id, baseline_run_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (candidate_run_id, baseline_run_id, _json_dump(payload), _utc_now()),
            )
        return payload

    def resume_target(self, *, runs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        draft_id = self.get_ui_state("last_draft_id")
        if draft_id:
            try:
                row = self._draft_row(draft_id)
            except FileNotFoundError:
                row = None
            if row is not None:
                return {
                    "label": "Resume workbench draft",
                    "href": f"/workbench?draft={draft_id}",
                    "kind": "draft",
                    "draft_id": draft_id,
                    "workflow_name": row["draft_workflow_name"],
                }
        last_run_id = self.get_ui_state("last_run_id")
        if last_run_id:
            return {
                "label": "Inspect last run",
                "href": f"/runs/{last_run_id}",
                "kind": "run",
                "run_id": last_run_id,
            }
        latest_runs = runs if runs is not None else self.list_runs()
        if latest_runs:
            latest_run_id = latest_runs[0].get("run_id")
            return {
                "label": "Inspect latest run",
                "href": f"/runs/{latest_run_id}",
                "kind": "run",
                "run_id": latest_run_id,
            }
        return {"label": "Open workbench", "href": "/workbench", "kind": "workbench"}

    def set_ui_state(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ui_state (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, value, _utc_now()),
            )

    def get_ui_state(self, key: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute("SELECT value FROM ui_state WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        return str(row["value"])

    def _draft_row(self, draft_id: str) -> sqlite3.Row:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM draft_sessions WHERE id = ?", (draft_id,)).fetchone()
        if row is None:
            raise FileNotFoundError(f"draft does not exist: {draft_id}")
        return row

    def _draft_values(self, draft_id: str) -> dict[str, str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT key, value FROM draft_values WHERE draft_id = ? ORDER BY key",
                (draft_id,),
            ).fetchall()
        return {str(row["key"]): str(row["value"]) for row in rows}

    def _validation_snapshot(self, draft_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM validation_snapshots WHERE draft_id = ?",
                (draft_id,),
            ).fetchone()
        if row is None:
            return None
        return _json_load(row["payload_json"])

    def _indexed_run(self, run_id: str | None) -> dict[str, Any] | None:
        if not run_id:
            return None
        with self._connect() as connection:
            row = connection.execute("SELECT run_json FROM run_index WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        return _json_load(row["run_json"])

    def _workflow_summary(self, registry: WorkflowRegistry, workflow_name: str) -> dict[str, Any]:
        for workflow in registry.list_workflows():
            if workflow.name == workflow_name:
                return workflow.__dict__
        raise FileNotFoundError(f"workflow does not exist: {workflow_name}")

    def _recommended_compare_run(self, *, workflow_name: str | None, run_id: str) -> dict[str, Any] | None:
        if not workflow_name:
            return None
        for item in self.list_runs():
            if item.get("run_id") == run_id:
                continue
            workflow = _mapping(item.get("workflow"))
            if workflow.get("name") == workflow_name:
                return {
                    "run_id": item.get("run_id"),
                    "label": _run_label(item),
                    "href": f"/runs/{run_id}/compare/{item.get('run_id')}",
                }
        return None

    def _workflow_guided_actions(self, workflow: dict[str, Any]) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = [
            {
                "label": "Open workbench",
                "href": f"/workbench?workflow={workflow['name']}",
            }
        ]
        if workflow["source"] == "builtin":
            actions.insert(
                0,
                {
                    "label": "Clone into local draft",
                    "method": "POST",
                    "href": "/api/drafts",
                    "payload": {"source_workflow_name": workflow["name"]},
                },
            )
        return actions

    def _replace_draft_values(self, connection: sqlite3.Connection, draft_id: str, values: Mapping[str, str]) -> None:
        connection.execute("DELETE FROM draft_values WHERE draft_id = ?", (draft_id,))
        connection.executemany(
            "INSERT INTO draft_values (draft_id, key, value) VALUES (?, ?, ?)",
            [(draft_id, key, str(value)) for key, value in values.items()],
        )

    def _unique_draft_name(self, registry: WorkflowRegistry, source_workflow_name: str) -> str:
        base_name = f"{source_workflow_name}-draft"
        candidate = base_name
        index = 2
        while True:
            try:
                registry.load(candidate)
            except FileNotFoundError:
                return candidate
            candidate = f"{base_name}-{index}"
            index += 1

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection



def default_app_db_path(workflows_dir: Path) -> Path:
    root = workflows_dir if workflows_dir.is_absolute() else Path.cwd() / workflows_dir
    if root.name == "workflows":
        return root.parent / "webui" / DEFAULT_APP_DB_NAME
    return root / "webui" / DEFAULT_APP_DB_NAME



def _allowed_draft_keys(blueprint: WorkflowBlueprint) -> set[str]:
    model = safe_edit_model(blueprint)
    keys = {"questions_limit", "artifacts_write_report"}
    for editor in model.get("aggregate_weight_editors", []):
        for contributor in editor.get("contributors", []):
            keys.add(f"weight:{editor['node']}:{contributor['name']}")
    return keys



def _default_draft_values(blueprint: WorkflowBlueprint) -> dict[str, str]:
    model = safe_edit_model(blueprint)
    values = {
        "questions_limit": str(model["questions_limit"]["value"]),
        "artifacts_write_report": "true" if model["artifacts_write_report"] else "false",
    }
    for editor in model.get("aggregate_weight_editors", []):
        for contributor in editor.get("contributors", []):
            values[f"weight:{editor['node']}:{contributor['name']}"] = str(contributor["percent"])
    return values



def _compare_verdict(rows: list[dict[str, Any]]) -> dict[str, Any]:
    improved = sum(1 for row in rows if "right improved" in str(row.get("interpretation")))
    regressed = sum(1 for row in rows if "right regressed" in str(row.get("interpretation")))
    changed = sum(1 for row in rows if "unchanged" not in str(row.get("interpretation")))
    if improved and not regressed:
        label = "better"
        summary = "Candidate improved the tracked comparison metrics."
        headline = "Candidate is ahead"
        tone = "success"
        next_step = "Review the candidate report and, if the question-level rows still look healthy, consider promoting it."
    elif regressed and not improved:
        label = "worse"
        summary = "Candidate regressed on the tracked comparison metrics."
        headline = "Baseline remains stronger"
        tone = "error"
        next_step = "Keep the baseline for now and return to the draft to address the regressions."
    elif improved and regressed:
        label = "mixed"
        summary = "Candidate improved some metrics and regressed on others."
        headline = "Trade-offs need review"
        tone = "warning"
        next_step = "Use the question comparison table to decide whether the gains justify the regressions before iterating."
    else:
        label = "no material change"
        summary = "Comparison metrics are unchanged or require manual review."
        headline = "No decisive winner"
        tone = "neutral"
        next_step = "Open the candidate artifacts if you still want to inspect output quality, or make a stronger edit and rerun."
    return {
        "label": label,
        "headline": headline,
        "summary": summary,
        "tone": tone,
        "next_step": next_step,
        "improved": improved,
        "regressed": regressed,
        "changed": changed,
    }



def _draft_next_step(
    *, status: str, has_baseline: bool, has_last_run: bool, validation: dict[str, Any] | None
) -> dict[str, str]:
    if has_last_run and has_baseline:
        return {
            "key": "compare",
            "title": "Compare the candidate against the baseline",
            "detail": "Use the comparison summary to decide whether to iterate the draft, inspect the candidate run, or keep the baseline.",
        }
    if has_last_run:
        return {
            "key": "inspect",
            "title": "Inspect the new candidate run",
            "detail": "Review the run detail and artifacts, then choose a baseline later if you want a comparison.",
        }
    if validation and validation.get("ok") and not validation.get("stale"):
        return {
            "key": "run",
            "title": "Run the validated draft",
            "detail": "The latest safe edits validated successfully. Run the local draft to create a candidate result.",
        }
    if validation and not validation.get("ok"):
        return {
            "key": "edit",
            "title": "Fix the safe-edit values and validate again",
            "detail": "The draft context is preserved. Adjust the supported fields, then re-run validation inline.",
        }
    return {
        "key": "validate",
        "title": "Validate before you run",
        "detail": f"Current draft state: {status}. Make the safe edits you need, then validate the draft inline before creating a candidate run.",
    }


def _step_state(*, status: str, has_baseline: bool, has_last_run: bool, validation: dict[str, Any] | None) -> list[dict[str, Any]]:
    run_unlocked = bool(validation and validation.get("ok") and not validation.get("stale"))
    compare_unlocked = has_baseline and has_last_run
    return [
        {"key": "inspect", "label": "Inspect", "locked": False, "description": "Review a baseline run or workflow."},
        {"key": "clone", "label": "Clone", "locked": False, "description": "Create or reopen an editable local workflow."},
        {"key": "edit", "label": "Edit", "locked": False, "description": "Adjust the constrained safe-edit fields."},
        {"key": "validate", "label": "Validate", "locked": False, "description": "Check whether the latest draft is runnable."},
        {
            "key": "run",
            "label": "Run",
            "locked": not run_unlocked,
            "description": "Locked until the latest validation passes." if not run_unlocked else "Run the validated local draft.",
        },
        {
            "key": "compare",
            "label": "Compare",
            "locked": not compare_unlocked,
            "description": "Locked until a candidate run and baseline exist."
            if not compare_unlocked
            else "Compare the candidate to the baseline run.",
        },
        {
            "key": "next-step",
            "label": "Next step",
            "locked": False,
            "description": f"Current draft state: {status}.",
        },
    ]



def _json_dump(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True)



def _json_load(value: str) -> Any:
    return json.loads(value)



def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}



def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None



def _run_search_text(run: Mapping[str, Any]) -> str:
    workflow = _mapping(run.get("workflow"))
    values = [
        run.get("run_id"),
        run.get("status"),
        run.get("provider"),
        run.get("command"),
        workflow.get("name"),
        workflow.get("title"),
    ]
    return " ".join(str(value).lower() for value in values if value)


def _run_detail_summary(
    *, run: Mapping[str, Any], workflow: Mapping[str, Any], summary: Mapping[str, Any], report: Mapping[str, Any]
) -> str:
    status = str(run.get("status") or summary.get("status") or "unknown").replace("-", " ")
    provider = str(run.get("provider") or summary.get("provider") or "unknown provider")
    forecast_count = _integer_or_none(summary.get("forecast_count")) or 0
    warnings = _integer_or_none(summary.get("warning_count")) or 0
    errors = _integer_or_none(summary.get("error_count")) or 0
    report_state = "HTML report ready." if report.get("available") else "HTML report missing or not written."
    workflow_title = workflow.get("title") or workflow.get("name") or "workflow"
    return (
        f"{workflow_title} finished {status} on {provider} with {_count_label(forecast_count, 'forecast')}, "
        f"{_count_label(warnings, 'warning')}, and {_count_label(errors, 'error')}. {report_state}"
    )


def _run_metadata_groups(
    *, run: Mapping[str, Any], workflow: Mapping[str, Any], summary: Mapping[str, Any]
) -> list[dict[str, Any]]:
    return [
        {
            "title": "Run metadata",
            "items": _present_items(
                [
                    ("Run ID", run.get("run_id")),
                    ("Status", run.get("status") or summary.get("status")),
                    ("Provider", run.get("provider") or summary.get("provider")),
                    ("Updated", run.get("updated_at") or run.get("completed_at")),
                    ("Created", run.get("created_at") or run.get("started_at")),
                    ("User", run.get("user")),
                ]
            ),
        },
        {
            "title": "Workflow metadata",
            "items": _present_items(
                [
                    ("Workflow", workflow.get("title") or workflow.get("name")),
                    ("Workflow key", workflow.get("name")),
                    ("Kind", workflow.get("kind")),
                    ("Entry node", workflow.get("entry")),
                    ("Graph steps", workflow.get("graph_step_count")),
                    ("Nodes", workflow.get("node_count")),
                ]
            ),
        },
    ]


def _run_result_groups(*, summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    eval_summary = _mapping(summary.get("eval"))
    train_summary = _mapping(summary.get("train"))
    token_counts = _mapping(summary.get("token_counts"))
    groups = [
        {
            "title": "Quality",
            "items": _present_items(
                [
                    ("Forecast count", summary.get("forecast_count")),
                    ("Eval Brier", eval_summary.get("brier_score")),
                    ("Eval ECE", eval_summary.get("ece")),
                    ("Evaluated rows", eval_summary.get("total_evaluations")),
                ]
            ),
        },
        {
            "title": "Training",
            "items": _present_items(
                [
                    ("Train Brier", train_summary.get("brier_score")),
                    ("Training samples", train_summary.get("training_samples")),
                    ("Train evaluations", train_summary.get("total_evaluations")),
                ]
            ),
        },
        {
            "title": "Usage",
            "items": _present_items(
                [
                    ("Duration (seconds)", summary.get("duration_seconds")),
                    ("Total tokens", token_counts.get("total_tokens")),
                    ("Prompt tokens", token_counts.get("prompt_tokens")),
                    ("Completion tokens", token_counts.get("completion_tokens")),
                    ("Warnings", summary.get("warning_count")),
                    ("Errors", summary.get("error_count")),
                ]
            ),
        },
    ]
    return [group for group in groups if group["items"]]


def _forecast_rows(detail: Mapping[str, Any]) -> list[dict[str, Any]]:
    questions = {
        str(question.get("id")): question
        for question in detail.get("questions", [])
        if isinstance(question, dict) and question.get("id") is not None
    }
    rows: list[dict[str, Any]] = []
    for forecast in detail.get("forecasts", []):
        if not isinstance(forecast, dict):
            continue
        output = forecast.get("output", {}) if isinstance(forecast.get("output"), dict) else {}
        question_id = str(forecast.get("question_id") or output.get("question_id") or "")
        question = _deep_merge_mappings(
            questions.get(question_id, {}),
            forecast.get("question"),
            output.get("question"),
        )
        probability = _first_non_empty(forecast.get("probability"), output.get("probability"))
        outcome = _first_non_empty(
            question.get("resolved_outcome"),
            question.get("metadata", {}).get("resolved_outcome"),
            question.get("metadata", {}).get("raw_data", {}).get("resolved_outcome"),
            forecast.get("outcome"),
            output.get("outcome"),
        )
        usage = (
            _mapping(forecast.get("provider_metadata")).get("usage")
            or _mapping(_mapping(output.get("metadata")).get("raw_data")).get("usage")
            or {}
        )
        rows.append(
            {
                "question_id": question_id,
                "question_title": _first_non_empty(
                    question.get("title"),
                    question.get("question_text"),
                    question.get("metadata", {}).get("raw_data", {}).get("title"),
                    question_id,
                ),
                "question_text": _first_non_empty(
                    question.get("question_text"),
                    question.get("title"),
                    question.get("description"),
                    question.get("metadata", {}).get("raw_data", {}).get("content"),
                ),
                "resolution_date": _first_non_empty(
                    question.get("resolution_date"),
                    question.get("resolution_time"),
                    question.get("metadata", {}).get("resolution_time"),
                    question.get("metadata", {}).get("raw_data", {}).get("resolution_time"),
                ),
                "probability": probability,
                "confidence": _first_non_empty(forecast.get("confidence"), output.get("confidence")),
                "recorded_at": _first_non_empty(
                    forecast.get("recorded_at"),
                    output.get("recorded_at"),
                    _mapping(output.get("metadata")).get("created_at"),
                ),
                "resolved": _first_non_empty(
                    question.get("resolved"),
                    forecast.get("resolved"),
                    output.get("resolved"),
                    outcome is not None,
                ),
                "outcome": outcome,
                "brier_score": _first_non_empty(
                    forecast.get("brier_score"),
                    output.get("brier_score"),
                    _brier_score(probability, outcome),
                ),
                "reasoning": _first_non_empty(forecast.get("reasoning"), output.get("reasoning")),
                "tokens_used": _first_non_empty(forecast.get("tokens"), _mapping(usage).get("total_tokens")),
                "source_url": _first_non_empty(
                    question.get("source_url"),
                    question.get("metadata", {}).get("source_metadata", {}).get("source_url"),
                    question.get("metadata", {}).get("raw_data", {}).get("source_metadata", {}).get("source_url"),
                ),
            }
        )
    return rows


def _report_state(run_dir: Path, run_id: str, run: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = _mapping(run.get("artifacts"))
    report_path = Path(str(artifacts.get("report.html"))) if artifacts.get("report.html") else run_dir / "report.html"
    if not report_path.is_absolute():
        report_path = run_dir / report_path.name
    available = report_path.exists()
    return {
        "label": "HTML report",
        "available": available,
        "href": f"/runs/{run_id}/report" if available else None,
        "path": str(report_path),
        "description": (
            "Open the rendered HTML report in a new tab."
            if available
            else "This run does not currently have a report.html artifact. Re-run with report writing enabled to generate one."
        ),
    }


def _artifact_items(run_dir: Path, run: Mapping[str, Any]) -> list[dict[str, Any]]:
    artifacts = _mapping(run.get("artifacts"))
    ordered_names = sorted(artifacts, key=lambda name: (name != "report.html", name))
    items: list[dict[str, Any]] = []
    for name in ordered_names:
        path = Path(str(artifacts[name]))
        actual = path if path.is_absolute() else run_dir / path.name
        items.append(
            {
                "name": name,
                "label": _artifact_label(name),
                "path": str(actual),
                "available": actual.exists(),
                "kind": "report" if name.endswith(".html") else ("jsonl" if name.endswith(".jsonl") else "json"),
            }
        )
    return items


def _artifact_label(name: str) -> str:
    labels = {
        "blueprint.json": "Workflow blueprint",
        "competition_submission.json": "Competition submission",
        "eval.json": "Evaluation payload",
        "events.jsonl": "Event stream",
        "forecasts.jsonl": "Forecast rows",
        "graph_trace.jsonl": "Graph trace",
        "provider.json": "Provider payload",
        "questions.jsonl": "Question rows",
        "report.html": "HTML report",
        "run.json": "Run manifest",
        "run_summary.json": "Run summary",
        "train.json": "Training payload",
    }
    return labels.get(name, name)


def _decorate_compare_row(row: Mapping[str, Any]) -> dict[str, Any]:
    metric = str(row.get("metric") or "")
    interpretation = str(row.get("interpretation") or "")
    return {
        **row,
        "label": _compare_metric_label(metric),
        "category": _compare_metric_category(metric),
        "tone": _interpretation_tone(interpretation),
    }


def _group_compare_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {
        "Run profile": [],
        "Coverage": [],
        "Efficiency": [],
        "Quality": [],
        "Question shifts": [],
        "Other": [],
    }
    for row in rows:
        grouped.setdefault(str(row.get("category") or "Other"), []).append(row)
    return [{"title": title, "rows": items} for title, items in grouped.items() if items]


def _compare_run_summary(*, run_id: str, detail: Mapping[str, Any], run_dir: Path) -> dict[str, Any]:
    run = _mapping(detail.get("run"))
    workflow = _mapping(detail.get("workflow"))
    return {
        "run_id": run_id,
        "label": workflow.get("title") or workflow.get("name") or run_id,
        "status": run.get("status"),
        "provider": run.get("provider"),
        "updated_at": run.get("updated_at") or run.get("completed_at"),
        "report": _report_state(run_dir, run_id, run),
    }


def _compare_question_rows(
    *, baseline_rows: list[dict[str, Any]], candidate_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    baseline_by_id = {str(row.get("question_id")): row for row in baseline_rows if row.get("question_id")}
    candidate_by_id = {str(row.get("question_id")): row for row in candidate_rows if row.get("question_id")}
    question_ids = sorted(set(baseline_by_id) | set(candidate_by_id))
    rows: list[dict[str, Any]] = []
    for question_id in question_ids:
        baseline = baseline_by_id.get(question_id)
        candidate = candidate_by_id.get(question_id)
        title = _first_non_empty(
            _mapping(candidate).get("question_title"),
            _mapping(baseline).get("question_title"),
            question_id,
        )
        baseline_brier = _mapping(baseline).get("brier_score")
        candidate_brier = _mapping(candidate).get("brier_score")
        brier_delta = (
            float(candidate_brier) - float(baseline_brier)
            if isinstance(baseline_brier, (int, float)) and isinstance(candidate_brier, (int, float))
            else None
        )
        rows.append(
            {
                "question_id": question_id,
                "question_title": title,
                "question_text": _first_non_empty(
                    _mapping(candidate).get("question_text"),
                    _mapping(baseline).get("question_text"),
                ),
                "status": (
                    "shared"
                    if baseline and candidate
                    else ("candidate-only" if candidate else "baseline-only")
                ),
                "baseline_probability": _mapping(baseline).get("probability"),
                "candidate_probability": _mapping(candidate).get("probability"),
                "probability_shift": _numeric_delta(
                    _mapping(baseline).get("probability"),
                    _mapping(candidate).get("probability"),
                ),
                "baseline_brier": baseline_brier,
                "candidate_brier": candidate_brier,
                "brier_delta": brier_delta,
                "resolution_date": _first_non_empty(
                    _mapping(candidate).get("resolution_date"),
                    _mapping(baseline).get("resolution_date"),
                ),
                "outcome": _first_non_empty(_mapping(candidate).get("outcome"), _mapping(baseline).get("outcome")),
                "tone": _question_compare_tone(status=baseline and candidate, brier_delta=brier_delta),
            }
        )
    return rows


def _compare_summary_cards(
    *, rows: list[dict[str, Any]], verdict: Mapping[str, Any], question_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    shared_questions = sum(1 for row in question_rows if row.get("status") == "shared")
    candidate_only = sum(1 for row in question_rows if row.get("status") == "candidate-only")
    return [
        {"label": "Improved metrics", "value": verdict.get("improved", 0)},
        {"label": "Regressed metrics", "value": verdict.get("regressed", 0)},
        {"label": "Changed metrics", "value": verdict.get("changed", 0)},
        {"label": "Shared questions", "value": shared_questions},
        {"label": "Candidate-only questions", "value": candidate_only},
        {"label": "Compared rows", "value": len(rows)},
    ]


def _compare_metric_label(metric: str) -> str:
    labels = {
        "status": "Run status",
        "provider": "Provider",
        "user": "User",
        "forecast_count": "Forecast rows",
        "duration_seconds": "Duration (seconds)",
        "total_tokens": "Total tokens",
        "eval_brier": "Eval Brier",
        "eval_ece": "Eval ECE",
        "train_brier": "Train Brier",
        "training_samples": "Training samples",
        "warnings": "Warnings",
        "errors": "Errors",
        "shared_questions": "Shared questions",
        "left_only_questions": "Baseline-only questions",
        "right_only_questions": "Candidate-only questions",
        "avg_abs_probability_shift": "Average probability shift",
        "shared_question_brier": "Shared-question Brier",
        "shared_questions_improved": "Shared questions improved",
        "shared_questions_regressed": "Shared questions regressed",
    }
    if metric.startswith("largest_probability_shift"):
        return "Largest single-question probability shift"
    return labels.get(metric, metric.replace("_", " ").title())


def _compare_metric_category(metric: str) -> str:
    if metric in {"status", "provider", "user"}:
        return "Run profile"
    if metric in {"forecast_count", "training_samples", "shared_questions", "left_only_questions", "right_only_questions"}:
        return "Coverage"
    if metric in {"duration_seconds", "total_tokens"}:
        return "Efficiency"
    if metric in {"eval_brier", "eval_ece", "train_brier", "warnings", "errors", "shared_question_brier"}:
        return "Quality"
    if metric.startswith("largest_probability_shift") or metric in {
        "avg_abs_probability_shift",
        "shared_questions_improved",
        "shared_questions_regressed",
    }:
        return "Question shifts"
    return "Other"


def _interpretation_tone(interpretation: str) -> str:
    if "right improved" in interpretation:
        return "success"
    if "right regressed" in interpretation:
        return "error"
    if "changed" in interpretation or "review" in interpretation:
        return "warning"
    return "neutral"


def _question_compare_tone(*, status: object, brier_delta: float | None) -> str:
    if not status:
        return "warning"
    if brier_delta is None:
        return "neutral"
    if brier_delta < 0:
        return "success"
    if brier_delta > 0:
        return "error"
    return "neutral"


def _present_items(items: list[tuple[str, Any]]) -> list[dict[str, Any]]:
    return [{"label": label, "value": value} for label, value in items if _has_value(value)]


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _count_label(count: int, noun: str) -> str:
    suffix = "" if count == 1 else "s"
    return f"{count} {noun}{suffix}"


def _integer_or_none(value: Any) -> int | None:
    return int(value) if isinstance(value, (int, float)) else None


def _numeric_delta(left: Any, right: Any) -> float | None:
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return float(right) - float(left)
    return None


def _deep_merge_mappings(*values: Any) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for value in values:
        if not isinstance(value, dict):
            continue
        for key, item in value.items():
            if isinstance(item, dict) and isinstance(merged.get(key), dict):
                merged[key] = _deep_merge_mappings(merged.get(key), item)
            elif isinstance(item, dict):
                merged[key] = _deep_merge_mappings(item)
            else:
                merged[key] = item
    return merged


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value
        if value is not None and not isinstance(value, str):
            return value
    return None


def _brier_score(probability: Any, outcome: Any) -> float | None:
    if isinstance(probability, (int, float)) and isinstance(outcome, bool):
        return (float(probability) - float(outcome)) ** 2
    return None



def _run_label(run: Mapping[str, Any]) -> str:
    workflow = _mapping(run.get("workflow"))
    title = workflow.get("title") or workflow.get("name") or run.get("run_id")
    return f"{title} · {run.get('status', 'unknown')}"



def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


__all__ = ["DEFAULT_APP_DB_NAME", "WebUIStateStore", "default_app_db_path"]
