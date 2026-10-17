import asyncio
from pathlib import Path

import pytest

from app.application.dto.analysis_input import AnalysisInput
from app.bootstrap import build_use_case
from app.config.settings import Settings
from app.domain.enums.statuses import AnalysisStatus


def write_dataset(path: Path) -> None:
    rows = ["income,spending,region,segment,outcome"]
    for index in range(40):
        income = index + 1
        region = "north" if index < 20 else "south"
        segment = "retail" if index % 2 else "business"
        outcome = 2 + (index % 3) if region == "north" else 10 + (index % 3)
        rows.append(f"{income},{income * 2},{region},{segment},{outcome}")
    path.write_text("\n".join(rows), encoding="utf-8")


def value(path: Path, configuration: dict[str, object] | None = None) -> AnalysisInput:
    return AnalysisInput(
        source={"kind": "csv", "path": path},
        user_question="Evaluate income and spending by region and segment.",
        configuration=configuration or {},
    )


async def test_build_use_case_executes_planner_analysis_with_local_csv(tmp_path: Path) -> None:
    path = tmp_path / "analysis.csv"
    write_dataset(path)

    report = await build_use_case(Settings(_env_file=None)).execute(value(path))

    assert report.status == AnalysisStatus.SKIPPED
    assert report.stage_statuses["Analysis"] == AnalysisStatus.SUCCESS
    assert report.stage_statuses["Critic"] == AnalysisStatus.SKIPPED
    assert report.stage_statuses["Insight"] == AnalysisStatus.SKIPPED
    assert not report.errors
    assert report.analysis_results
    assert all(result.status == AnalysisStatus.SUCCESS for result in report.analysis_results)
    assert report.metrics.tool_calls == len(report.analysis_results)
    assert report.metrics.analytics_time is not None and report.metrics.analytics_time >= 0
    assert {"DataUnderstanding", "Planner", "Analysis"} <= set(report.stage_statuses)
    assert "table" not in report.model_dump_json()


@pytest.mark.parametrize("budget, maximum", [(0, 0), (1, 1)])
async def test_workflow_respects_fast_tool_budget(
    tmp_path: Path, budget: int, maximum: int
) -> None:
    path = tmp_path / f"budget-{budget}.csv"
    write_dataset(path)

    report = await build_use_case(Settings(_env_file=None)).execute(
        value(path, {"analysis": {"max_tool_calls": budget}})
    )

    assert report.metrics.tool_calls == maximum
    assert len(report.analysis_results) <= maximum
    assert report.status == AnalysisStatus.SKIPPED
    assert report.stage_statuses["Analysis"] == (
        AnalysisStatus.SKIPPED if budget == 0 else AnalysisStatus.SUCCESS
    )
    assert report.stage_statuses["Critic"] == AnalysisStatus.SKIPPED
    assert report.stage_statuses["Insight"] == AnalysisStatus.SKIPPED
    assert not report.errors


async def test_workflow_isolates_concurrent_runs(tmp_path: Path) -> None:
    path = tmp_path / "concurrent.csv"
    write_dataset(path)
    use_case = build_use_case(Settings(_env_file=None))

    first, second = await asyncio.gather(
        use_case.execute(value(path)), use_case.execute(value(path))
    )

    assert first.status == second.status == AnalysisStatus.SKIPPED
    for report in (first, second):
        assert report.stage_statuses["Analysis"] == AnalysisStatus.SUCCESS
        assert report.stage_statuses["Critic"] == AnalysisStatus.SKIPPED
        assert report.stage_statuses["Insight"] == AnalysisStatus.SKIPPED
        assert not report.errors
    assert first.run_id != second.run_id
    assert first.dataset_profile.dataset_id != second.dataset_profile.dataset_id
    assert [result.method for result in first.analysis_results] == [
        result.method for result in second.analysis_results
    ]
