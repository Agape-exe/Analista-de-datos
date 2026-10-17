import asyncio
from pathlib import Path

from app.agents.data_understanding import DataUnderstandingAgent
from app.analytics.registry import ToolRegistry
from app.application.dto.analysis_input import AnalysisInput
from app.application.services.dataset_registry import DatasetRegistry
from app.bootstrap import build_agents, build_data_understanding, build_llm, build_use_case
from app.config.settings import Settings
from app.domain.enums.statuses import AnalysisStatus
from app.orchestration.graph import LangGraphWorkflow


def write_dataset(path: Path, rows: int = 30, offset: int = 0) -> None:
    values = ["segment,region,income,spend"]
    for number in range(1, rows + 1):
        segment = "a" if number <= rows // 2 else "b"
        region = "north" if number % 2 else "south"
        values.append(f"{segment},{region},{number + offset},{(number + offset) * 2}")
    path.write_text("\n".join(values), encoding="utf-8")


def input_for(path: Path, configuration: dict[str, object] | None = None) -> AnalysisInput:
    return AnalysisInput(
        source={"kind": "csv", "path": path},
        user_question="Evaluar la asociación entre income y spend.",
        configuration=configuration or {},
    )


async def test_langgraph_executes_planner_analysis_with_csv(tmp_path: Path) -> None:
    path = tmp_path / "analysis.csv"
    write_dataset(path)

    report = await build_use_case(Settings(_env_file=None)).execute(input_for(path))

    assert report.status == AnalysisStatus.SUCCESS
    assert report.stage_statuses["Critic"] == AnalysisStatus.SUCCESS
    assert report.stage_statuses["Insight"] == AnalysisStatus.SUCCESS
    assert {result.method for result in report.analysis_results} >= {"pearson", "spearman"}
    assert all(result.status == AnalysisStatus.SUCCESS for result in report.analysis_results)
    assert report.stage_statuses["DataUnderstanding"] == AnalysisStatus.SUCCESS
    assert report.stage_statuses["Planner"] == AnalysisStatus.SUCCESS
    assert report.stage_statuses["Analysis"] == AnalysisStatus.SUCCESS
    assert len(report.stage_durations) == 6


async def test_build_use_case_produces_real_analysis_results(tmp_path: Path) -> None:
    path = tmp_path / "analysis.csv"
    write_dataset(path)

    report = await build_use_case(Settings(_env_file=None)).execute(input_for(path))

    assert report.analysis_results
    assert all(result.sample_size == 30 for result in report.analysis_results)
    assert report.metrics.analytics_time is not None
    assert report.metrics.analytics_time >= 0


async def test_workflow_reports_real_tool_calls(tmp_path: Path) -> None:
    path = tmp_path / "analysis.csv"
    write_dataset(path)

    report = await build_use_case(Settings(_env_file=None)).execute(input_for(path))

    assert report.metrics.tool_calls == len(report.analysis_results)
    assert report.metrics.tool_calls > 0
    assert report.metrics.llm_calls == 0
    assert report.metrics.total_response_time is not None


async def test_workflow_respects_fast_mode_limits(tmp_path: Path) -> None:
    path = tmp_path / "analysis.csv"
    write_dataset(path)
    use_case = build_use_case(Settings(_env_file=None))

    zero = await use_case.execute(input_for(path, {"analysis": {"max_tool_calls": 0}}))
    one = await use_case.execute(input_for(path, {"analysis": {"max_tool_calls": 1}}))

    assert zero.status == AnalysisStatus.SKIPPED
    assert zero.analysis_results == []
    assert zero.metrics.tool_calls == 0
    assert one.status == AnalysisStatus.SUCCESS
    assert one.insights and one.relationship_assessments
    assert all(item.potentially_spurious is None for item in one.relationship_assessments)
    assert one.stage_statuses["Analysis"] == AnalysisStatus.SUCCESS
    assert one.analysis_results[0].status == AnalysisStatus.SUCCESS
    assert len(one.analysis_results) == one.metrics.tool_calls == 1


