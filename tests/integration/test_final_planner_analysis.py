import asyncio
from math import sqrt
from pathlib import Path

import pytest

from app.bootstrap import build_use_case
from app.modules.analysis.adapters.analytics.factory import build_statistical_tool_registry
from app.modules.analysis.adapters.orchestration.graph import LangGraphWorkflow
from app.modules.analysis.application.agents.analyst import AnalysisAgent
from app.modules.analysis.application.agents.planner import PlannerAgent
from app.modules.data_intake.adapters.datasource.csv_source import CsvDataSource
from app.modules.data_intake.application.agents.data_understanding import DataUnderstandingAgent
from app.modules.data_intake.application.services.data_understanding import DataUnderstandingService
from app.shared.application.dataset_registry import DatasetRegistry
from app.shared.config.settings import Settings
from app.shared.contracts.agent import AgentContext
from app.shared.contracts.analysis_input import AnalysisInput, resolve_configuration
from app.shared.contracts.llm import LLMRequest, LLMResponse
from app.shared.domain.enums.statuses import AnalysisStatus
from app.shared.domain.models.analysis import AnalysisPlan, AnalysisStep, Hypothesis, ToolRequest


class MustNotCallLLM:
    async def generate(self, request: LLMRequest) -> LLMResponse:
        raise AssertionError("Planner and Analysis must not call the LLM")


def write_validation_csv(path: Path) -> None:
    rows = ["x,linear,control,partial_y,category_a,category_b,outcome,constant"]
    for index in range(50):
        control = index // 5
        residual = (index % 5) - 2
        x = control * 10 + residual
        partial_y = control * 20 - residual
        category_a = "a" if index < 25 else "b"
        category_b = "north" if (index < 20 or 25 <= index < 30) else "south"
        outcome = 1 + (index % 2) if category_a == "a" else 10 + (index % 2)
        rows.append(f"{x},{2 * x + 3},{control},{partial_y},{category_a},{category_b},{outcome},1")
    path.write_text("\n".join(rows), encoding="utf-8")


async def local_context(
    path: Path, configuration: dict[str, object] | None = None
) -> tuple[AgentContext, DatasetRegistry]:
    settings = Settings(_env_file=None)
    value = AnalysisInput(
        source={"kind": "csv", "path": path},
        user_question="Evaluar x y partial_y controlando por control.",
        configuration=configuration or {},
    )
    understood = await DataUnderstandingService(CsvDataSource(), settings.data_intake).understand(
        value
    )
    datasets = DatasetRegistry()
    datasets.register(understood.dataset)
    return (
        AgentContext(
            run_id="final-validation",
            input=value,
            configuration=resolve_configuration(settings, value.configuration),
            dataset_id=understood.dataset.dataset_id,
            dataset_profile=understood.profile,
            data_dictionary=understood.data_dictionary,
        ),
        datasets,
    )


def plan(dataset_id: str, steps: list[AnalysisStep], hypotheses: list[Hypothesis]) -> AnalysisPlan:
    assert all(step.request.dataset_id == dataset_id for step in steps)
    return AnalysisPlan(hypotheses=hypotheses, steps=steps)


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def correlation(first: list[float], second: list[float]) -> float:
    first_mean = mean(first)
    second_mean = mean(second)
    numerator = sum(
        (left - first_mean) * (right - second_mean)
        for left, right in zip(first, second, strict=True)
    )
    return numerator / sqrt(
        sum((value - first_mean) ** 2 for value in first)
        * sum((value - second_mean) ** 2 for value in second)
    )


