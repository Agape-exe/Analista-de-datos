"""Run a small reproducible Planner & Analysis benchmark outside Pytest."""

import asyncio
import platform
import statistics
import tempfile
from pathlib import Path
from time import perf_counter

from app.application.dto.analysis_input import AnalysisInput
from app.bootstrap import build_use_case
from app.config.settings import Settings


def write_csv(path: Path, rows: int) -> None:
    values = ["income,spending,region,segment,outcome"]
    for index in range(rows):
        income = index + 1
        region = "north" if index % 2 else "south"
        segment = "retail" if index % 3 else "business"
        outcome = 2 + (index % 3) if region == "north" else 9 + (index % 3)
        values.append(f"{income},{income * 2},{region},{segment},{outcome}")
    path.write_text("\n".join(values), encoding="utf-8")


async def measure(rows: int, repetitions: int = 3) -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "benchmark.csv"
        write_csv(path, rows)
        use_case = build_use_case(Settings(_env_file=None))
        totals: list[float] = []
        analytics: list[float] = []
        calls: list[int] = []
        statuses: list[str] = []
        for _ in range(repetitions):
            started = perf_counter()
            report = await use_case.execute(
                AnalysisInput(
                    source={"kind": "csv", "path": path},
                    user_question="Evaluate income and spending by region and segment.",
                )
            )
            totals.append(perf_counter() - started)
            analytics.append(report.metrics.analytics_time or 0.0)
            calls.append(report.metrics.tool_calls or 0)
            statuses.append(str(report.status))
    print(
        {
            "rows": rows,
            "columns": 5,
            "repetitions": repetitions,
            "median_total_seconds": statistics.median(totals),
            "median_analytics_seconds": statistics.median(analytics),
            "tool_calls": calls[-1],
            "status": statuses[-1],
        }
    )


async def main() -> None:
    print({"python": platform.python_version(), "platform": platform.platform()})
    for rows in (50, 500, 5000):
        await measure(rows)


if __name__ == "__main__":
    asyncio.run(main())