async def test_workflow_skips_insufficient_sample(tmp_path: Path) -> None:
    path = tmp_path / "small.csv"
    write_dataset(path, rows=3)

    report = await build_use_case(Settings(_env_file=None)).execute(input_for(path))

    assert report.status == AnalysisStatus.SKIPPED
    assert report.analysis_results == []
    assert report.metrics.tool_calls == 0
    assert report.stage_statuses["Planner"] == AnalysisStatus.SKIPPED
    assert report.stage_statuses["Analysis"] == AnalysisStatus.SKIPPED


async def test_workflow_isolates_sequential_and_concurrent_runs(tmp_path: Path) -> None:
    first_path = tmp_path / "first.csv"
    second_path = tmp_path / "second.csv"
    write_dataset(first_path)
    write_dataset(second_path, offset=100)
    use_case = build_use_case(Settings(_env_file=None))

    first = await use_case.execute(input_for(first_path))
    second = await use_case.execute(input_for(second_path))
    concurrent_first, concurrent_second = await asyncio.gather(
        use_case.execute(input_for(first_path)), use_case.execute(input_for(second_path))
    )

    assert (
        len({first.run_id, second.run_id, concurrent_first.run_id, concurrent_second.run_id}) == 4
    )
    assert (
        len(
            {
                first.dataset_profile.dataset_id,
                second.dataset_profile.dataset_id,
                concurrent_first.dataset_profile.dataset_id,
                concurrent_second.dataset_profile.dataset_id,
            }
        )
        == 4
    )

    for report in (first, second, concurrent_first, concurrent_second):
        assert report.status == AnalysisStatus.SUCCESS
        assert report.stage_statuses["Analysis"] == AnalysisStatus.SUCCESS
        assert report.stage_statuses["Critic"] == AnalysisStatus.SUCCESS
        assert report.stage_statuses["Insight"] == AnalysisStatus.SUCCESS
        assert report.analysis_results
        assert all(result.status == AnalysisStatus.SUCCESS for result in report.analysis_results)


async def test_workflow_releases_dataset_after_failure(tmp_path: Path) -> None:
    path = tmp_path / "analysis.csv"
    write_dataset(path)
    settings = Settings(_env_file=None)
    registries: list[DatasetRegistry] = []

    def build_run():
        datasets = DatasetRegistry()
        registries.append(datasets)
        return (
            build_agents(
                build_llm(settings), ToolRegistry(), build_data_understanding(settings), datasets
            ),
            datasets.clear,
        )

    report = await LangGraphWorkflow(settings, run_factory=build_run).run(input_for(path))

    assert report.status == AnalysisStatus.FAILED
    assert registries[0].ids() == ()


class BlockingDataUnderstandingAgent(DataUnderstandingAgent):
    async def run(self, context):
        result = await super().run(context)
        await asyncio.Event().wait()
        return result


async def test_workflow_handles_timeout_without_leaks(tmp_path: Path) -> None:
    path = tmp_path / "analysis.csv"
    write_dataset(path)
    settings = Settings(_env_file=None)
    registries: list[DatasetRegistry] = []

    def build_run():
        datasets = DatasetRegistry()
        registries.append(datasets)
        return (
            [BlockingDataUnderstandingAgent(build_data_understanding(settings), datasets)],
            datasets.clear,
        )

    report = await LangGraphWorkflow(settings, run_factory=build_run).run(
        input_for(path, {"performance": {"timeout_seconds": 0.01}})
    )

    assert report.status == AnalysisStatus.FAILED
    assert "timeout" in report.errors[0].lower()
    assert registries[0].ids() == ()


async def test_workflow_serializes_analysis_report_without_raw_rows(tmp_path: Path) -> None:
    path = tmp_path / "analysis.csv"
    write_dataset(path)

    report = await build_use_case(Settings(_env_file=None)).execute(input_for(path))

    assert type(report).model_validate_json(report.model_dump_json()) == report
    assert '"table":' not in report.model_dump_json()