async def test_final_numeric_correlation_results(tmp_path: Path) -> None:
    path = tmp_path / "validation.csv"
    write_validation_csv(path)
    context, datasets = await local_context(path)
    try:
        hypothesis = Hypothesis(hypothesis_id="numeric", statement="Evaluate x and linear")
        steps = [
            AnalysisStep(
                step_id="pearson",
                hypothesis_id="numeric",
                request=ToolRequest(
                    dataset_id=context.dataset_id, method="pearson", variables=["x", "linear"]
                ),
            ),
            AnalysisStep(
                step_id="spearman",
                hypothesis_id="numeric",
                request=ToolRequest(
                    dataset_id=context.dataset_id, method="spearman", variables=["x", "linear"]
                ),
            ),
        ]
        result = await AnalysisAgent(
            MustNotCallLLM(), build_statistical_tool_registry(datasets)
        ).run(
            context.model_copy(
                update={"analysis_plan": plan(context.dataset_id, steps, [hypothesis])}
            )
        )
    finally:
        datasets.clear()

    assert result.status == AnalysisStatus.SUCCESS
    assert [item.result["correlation"] for item in result.update.analysis_results] == pytest.approx(
        [1.0, 1.0]
    )
    assert all(
        item.p_value is not None and item.p_value < 0.001 for item in result.update.analysis_results
    )
    assert all(item.sample_size == 50 for item in result.update.analysis_results)


async def test_final_partial_correlation_results(tmp_path: Path) -> None:
    path = tmp_path / "validation.csv"
    write_validation_csv(path)
    context, datasets = await local_context(path)
    try:
        planned = await PlannerAgent(MustNotCallLLM()).run(context)
        assert planned.status == AnalysisStatus.SUCCESS
        assert planned.update.analysis_plan is not None
        partial = next(
            step
            for step in planned.update.analysis_plan.steps
            if step.request.method == "partial_correlation"
        )
        result = await AnalysisAgent(
            MustNotCallLLM(), build_statistical_tool_registry(datasets)
        ).run(context.model_copy(update={"analysis_plan": planned.update.analysis_plan}))
    finally:
        datasets.clear()

    partial_result = next(
        item for item in result.update.analysis_results if item.method == "partial_correlation"
    )
    assert partial.request.parameters == {"control_variable": "control"}
    assert partial_result.status == AnalysisStatus.SUCCESS
    assert partial_result.result["correlation"] == pytest.approx(-1.0)
    assert partial_result.metadata["control_variable"] == "control"
    assert partial_result.sample_size == 50


async def test_final_categorical_association_results(tmp_path: Path) -> None:
    path = tmp_path / "validation.csv"
    write_validation_csv(path)
    context, datasets = await local_context(path)
    try:
        hypothesis = Hypothesis(hypothesis_id="categorical", statement="Evaluate categories")
        steps = [
            AnalysisStep(
                step_id="chi",
                hypothesis_id="categorical",
                request=ToolRequest(
                    dataset_id=context.dataset_id,
                    method="chi_square",
                    variables=["category_a", "category_b"],
                ),
            ),
            AnalysisStep(
                step_id="cramers",
                hypothesis_id="categorical",
                request=ToolRequest(
                    dataset_id=context.dataset_id,
                    method="cramers_v",
                    variables=["category_a", "category_b"],
                ),
            ),
        ]
        result = await AnalysisAgent(
            MustNotCallLLM(), build_statistical_tool_registry(datasets)
        ).run(
            context.model_copy(
                update={"analysis_plan": plan(context.dataset_id, steps, [hypothesis])}
            )
        )
    finally:
        datasets.clear()

    chi, cramers = result.update.analysis_results
    assert chi.result["chi_square"] == pytest.approx(18.0)
    assert chi.p_value is not None and chi.p_value < 0.001
    assert cramers.result["cramers_v"] == pytest.approx(0.6)
    assert chi.sample_size == cramers.sample_size == 50


