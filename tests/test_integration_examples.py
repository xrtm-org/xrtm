from __future__ import annotations

import asyncio
import importlib.util
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, relative_path: str):
    module_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _write_canonical_run_fixture(runs_dir: Path, run_id: str, question_ids: list[str]) -> None:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "provider": "mock",
                "created_at": "2026-05-01T10:00:00+00:00",
                "user": "alice",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "run_summary.json").write_text(
        json.dumps({"forecast_count": len(question_ids)}),
        encoding="utf-8",
    )
    (run_dir / "eval.json").write_text(
        json.dumps({"summary_statistics": {"brier_score": 0.1, "ece": 0.02}, "total_evaluations": len(question_ids)}),
        encoding="utf-8",
    )
    (run_dir / "questions.jsonl").write_text(
        "\n".join(
            json.dumps(
                {
                    "id": question_id,
                    "title": f"Question {question_id}",
                    "metadata": {"raw_data": {"resolved_outcome": question_id.endswith("1")}},
                }
            )
            for question_id in question_ids
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "forecasts.jsonl").write_text(
        "\n".join(
            json.dumps(
                {
                    "question_id": question_id,
                    "recorded_at": "2026-05-01T10:05:00+00:00",
                    "output": {"probability": 0.6, "reasoning": "fixture"},
                    "provider_metadata": {"usage": {"total_tokens": 42}},
                }
            )
            for question_id in question_ids
        )
        + "\n",
        encoding="utf-8",
    )


def test_batch_processing_uses_unique_batch_dirs_for_same_second_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    batch_module = _load_module("test_batch_processing_example", "examples/integration/batch-processing/run_batch.py")

    class FrozenDateTime:
        @classmethod
        def now(cls) -> datetime:
            return datetime(2026, 5, 1, 12, 30, 45)

    monkeypatch.setattr(batch_module, "datetime", FrozenDateTime)

    processor = batch_module.BatchProcessor(provider="mock", runs_dir=tmp_path / "batch-runs")
    questions = [batch_module.Question(id="q1", question="Will this batch example avoid same-second clobbering?")]

    asyncio.run(processor.process_batch(questions))
    asyncio.run(processor.process_batch(questions))

    batch_dirs = sorted(path.name for path in (tmp_path / "batch-runs").iterdir() if path.is_dir())
    assert batch_dirs == ["batch-20260501-123045", "batch-20260501-123045-01"]


def test_fastapi_service_generates_unique_forecast_ids_for_duplicate_requests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("fastapi")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XRTM_RUNS_DIR", str(tmp_path / "service-runs"))
    fastapi_module = _load_module("test_fastapi_service_example", "examples/integration/fastapi-service/app.py")
    fastapi_module.app.state.store = fastapi_module.ForecastStore()

    from fastapi.testclient import TestClient

    payload = {
        "question": "Will duplicate mock requests receive distinct forecast identifiers by 2027?",
        "resolution_date": "2027-12-31",
    }

    with TestClient(fastapi_module.app) as client:
        responses = [client.post("/api/v1/forecast", json=payload) for _ in range(5)]
        ids = [response.json()["forecast_id"] for response in responses]
        listing = client.get("/api/v1/forecasts?limit=10").json()

    assert all(response.status_code == 201 for response in responses)
    assert len(set(ids)) == len(ids)
    assert listing["total"] == 5


def test_scheduled_monitor_uses_unique_run_dirs_for_same_second_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monitor_module = _load_module("test_scheduled_monitor_example", "examples/integration/scheduled-monitor/monitor.py")

    class FrozenDateTime:
        @classmethod
        def now(cls) -> datetime:
            return datetime(2026, 5, 1, 9, 0, 0)

    monkeypatch.setattr(monitor_module, "datetime", FrozenDateTime)

    questions_file = tmp_path / "questions.json"
    questions_file.write_text(
        json.dumps(
            {
                "questions": [
                    {
                        "id": "q1",
                        "question": "Will the scheduled monitor keep separate artifacts for same-second runs?",
                        "track_trend": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    pipeline = monitor_module.MonitorPipeline(
        provider="mock",
        questions_file=questions_file,
        runs_dir=tmp_path / "monitor-runs",
    )

    asyncio.run(pipeline.run_once())
    asyncio.run(pipeline.run_once())

    run_dirs = sorted(
        path.name for path in (tmp_path / "monitor-runs").iterdir() if path.is_dir() and path.name != "latest"
    )
    assert run_dirs == ["run-20260501-090000", "run-20260501-090000-01"]
    assert (tmp_path / "monitor-runs" / "latest").resolve().name == "run-20260501-090000-01"


def test_data_export_sqlite_refreshes_selected_runs_in_place(tmp_path: Path) -> None:
    export_module = _load_module("test_data_export_example", "examples/integration/data-export/export.py")

    runs_dir = tmp_path / "runs"
    _write_canonical_run_fixture(runs_dir, "run-1", ["q1"])
    _write_canonical_run_fixture(runs_dir, "run-2", ["q2"])

    exporter = export_module.RunExporter(runs_dir)
    db_path = tmp_path / "forecasts.db"

    exporter.to_sqlite(db_path)
    exporter.to_sqlite(db_path)

    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM forecasts").fetchone()[0] == 2
    finally:
        conn.close()
