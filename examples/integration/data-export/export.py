"""Data export example for XRTM run artifacts.

This script demonstrates how to flatten canonical XRTM run directories into
analysis-friendly records for CSV, JSON, SQLite, and Parquet workflows.

Usage:
    python export.py --run-id 20260501T120000Z-abc12345 --runs-dir runs --format csv --output data.csv
    python export.py --runs-dir runs --format sqlite --output forecasts.db
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    import pandas as pd

    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


@dataclass
class ForecastRecord:
    """A flattened forecast record from one canonical XRTM run."""

    run_id: str
    question_id: str
    question_title: str
    probability: float
    reasoning: str
    recorded_at: str
    provider: str
    user: str | None = None
    resolution_time: str | None = None
    outcome: bool | None = None
    brier_score: float | None = None
    tokens_used: int | None = None


class RunExporter:
    """Export canonical XRTM runs to analysis-friendly formats."""

    def __init__(self, runs_dir: Path | str):
        self.runs_dir = Path(runs_dir)
        if not self.runs_dir.exists():
            raise ValueError(f"Runs directory not found: {self.runs_dir}")

    def list_runs(self, limit: int | None = None) -> list[str]:
        """List canonical run IDs under the runs directory."""

        run_dirs = sorted([path.name for path in self.runs_dir.iterdir() if path.is_dir()], reverse=True)
        if limit is not None:
            run_dirs = run_dirs[:limit]
        return run_dirs

    def load_run(self, run_id: str) -> dict[str, Any]:
        """Load one canonical run directory."""

        run_dir = self.runs_dir / run_id
        if not run_dir.exists():
            raise ValueError(f"Run not found: {run_id}")

        return {
            "run_id": run_id,
            "run": self._read_json(run_dir / "run.json"),
            "summary": self._read_json(run_dir / "run_summary.json"),
            "eval": self._read_json(run_dir / "eval.json"),
            "questions": self._read_jsonl(run_dir / "questions.jsonl"),
            "forecasts": self._read_jsonl(run_dir / "forecasts.jsonl"),
        }

    def to_records(self, run_ids: list[str] | None = None) -> list[ForecastRecord]:
        """Convert canonical runs into flat forecast records."""

        if run_ids is None:
            run_ids = self.list_runs()

        records: list[ForecastRecord] = []
        for run_id in run_ids:
            try:
                run_data = self.load_run(run_id)
                run_metadata = run_data.get("run", {})
                questions = {
                    question.get("id"): question for question in run_data.get("questions", []) if question.get("id") is not None
                }

                for forecast in run_data.get("forecasts", []):
                    question_id = str(forecast.get("question_id") or "")
                    question = questions.get(question_id, {})
                    output = forecast.get("output", {})
                    probability = _coerce_float(output.get("probability") or forecast.get("probability"))
                    outcome = _extract_outcome(question)
                    records.append(
                        ForecastRecord(
                            run_id=run_id,
                            question_id=question_id,
                            question_title=str(question.get("title") or question.get("question_text") or ""),
                            probability=probability,
                            reasoning=str(output.get("reasoning") or forecast.get("reasoning") or ""),
                            recorded_at=str(forecast.get("recorded_at") or run_metadata.get("created_at") or ""),
                            provider=str(run_metadata.get("provider") or "unknown"),
                            user=_string_or_none(run_metadata.get("user")),
                            resolution_time=_string_or_none(
                                question.get("resolution_time")
                                or question.get("metadata", {}).get("raw_data", {}).get("resolution_time")
                            ),
                            outcome=outcome,
                            brier_score=_compute_brier(probability, outcome),
                            tokens_used=_extract_tokens(forecast),
                        )
                    )
            except Exception as exc:
                print(f"Warning: Failed to load run {run_id}: {exc}", file=sys.stderr)

        return records

    def to_dataframe(self, run_ids: list[str] | None = None) -> "pd.DataFrame":
        """Convert records to a pandas DataFrame."""

        if not HAS_PANDAS:
            raise ImportError("pandas is required for DataFrame export. Install with: pip install pandas")
        return pd.DataFrame(asdict(record) for record in self.to_records(run_ids))

    def to_csv(self, output_file: Path, run_ids: list[str] | None = None) -> None:
        """Export records to CSV without requiring pandas."""

        records = self.to_records(run_ids)
        rows = [asdict(record) for record in records]
        fieldnames = list(ForecastRecord.__dataclass_fields__.keys())
        with output_file.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Exported {len(rows)} forecasts to {output_file}")

    def to_json(self, output_file: Path, run_ids: list[str] | None = None) -> None:
        """Export records to JSON."""

        data = [asdict(record) for record in self.to_records(run_ids)]
        with output_file.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
        print(f"Exported {len(data)} forecasts to {output_file}")

    def to_sqlite(self, db_file: Path, run_ids: list[str] | None = None) -> None:
        """Export records and run-level metrics to SQLite."""

        if run_ids is None:
            run_ids = self.list_runs()

        conn = sqlite3.connect(str(db_file))
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    provider TEXT,
                    user TEXT,
                    created_at TEXT,
                    forecast_count INTEGER,
                    eval_brier_score REAL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evaluations (
                    run_id TEXT PRIMARY KEY,
                    brier_score REAL,
                    ece REAL,
                    total_evaluations INTEGER,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS forecasts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    question_id TEXT,
                    question_title TEXT,
                    probability REAL,
                    reasoning TEXT,
                    recorded_at TEXT,
                    resolution_time TEXT,
                    outcome INTEGER,
                    brier_score REAL,
                    tokens_used INTEGER,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                )
                """
            )

            forecast_count = 0
            for run_id in run_ids:
                run_data = self.load_run(run_id)
                run_metadata = run_data.get("run", {})
                summary = run_data.get("summary", {})
                eval_summary = run_data.get("eval", {}).get("summary_statistics", {})
                records = self.to_records([run_id])

                conn.execute("DELETE FROM forecasts WHERE run_id = ?", (run_id,))

                conn.execute(
                    """
                    INSERT OR REPLACE INTO runs (run_id, provider, user, created_at, forecast_count, eval_brier_score)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        run_metadata.get("provider"),
                        run_metadata.get("user"),
                        run_metadata.get("created_at"),
                        summary.get("forecast_count", len(records)),
                        eval_summary.get("brier_score"),
                    ),
                )
                conn.execute(
                    """
                    INSERT OR REPLACE INTO evaluations (run_id, brier_score, ece, total_evaluations)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        eval_summary.get("brier_score"),
                        eval_summary.get("ece"),
                        run_data.get("eval", {}).get("total_evaluations"),
                    ),
                )
                for record in records:
                    conn.execute(
                        """
                        INSERT INTO forecasts (
                            run_id,
                            question_id,
                            question_title,
                            probability,
                            reasoning,
                            recorded_at,
                            resolution_time,
                            outcome,
                            brier_score,
                            tokens_used
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            record.run_id,
                            record.question_id,
                            record.question_title,
                            record.probability,
                            record.reasoning,
                            record.recorded_at,
                            record.resolution_time,
                            _sqlite_bool(record.outcome),
                            record.brier_score,
                            record.tokens_used,
                        ),
                    )
                    forecast_count += 1

            conn.commit()
        finally:
            conn.close()

        print(f"Exported {len(run_ids)} runs ({forecast_count} forecasts) to {db_file}")

    def to_parquet(self, output_file: Path, run_ids: list[str] | None = None) -> None:
        """Export records to Parquet."""

        try:
            import pyarrow.parquet as pq  # noqa: F401
        except ImportError as exc:
            raise ImportError("pyarrow is required for Parquet export. Install with: pip install pyarrow") from exc

        df = self.to_dataframe(run_ids)
        df.to_parquet(output_file, index=False)
        print(f"Exported {len(df)} forecasts to {output_file}")

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Export XRTM run data to various formats")
    parser.add_argument("--run-id", help="Specific run ID to export")
    parser.add_argument("--runs-dir", default="runs", help="Directory containing canonical run directories")
    parser.add_argument("--format", choices=["csv", "json", "sqlite", "parquet"], required=True, help="Output format")
    parser.add_argument("--output", required=True, help="Output file path")
    parser.add_argument("--limit", type=int, help="Limit number of runs to export when --run-id is omitted")

    args = parser.parse_args()

    try:
        exporter = RunExporter(args.runs_dir)
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    if args.run_id:
        run_ids = [Path(args.run_id).name]
    else:
        run_ids = exporter.list_runs(limit=args.limit)
        if not run_ids:
            print(f"No runs found in {args.runs_dir}")
            sys.exit(1)

    output_file = Path(args.output)
    try:
        if args.format == "csv":
            exporter.to_csv(output_file, run_ids)
        elif args.format == "json":
            exporter.to_json(output_file, run_ids)
        elif args.format == "sqlite":
            exporter.to_sqlite(output_file, run_ids)
        elif args.format == "parquet":
            exporter.to_parquet(output_file, run_ids)
    except ImportError as exc:
        print(f"Error: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"Export failed: {exc}")
        sys.exit(1)


def _coerce_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _string_or_none(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _extract_outcome(question: dict[str, Any]) -> bool | None:
    value = question.get("metadata", {}).get("raw_data", {}).get("resolved_outcome")
    if isinstance(value, bool):
        return value
    return None


def _compute_brier(probability: float, outcome: bool | None) -> float | None:
    if outcome is None:
        return None
    target = 1.0 if outcome else 0.0
    return (probability - target) ** 2


def _extract_tokens(forecast: dict[str, Any]) -> int | None:
    usage = forecast.get("provider_metadata", {}).get("usage", {})
    total_tokens = usage.get("total_tokens")
    if isinstance(total_tokens, int):
        return total_tokens
    return None


def _sqlite_bool(value: bool | None) -> int | None:
    if value is None:
        return None
    return int(value)


if __name__ == "__main__":
    main()