async def test_final_anova_results(tmp_path: Path) -> None:
    path = tmp_path / "validation.csv"
    write_validation_csv(path)
    context, datasets = await local_context(path)
    try:
        hypothesis = Hypothesis(hypothesis_id="anova", statement="Evaluate group means")
        step = AnalysisStep(
            step_id="anova",
            hypothesis_id="anova",
            request=ToolRequest(
                dataset_id=context.dataset_id,
                method="anova_one_way",
                variables=["category_a", "outcome"],
            ),
        )
        result = await AnalysisAgent(
            MustNotCallLLM(), build_statistical_tool_registry(datasets)
        ).run(
            context.model_copy(
                update={"analysis_plan": plan(context.dataset_id, [step], [hypothesis])}
            )
        )
    finally:
        datasets.clear()

    anova = result.update.analysis_results[0]
    assert anova.result["f_statistic"] == pytest.approx(3928.923076923077)
    assert anova.effect_size == pytest.approx(0.9879303675048353)
    assert anova.p_value is not None and anova.p_value < 0.001
    assert anova.metadata["group_count"] == 2
    assert anova.sample_size == 50


async def test_final_missing_data_is_handled(tmp_path: Path) -> None:
    path = tmp_path / "missing.csv"
    write_validation_csv(path)
    rows = path.read_text(encoding="utf-8").splitlines()
    for index in range(1, len(rows), 10):
        values = rows[index].split(",")
        values[1] = ""
        rows[index] = ",".join(values)
    path.write_text("\n".join(rows), encoding="utf-8")
    context, datasets = await local_context(path)
    try:
        hypothesis = Hypothesis(hypothesis_id="missing", statement="Evaluate complete observations")
        step = AnalysisStep(
            step_id="pearson",
            hypothesis_id="missing",
            request=ToolRequest(
                dataset_id=context.dataset_id, method="pearson", variables=["x", "linear"]
            ),
        )
        result = await AnalysisAgent(
            MustNotCallLLM(), build_statistical_tool_registry(datasets)
        ).run(
            context.model_copy(
                update={"analysis_plan": plan(context.dataset_id, [step], [hypothesis])}
            )
        )
    finally:
        datasets.clear()

    analysis = result.update.analysis_results[0]
    assert analysis.status == AnalysisStatus.SUCCESS
    assert analysis.sample_size == 45
    assert analysis.result["correlation"] == pytest.approx(1.0)


async def test_final_constant_columns_are_handled(tmp_path: Path) -> None:
    path = tmp_path / "validation.csv"
    write_validation_csv(path)
    context, datasets = await local_context(path)
    try:
        hypothesis = Hypothesis(hypothesis_id="constant", statement="Reject constant columns")
        step = AnalysisStep(
            step_id="pearson",
            hypothesis_id="constant",
            request=ToolRequest(
                dataset_id=context.dataset_id, method="pearson", variables=["x", "constant"]
            ),
        )
        result = await AnalysisAgent(
            MustNotCallLLM(), build_statistical_tool_registry(datasets)
        ).run(
            context.model_copy(
                update={"analysis_plan": plan(context.dataset_id, [step], [hypothesis])}
            )
        )
    finally:
        datasets.clear()

    analysis = result.update.analysis_results[0]
    assert result.status == analysis.status == AnalysisStatus.FAILED
    assert analysis.result is analysis.p_value is analysis.effect_size is None


async def test_final_invalid_dataset_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "validation.csv"
    write_validation_csv(path)
    context, datasets = await local_context(path)
    missing_id = "unknown-dataset"
    try:
        hypothesis = Hypothesis(hypothesis_id="missing-dataset", statement="Reject missing dataset")
        step = AnalysisStep(
            step_id="pearson",
            hypothesis_id="missing-dataset",
            request=ToolRequest(dataset_id=missing_id, method="pearson", variables=["x", "linear"]),
        )
        result = await AnalysisAgent(
            MustNotCallLLM(), build_statistical_tool_registry(datasets)
        ).run(
            context.model_copy(
                update={
                    "dataset_id": missing_id,
                    "dataset_profile": context.dataset_profile.model_copy(
                        update={"dataset_id": missing_id}
                    ),
                    "analysis_plan": plan(missing_id, [step], [hypothesis]),
                }
            )
        )
    finally:
        datasets.clear()

    analysis = result.update.analysis_results[0]
    assert result.status == analysis.status == AnalysisStatus.FAILED
    assert analysis.result is analysis.p_value is analysis.effect_size is None


