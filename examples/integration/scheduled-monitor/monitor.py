"""Scheduled monitoring example for XRTM.

This script demonstrates how to run recurring forecasts on a schedule with
trend tracking and reporting.

Usage:
    python monitor.py --provider mock --questions-file questions.json --run-once
    python monitor.py --provider mock --questions-file questions.json --schedule "every day at 09:00"
"""

import argparse
import asyncio
import json
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import schedule
    HAS_SCHEDULE = True
except ImportError:
    HAS_SCHEDULE = False

from xrtm.forecast import ForecastingAnalyst

from xrtm.product.providers import DeterministicProvider


@dataclass
class Question:
    """Question to monitor over time."""
    id: str
    question: str
    resolution_date: str | None = None
    track_trend: bool = True


def _create_unique_output_dir(parent: Path, prefix: str) -> tuple[str, Path]:
    """Create a timestamped output directory without clobbering same-second runs."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    for attempt in range(1000):
        suffix = "" if attempt == 0 else f"-{attempt:02d}"
        output_id = f"{prefix}-{timestamp}{suffix}"
        output_dir = parent / output_id
        try:
            output_dir.mkdir(parents=True, exist_ok=False)
            return output_id, output_dir
        except FileExistsError:
            continue

    raise RuntimeError(f"Failed to create unique {prefix} directory under {parent}")


class TrendDatabase:
    """SQLite database for tracking forecast trends over time."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self._init_schema()

    def _init_schema(self):
        """Initialize database schema."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS forecasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id TEXT NOT NULL,
                question TEXT NOT NULL,
                confidence REAL NOT NULL,
                timestamp TEXT NOT NULL,
                provider TEXT,
                reasoning TEXT
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_question_id ON forecasts(question_id)
        """)
        self.conn.commit()

    def save_forecast(self, question_id: str, question: str, confidence: float,
                     reasoning: str, provider: str):
        """Save a forecast to the database."""
        self.conn.execute(
            "INSERT INTO forecasts (question_id, question, confidence, timestamp, provider, reasoning) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (question_id, question, confidence, datetime.now().isoformat(), provider, reasoning)
        )
        self.conn.commit()

    def get_trend(self, question_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent trend data for a question."""
        cursor = self.conn.execute(
            "SELECT confidence, timestamp FROM forecasts WHERE question_id = ? "
            "ORDER BY timestamp DESC LIMIT ?",
            (question_id, limit)
        )
        results = []
        for row in cursor:
            results.append({"confidence": row[0], "timestamp": row[1]})
        return list(reversed(results))  # Return oldest to newest

    def get_latest(self, question_id: str) -> dict[str, Any] | None:
        """Get most recent forecast for a question."""
        cursor = self.conn.execute(
            "SELECT confidence, timestamp, reasoning FROM forecasts WHERE question_id = ? "
            "ORDER BY timestamp DESC LIMIT 1",
            (question_id,)
        )
        row = cursor.fetchone()
        if row:
            return {"confidence": row[0], "timestamp": row[1], "reasoning": row[2]}
        return None


class MonitorPipeline:
    """Monitor pipeline for scheduled forecasting."""

    def __init__(self, provider: str, questions_file: Path, runs_dir: Path, model: str | None = None):
        self.provider_name = provider
        self.model = model
        self.questions_file = questions_file
        self.runs_dir = runs_dir
        self.runs_dir.mkdir(parents=True, exist_ok=True)

        # Initialize trend database
        self.db = TrendDatabase(self.runs_dir / "trends.db")

        # Load questions
        self.questions = self._load_questions()

    def _load_questions(self) -> list[Question]:
        """Load questions from configuration file."""
        with self.questions_file.open() as f:
            config = json.load(f)

        return [
            Question(
                id=q["id"],
                question=q["question"],
                resolution_date=q.get("resolution_date"),
                track_trend=q.get("track_trend", True)
            )
            for q in config["questions"]
        ]

    async def _create_analyst(self) -> ForecastingAnalyst:
        """Create forecasting analyst."""
        if self.provider_name == "mock":
            provider = DeterministicProvider()
        else:
            from xrtm.forecast import create_forecasting_analyst
            model_id = f"{self.provider_name}:{self.model or 'default'}"
            return create_forecasting_analyst(model_id=model_id, name="MonitorAnalyst")

        return ForecastingAnalyst(model=provider, name="MonitorAnalyst")

    async def run_once(self) -> dict[str, Any]:
        """Run a single forecast cycle."""
        run_id, run_dir = _create_unique_output_dir(self.runs_dir, "run")

        print(f"\n{'='*60}")
        print(f"Starting monitor run: {run_id}")
        print(f"Provider: {self.provider_name}")
        print(f"Questions: {len(self.questions)}")
        print(f"{'='*60}\n")

        analyst = await self._create_analyst()
        forecasts = []

        for i, question in enumerate(self.questions, 1):
            print(f"[{i}/{len(self.questions)}] {question.question[:60]}...")

            try:
                # Generate forecast
                result = await analyst.run(question.question)

                # Save to database
                self.db.save_forecast(
                    question.id,
                    question.question,
                    result.confidence,
                    result.reasoning,
                    self.provider_name
                )

                # Get trend if tracking
                trend_data = None
                delta = None
                if question.track_trend:
                    trend_data = self.db.get_trend(question.id, limit=5)
                    if len(trend_data) > 1:
                        delta = trend_data[-1]["confidence"] - trend_data[-2]["confidence"]

                forecast = {
                    "id": question.id,
                    "question": question.question,
                    "confidence": result.confidence,
                    "reasoning": result.reasoning,
                    "timestamp": datetime.now().isoformat(),
                    "delta": delta,
                    "trend": trend_data
                }

                forecasts.append(forecast)

                # Track trend
                if delta is not None:
                    arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
                    print(f"  Confidence: {result.confidence:.3f} ({delta:+.3f} {arrow})")
                else:
                    print(f"  Confidence: {result.confidence:.3f}")

            except Exception as e:
                print(f"  ERROR: {e}")

        # Write results
        forecasts_file = run_dir / "forecasts.jsonl"
        with forecasts_file.open("w") as f:
            for forecast in forecasts:
                f.write(json.dumps(forecast) + "\n")

        # Generate report
        report = self._generate_report(forecasts, run_id)
        report_file = run_dir / "report.md"
        with report_file.open("w") as f:
            f.write(report)

        # Create symlink to latest
        latest_link = self.runs_dir / "latest"
        if latest_link.exists() or latest_link.is_symlink():
            latest_link.unlink()
        latest_link.symlink_to(run_dir.name)

        print(f"\n{'='*60}")
        print(f"Run complete: {run_id}")
        print(f"Forecasts: {len(forecasts)}")
        print(f"Report: {report_file}")
        print(f"{'='*60}\n")

        return {
            "run_id": run_id,
            "forecast_count": len(forecasts),
            "timestamp": datetime.now().isoformat()
        }

    def _generate_report(self, forecasts: list[dict[str, Any]], run_id: str) -> str:
        """Generate markdown report."""
        lines = [
            f"# Monitor Report: {run_id}",
            "",
            f"**Timestamp**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
            f"**Provider**: {self.provider_name}  ",
            f"**Questions**: {len(forecasts)}  ",
            "",
            "## Forecasts",
            ""
        ]

        for forecast in forecasts:
            lines.append(f"### {forecast['question']}")
            lines.append("")
            lines.append(f"**Confidence**: {forecast['confidence']:.3f}")

            if forecast.get("delta") is not None:
                delta = forecast["delta"]
                arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
                lines.append(f"**Change**: {delta:+.3f} {arrow}")

            lines.append("")
            lines.append(f"**Reasoning**: {forecast['reasoning']}")
            lines.append("")

            if forecast.get("trend"):
                lines.append("**Recent Trend**:")
                lines.append("```")
                for point in forecast["trend"]:
                    ts = point["timestamp"][:10]  # Date only
                    conf = point["confidence"]
                    lines.append(f"{ts}: {conf:.3f}")
                lines.append("```")
                lines.append("")

        return "\n".join(lines)


async def run_once_async(args):
    """Run monitor once asynchronously."""
    pipeline = MonitorPipeline(
        provider=args.provider,
        questions_file=Path(args.questions_file),
        runs_dir=Path(args.runs_dir),
        model=args.model
    )
    await pipeline.run_once()


def main():
    parser = argparse.ArgumentParser(description="Scheduled monitor for XRTM forecasting")
    parser.add_argument("--provider", default="mock", help="Provider to use")
    parser.add_argument("--model", help="Model ID for provider")
    parser.add_argument("--questions-file", required=True, help="Questions configuration file")
    parser.add_argument("--runs-dir", default="monitor-runs", help="Directory for monitor runs")
    parser.add_argument("--run-once", action="store_true", help="Run once and exit")
    parser.add_argument("--schedule", help="Schedule string (e.g., 'every day at 09:00')")

    args = parser.parse_args()

    # Validate questions file
    if not Path(args.questions_file).exists():
        print(f"Error: Questions file not found: {args.questions_file}")
        sys.exit(1)

    if args.run_once:
        # Run once and exit
        asyncio.run(run_once_async(args))
    elif args.schedule:
        # Run on schedule
        if not HAS_SCHEDULE:
            print("Error: schedule library required. Install with: pip install schedule")
            sys.exit(1)

        print(f"Scheduling monitor: {args.schedule}")

        # Parse schedule
        parts = args.schedule.split()
        if "every" not in parts:
            print("Error: Invalid schedule format. Expected 'every ...'")
            sys.exit(1)

        # Simple schedule parsing
        def job():
            asyncio.run(run_once_async(args))

        # Configure schedule
        if "day" in args.schedule and "at" in args.schedule:
            time_str = args.schedule.split("at")[1].strip()
            schedule.every().day.at(time_str).do(job)
        elif "hour" in args.schedule:
            schedule.every().hour.do(job)
        else:
            print(f"Error: Unsupported schedule format: {args.schedule}")
            sys.exit(1)

        # Run scheduler
        print("Monitor started. Press Ctrl+C to stop.")
        while True:
            schedule.run_pending()
            time.sleep(60)
    else:
        print("Error: Must specify --run-once or --schedule")
        sys.exit(1)


if __name__ == "__main__":
    main()
