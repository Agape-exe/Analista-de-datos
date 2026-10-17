"""Run a small, reproducible Planner & Analysis workflow benchmark.

Usage: uv run python scripts/benchmark_planner_analysis.py
"""

import asyncio
import json
import platform
import random
import statistics
import sys
import tempfile
from pathlib import Path
from time import perf_counter

from app.bootstrap import build_use_case
from app.shared.config.settings import Settings
from app.shared.contracts.analysis_input import AnalysisInput

ROWS = (50, 500, 5_000)
REPETITIONS = 3
SEED = 20_261_016


def write_dataset(path: Path, rows: int) -> None:
    generator = random.Random(SEED)
    lines = ["segment,region,income,spend,control"]
    for index in range(rows):
        segment = "a" if index % 2 else "b"
        region = "north" if index % 3 else "south"
        control = index % 20
        income = control * 10 + generator.uniform(-2, 2)
        spend = income * 1.8 + generator.uniform(-3, 3)
        lines.append(f"{segment},{region},{income:.8f},{spend:.8f},{control}")
    path.write_text("\n".join(lines), encoding="utf-8")


async def benchmark() -> list[dict[str, object]]:
    settings = Settings(_env_file=None)
    use_case = build_use_case(settings)
    measurements: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="planner-analysis-benchmark-") as directory:
        root = Path(directory)
        for rows in ROWS:
            path = root / f"dataset-{rows}.csv"
            write_dataset(path, rows)
            totals: list[float] = []
            analytics: list[float] = []
            calls: list[int] = []
            statuses: list[str] = []
            for _ in range(REPETITIONS):
                started = perf_counter()
                report = await use_case.execute(
                    AnalysisInput(
                        source={"kind": "csv", "path": path},
                        user_question="Evaluate the association between income and spend.",
                    )
                )
                totals.append(perf_counter() - started)
                analytics.append(report.metrics.analytics_time or 0.0)
                calls.append(report.metrics.tool_calls or 0)
                statuses.append(str(report.status))
            measurements.append(
                {
                    "rows": rows,
                    "columns": 5,
                    "repetitions": REPETITIONS,
                    "median_total_seconds": statistics.median(totals),
                    "median_analytics_seconds": statistics.median(analytics),
                    "tool_calls": calls,
                    "statuses": statuses,
                }
            )
    return measurements


async def main() -> None:
    print(
        json.dumps(
            {
                "environment": {
                    "python": sys.version.split()[0],
                    "platform": platform.platform(),
                    "seed": SEED,
                },
                "measurements": await benchmark(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
