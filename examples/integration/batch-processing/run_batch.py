"""Batch processing example for XRTM.

This script demonstrates how to process multiple forecasting questions from
CSV/JSON files with error handling and progress tracking.

Usage:
    python run_batch.py --provider mock --input sample_questions.json
    python run_batch.py --provider gemini --model gemini-2.0-flash --input data.csv
"""

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

from xrtm.forecast import ForecastingAnalyst

from xrtm.product.providers import DeterministicProvider


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


@dataclass
class Question:
    """Question to be forecasted."""
    id: str
    question: str
    resolution_date: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class BatchResult:
    """Result from batch processing."""
    total_count: int
    success_count: int
    error_count: int
    duration_seconds: float
    forecasts: list[dict[str, Any]]
    errors: list[dict[str, Any]]


class BatchProcessor:
    """Process multiple questions with XRTM."""

    def __init__(self, provider: str, model: str | None = None, runs_dir: Path = Path("batch-runs")):
        self.provider_name = provider
        self.model = model
        self.runs_dir = runs_dir
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    async def _create_analyst(self) -> ForecastingAnalyst:
        """Create forecasting analyst with specified provider."""
        if self.provider_name == "mock":
            provider = DeterministicProvider()
        else:
            # For real providers, use create_forecasting_analyst
            from xrtm.forecast import create_forecasting_analyst
            model_id = f"{self.provider_name}:{self.model or 'default'}"
            return create_forecasting_analyst(model_id=model_id, name="BatchAnalyst")

        return ForecastingAnalyst(model=provider, name="BatchAnalyst")

    async def _process_question(self, analyst: ForecastingAnalyst, question: Question) -> dict[str, Any]:
        """Process a single question and return forecast."""
        try:
            result = await analyst.run(question.question)
            return {
                "id": question.id,
                "question": question.question,
                "confidence": result.confidence,
                "reasoning": result.reasoning,
                "resolution_date": question.resolution_date,
                "metadata": question.metadata or {},
                "status": "success"
            }
        except Exception as e:
            return {
                "id": question.id,
                "question": question.question,
                "status": "error",
                "error": str(e),
                "error_type": type(e).__name__
            }

    async def process_batch(self, questions: list[Question]) -> BatchResult:
        """Process a batch of questions and return results."""
        start_time = time.time()
        analyst = await self._create_analyst()

        # Create batch directory
        batch_id, batch_dir = _create_unique_output_dir(self.runs_dir, "batch")

        print(f"Processing {len(questions)} questions with {self.provider_name} provider...")

        forecasts = []
        errors = []

        # Process questions sequentially (can be made concurrent for cloud providers)
        for i, question in enumerate(questions, 1):
            print(f"[{i}/{len(questions)}] Processing: {question.question[:60]}...")
            result = await self._process_question(analyst, question)

            if result["status"] == "success":
                forecasts.append(result)
            else:
                errors.append(result)

        duration = time.time() - start_time

        # Write results
        forecasts_file = batch_dir / "forecasts.jsonl"
        with forecasts_file.open("w") as f:
            for forecast in forecasts:
                f.write(json.dumps(forecast) + "\n")

        errors_file = batch_dir / "errors.jsonl"
        with errors_file.open("w") as f:
            for error in errors:
                f.write(json.dumps(error) + "\n")

        # Write summary
        summary = {
            "batch_id": batch_id,
            "provider": self.provider_name,
            "model": self.model,
            "total_count": len(questions),
            "success_count": len(forecasts),
            "error_count": len(errors),
            "duration_seconds": duration,
            "timestamp": datetime.now().isoformat()
        }

        summary_file = batch_dir / "summary.json"
        with summary_file.open("w") as f:
            json.dump(summary, f, indent=2)

        print(f"\nBatch complete: {len(forecasts)}/{len(questions)} successful")
        print(f"Results saved to: {batch_dir}")

        return BatchResult(
            total_count=len(questions),
            success_count=len(forecasts),
            error_count=len(errors),
            duration_seconds=duration,
            forecasts=forecasts,
            errors=errors
        )


def load_questions_from_json(path: Path) -> list[Question]:
    """Load questions from JSON file."""
    with path.open() as f:
        data = json.load(f)

    return [
        Question(
            id=item.get("id", str(i)),
            question=item["question"],
            resolution_date=item.get("resolution_date"),
            metadata=item.get("metadata")
        )
        for i, item in enumerate(data)
    ]


def load_questions_from_csv(path: Path) -> list[Question]:
    """Load questions from CSV file."""
    if not HAS_PANDAS:
        print("Error: pandas is required for CSV support. Install with: pip install pandas")
        sys.exit(1)

    df = pd.read_csv(path)
    questions = []

    for i, row in df.iterrows():
        questions.append(Question(
            id=row.get("id", str(i)),
            question=row["question"],
            resolution_date=row.get("resolution_date"),
            metadata={k: v for k, v in row.items() if k not in ["id", "question", "resolution_date"]}
        ))

    return questions


async def main():
    parser = argparse.ArgumentParser(description="Batch process forecasting questions with XRTM")
    parser.add_argument("--provider", default="mock", help="Provider to use (mock, gemini, openai)")
    parser.add_argument("--model", help="Model ID for provider")
    parser.add_argument("--input", required=True, help="Input file (JSON or CSV)")
    parser.add_argument("--runs-dir", default="batch-runs", help="Directory for batch runs")

    args = parser.parse_args()

    # Load questions
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    if input_path.suffix == ".json":
        questions = load_questions_from_json(input_path)
    elif input_path.suffix == ".csv":
        questions = load_questions_from_csv(input_path)
    else:
        print("Error: Input file must be .json or .csv")
        sys.exit(1)

    # Process batch
    processor = BatchProcessor(
        provider=args.provider,
        model=args.model,
        runs_dir=Path(args.runs_dir)
    )

    result = await processor.process_batch(questions)

    # Print summary
    print("\n" + "="*60)
    print("BATCH SUMMARY")
    print("="*60)
    print(f"Total questions:    {result.total_count}")
    print(f"Successful:         {result.success_count}")
    print(f"Errors:             {result.error_count}")
    print(f"Duration:           {result.duration_seconds:.2f}s")
    print(f"Avg per question:   {result.duration_seconds/result.total_count:.3f}s")


if __name__ == "__main__":
    asyncio.run(main())
