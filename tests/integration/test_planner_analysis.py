from pathlib import Path

from app.adapters.datasource.csv_source import CsvDataSource
from app.agents.analyst import AnalysisAgent
from app.agents.planner import PlannerAgent
from app.analytics.factory import build_statistical_tool_registry
from app.application.dto.agent import AgentContext
from app.application.dto.analysis_input import AnalysisInput, resolve_configuration
from app.application.dto.llm import LLMRequest, LLMResponse
from app.application.services.data_understanding import DataUnderstandingService
from app.application.services.dataset_registry import DatasetRegistry
from app.config.settings import Settings
from app.domain.enums.statuses import AnalysisStatus


class MustNotCallLLM:
    async def generate(self, request: LLMRequest) -> LLMResponse:
        raise AssertionError("Planning and analysis must not call the LLM")


def service() -> DataUnderstandingService:
    return DataUnderstandingService(CsvDataSource(), Settings(_env_file=None).data_intake)


def write_dataset(path: Path, offset: int = 0) -> None:
    rows = ["segment,region,income,spend"]
    for value in range(1, 31):
        segment = "a" if value <= 15 else "b"
        region = "north" if value % 2 else "south"
        rows.append(f"{segment},{region},{value + offset},{(value + offset) * 2}")
    path.write_text("\n".join(rows), encoding="utf-8")


async def test_planner_analysis_executes_real_csv_dataset(tmp_path: Path) -> None:
    path = tmp_path / "analysis.csv"
    write_dataset(path)
    value = AnalysisInput(
        source={"kind": "csv", "path": path},
        user_question="Evaluar la asociación entre income y spend.",
    )
    settings = Settings(_env_file=None)
    understood = await service().understand(value)
    datasets = DatasetRegistry()
    datasets.register(understood.dataset)
    try:
        planning_context = AgentContext(
            run_id="integration-run",
            input=value,
            configuration=resolve_configuration(settings, value.configuration),
            dataset_id=understood.dataset.dataset_id,
            dataset_profile=understood.profile,
            data_dictionary=understood.data_dictionary,
        )
        planned = await PlannerAgent(MustNotCallLLM()).run(planning_context)
        assert planned.status == AnalysisStatus.SUCCESS
        assert planned.update.analysis_plan is not None

        analysis = await AnalysisAgent(
            MustNotCallLLM(), build_statistical_tool_registry(datasets)
        ).run(planning_context.model_copy(update={"analysis_plan": planned.update.analysis_plan}))
    finally:
        datasets.clear()

    assert analysis.status == AnalysisStatus.SUCCESS
    assert analysis.update.analysis_results
    assert {result.method for result in analysis.update.analysis_results} >= {"pearson", "spearman"}
    assert all(
        result.status == AnalysisStatus.SUCCESS for result in analysis.update.analysis_results
    )
    assert all(result.sample_size == 30 for result in analysis.update.analysis_results)
    assert analysis.update.metrics.tool_calls == len(analysis.update.analysis_results)
    assert datasets.ids() == ()


async def test_planner_analysis_runs_are_isolated(tmp_path: Path) -> None:
    first_path = tmp_path / "first.csv"
    second_path = tmp_path / "second.csv"
    write_dataset(first_path)
    write_dataset(second_path, offset=100)
    first = await service().understand(AnalysisInput(source={"kind": "csv", "path": first_path}))
    second = await service().understand(AnalysisInput(source={"kind": "csv", "path": second_path}))
    first_registry = DatasetRegistry()
    second_registry = DatasetRegistry()
    first_registry.register(first.dataset)
    second_registry.register(second.dataset)
    try:
        first_tools = build_statistical_tool_registry(first_registry)
        second_tools = build_statistical_tool_registry(second_registry)
        assert first_tools is not second_tools
        assert first_registry.ids() == (first.dataset.dataset_id,)
        assert second_registry.ids() == (second.dataset.dataset_id,)
    finally:
        first_registry.clear()
        second_registry.clear()

    assert first_registry.ids() == second_registry.ids() == ()