async def test_final_planner_analysis_is_reproducible(tmp_path: Path) -> None:
    path = tmp_path / "validation.csv"
    write_validation_csv(path)
    use_case = build_use_case(Settings(_env_file=None))
    value = AnalysisInput(
        source={"kind": "csv", "path": path},
        user_question="Evaluar x y partial_y controlando por control.",
    )

    first = await use_case.execute(value)
    second = await use_case.execute(value)

    first_results = [
        (item.method, item.variables, item.result, item.p_value) for item in first.analysis_results
    ]
    second_results = [
        (item.method, item.variables, item.result, item.p_value) for item in second.analysis_results
    ]

    assert first.status == second.status == AnalysisStatus.SUCCESS
    for report in (first, second):
        assert report.stage_statuses["Analysis"] == AnalysisStatus.SUCCESS
        assert report.stage_statuses["Critic"] == AnalysisStatus.SUCCESS
        assert report.stage_statuses["Insight"] == AnalysisStatus.SUCCESS
        assert report.analysis_results
        assert all(result.status == AnalysisStatus.SUCCESS for result in report.analysis_results)

        assert report.evidence
        assert report.relationship_assessments
        assert report.insights

        result_ids = {result.analysis_id for result in report.analysis_results}
        evidence_ids = {item.evidence_id for item in report.evidence}

        assert all(item.analysis_id in result_ids for item in report.evidence)
        for assessment in report.relationship_assessments:
            assert assessment.evidence_ids
            assert set(assessment.evidence_ids).issubset(evidence_ids)
        for insight in report.insights:
            assert insight.evidence_ids
            assert set(insight.evidence_ids).issubset(evidence_ids)

        assert report.evidence
        assert report.relationship_assessments
        assert report.insights

        result_ids = {result.analysis_id for result in report.analysis_results}
        evidence_ids = {item.evidence_id for item in report.evidence}

        assert all(item.analysis_id in result_ids for item in report.evidence)
        for assessment in report.relationship_assessments:
            assert assessment.evidence_ids
            assert set(assessment.evidence_ids).issubset(evidence_ids)
        for insight in report.insights:
            assert insight.evidence_ids
            assert set(insight.evidence_ids).issubset(evidence_ids)
    assert first_results == pytest.approx(second_results, nan_ok=False)
    assert first.metrics.tool_calls == second.metrics.tool_calls
    assert first.metrics.iterations == second.metrics.iterations == 1


class WaitingAfterRegistration(DataUnderstandingAgent):
    def __init__(self, service, datasets: DatasetRegistry, registered: asyncio.Event) -> None:
        super().__init__(service, datasets)
        self.registered = registered

    async def run(self, context: AgentContext):
        result = await super().run(context)
        self.registered.set()
        await asyncio.Event().wait()
        return result


async def test_workflow_cancellation_releases_registered_dataset(tmp_path: Path) -> None:
    path = tmp_path / "validation.csv"
    write_validation_csv(path)
    settings = Settings(_env_file=None)
    datasets = DatasetRegistry()
    registered = asyncio.Event()

    def build_run():
        return (
            [
                WaitingAfterRegistration(
                    DataUnderstandingService(CsvDataSource(), settings.data_intake),
                    datasets,
                    registered,
                )
            ],
            datasets.clear,
        )

    task = asyncio.create_task(
        LangGraphWorkflow(settings, run_factory=build_run).run(
            AnalysisInput(source={"kind": "csv", "path": path})
        )
    )
    await registered.wait()
    assert datasets.ids()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert datasets.ids() == ()
