import asyncio
from pathlib import Path

import pytest

from app.adapters.datasource.csv_source import CsvDataSource
from app.agents.analyst import AnalysisAgent
from app.agents.data_understanding import DataUnderstandingAgent
from app.analytics.factory import build_statistical_tool_registry
from app.application.dto.agent import AgentContext
from app.application.dto.analysis_input import AnalysisInput, resolve_configuration
from app.application.services.data_understanding import DataUnderstandingService
from app.application.services.dataset_registry import DatasetRegistry
from app.bootstrap import build_use_case
from app.config.settings import Settings
from app.domain.enums.statuses import AnalysisStatus
from app.domain.models.analysis import AnalysisPlan, AnalysisStep, Hypothesis, ToolRequest
from app.orchestration.graph import LangGraphWorkflow


class NoLLM:
    async def generate(self, request):
        raise AssertionError("Planner and Analysis must not call an LLM")


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


async def local_context(path: Path) -> tuple[AgentContext, DatasetRegistry]:
    settings = Settings(_env_file=None)
    value = AnalysisInput(
        source={"kind": "csv", "path": path},
        user_question="Evaluar x y partial_y controlando por control.",
    )
    understood = await DataUnderstandingService(CsvDataSource(), settings.data_intake).understand(
        value
    )
    datasets = DatasetRegistry()
    datasets.register(understood.dataset)
    return (
        AgentContext(
            run_id="regression",
            input=value,
            configuration=resolve_configuration(settings, value.configuration),
            dataset_id=understood.dataset.dataset_id,
            dataset_profile=understood.profile,
            data_dictionary=understood.data_dictionary,
        ),
        datasets,
    )


def analysis_plan(
    dataset_id: str,
    requests: list[tuple[str, str, list[str], dict[str, str] | None]],
) -> AnalysisPlan:
    hypothesis = Hypothesis(hypothesis_id="reference", statement="Evaluate reference data")
    return AnalysisPlan(
        hypotheses=[hypothesis],
        steps=[
            AnalysisStep(
                step_id=step_id,
                hypothesis_id=hypothesis.hypothesis_id,
                request=ToolRequest(
                    dataset_id=dataset_id,
                    method=method,
                    variables=variables,
                    parameters=parameters or {},
                ),
            )
            for step_id, method, variables, parameters in requests
        ],
    )


async def execute(
    context: AgentContext,
    datasets: DatasetRegistry,
    requests: list[tuple[str, str, list[str], dict[str, str] | None]],
):
    plan = analysis_plan(context.dataset_id, requests)
    return await AnalysisAgent(NoLLM(), build_statistical_tool_registry(datasets)).run(
        context.model_copy(update={"analysis_plan": plan})
    )


async def test_regression_numeric_correlations_match_reference(tmp_path: Path) -> None:
    path = tmp_path / "numeric.csv"
    write_validation_csv(path)
    context, datasets = await local_context(path)
    try:
        result = await execute(
            context,
            datasets,
            [
                ("pearson", "pearson", ["x", "linear"], None),
                ("spearman", "spearman", ["x", "linear"], None),
            ],
        )
    finally:
        datasets.clear()

    pearson, spearman = result.update.analysis_results
    assert result.status == AnalysisStatus.SUCCESS
    assert pearson.result["correlation"] == pytest.approx(1.0)
    assert spearman.result["correlation"] == pytest.approx(1.0)
    assert pearson.effect_size == pytest.approx(1.0)
    assert spearman.effect_size == pytest.approx(1.0)
    assert pearson.p_value is not None and pearson.p_value < 1e-30
    assert spearman.p_value is not None and spearman.p_value < 1e-30
    assert pearson.sample_size == spearman.sample_size == 50


async def test_regression_partial_correlation_matches_reference(tmp_path: Path) -> None:
    path = tmp_path / "partial.csv"
    write_validation_csv(path)
    context, datasets = await local_context(path)
    try:
        result = await execute(
            context,
            datasets,
            [
                (
                    "partial",
                    "partial_correlation",
                    ["x", "partial_y"],
                    {"control_variable": "control"},
                )
            ],
        )
    finally:
        datasets.clear()

    partial = result.update.analysis_results[0]
    assert partial.status == AnalysisStatus.SUCCESS
    assert partial.result["correlation"] == pytest.approx(-1.0)
    assert partial.effect_size == pytest.approx(-1.0)
    assert partial.p_value == pytest.approx(0.0)
    assert partial.sample_size == 50
    assert partial.metadata["control_variable"] == "control"
    assert partial.metadata["degrees_of_freedom"] == 47


async def test_regression_categorical_statistics_match_reference(tmp_path: Path) -> None:
    path = tmp_path / "categorical.csv"
    write_validation_csv(path)
    context, datasets = await local_context(path)
    try:
        result = await execute(
            context,
            datasets,
            [
                ("chi", "chi_square", ["category_a", "category_b"], None),
                ("cramers", "cramers_v", ["category_a", "category_b"], None),
            ],
        )
    finally:
        datasets.clear()

    chi_square, cramers_v = result.update.analysis_results
    assert chi_square.result["chi_square"] == pytest.approx(18.0)
    assert chi_square.p_value == pytest.approx(2.2090496998585438e-05)
    assert chi_square.sample_size == 50
    assert chi_square.metadata["degrees_of_freedom"] == 1
    assert cramers_v.result["cramers_v"] == pytest.approx(0.6)
    assert cramers_v.effect_size == pytest.approx(0.6)
    assert cramers_v.p_value == pytest.approx(chi_square.p_value)
    assert cramers_v.sample_size == 50


async def test_regression_anova_matches_reference(tmp_path: Path) -> None:
    path = tmp_path / "anova.csv"
    write_validation_csv(path)
    context, datasets = await local_context(path)
    try:
        result = await execute(
            context,
            datasets,
            [("anova", "anova_one_way", ["category_a", "outcome"], None)],
        )
    finally:
        datasets.clear()

    anova = result.update.analysis_results[0]
    assert anova.result["f_statistic"] == pytest.approx(3928.923076923077)
    assert anova.p_value == pytest.approx(1.2587568038678922e-43)
    assert anova.effect_size == pytest.approx(0.9879303675048353)
    assert anova.sample_size == 50
    assert anova.metadata["degrees_of_freedom_between"] == 1
    assert anova.metadata["degrees_of_freedom_within"] == 48


async def test_regression_missing_values_use_complete_cases(tmp_path: Path) -> None:
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
        result = await execute(
            context,
            datasets,
            [("pearson", "pearson", ["x", "linear"], None)],
        )
    finally:
        datasets.clear()

    analysis = result.update.analysis_results[0]
    assert analysis.status == AnalysisStatus.SUCCESS
    assert analysis.sample_size == 45
    assert analysis.result["correlation"] == pytest.approx(1.0)


@pytest.mark.parametrize(
    "variables, warning",
    [(["x", "constant"], "constant"), (["x", "missing"], "missing")],
)
async def test_regression_invalid_variables_do_not_fabricate_statistics(
    tmp_path: Path, variables: list[str], warning: str
) -> None:
    path = tmp_path / f"invalid-{warning}.csv"
    write_validation_csv(path)
    context, datasets = await local_context(path)
    try:
        result = await execute(
            context,
            datasets,
            [("invalid", "pearson", variables, None)],
        )
    finally:
        datasets.clear()

    analysis = result.update.analysis_results[0]
    assert result.status == analysis.status == AnalysisStatus.FAILED
    assert warning in analysis.warnings[0]
    assert analysis.result is analysis.p_value is analysis.effect_size is None


async def test_regression_unknown_dataset_does_not_fabricate_statistics(
    tmp_path: Path,
) -> None:
    path = tmp_path / "unknown-dataset.csv"
    write_validation_csv(path)
    context, datasets = await local_context(path)
    missing_id = "unknown-dataset"
    missing_context = context.model_copy(
        update={
            "dataset_id": missing_id,
            "dataset_profile": context.dataset_profile.model_copy(
                update={"dataset_id": missing_id}
            ),
        }
    )
    try:
        result = await execute(
            missing_context,
            datasets,
            [("unknown", "pearson", ["x", "linear"], None)],
        )
    finally:
        datasets.clear()

    analysis = result.update.analysis_results[0]
    assert result.status == analysis.status == AnalysisStatus.FAILED
    assert "Unknown dataset" in analysis.warnings[0]
    assert analysis.result is analysis.p_value is analysis.effect_size is None
    assert result.update.metrics.tool_calls == 1


async def test_regression_planner_analysis_is_reproducible(tmp_path: Path) -> None:
    path = tmp_path / "reproducible.csv"
    write_validation_csv(path)
    value = AnalysisInput(
        source={"kind": "csv", "path": path},
        user_question="Evaluar x y partial_y controlando por control.",
    )
    use_case = build_use_case(Settings(_env_file=None))

    first = await use_case.execute(value)
    second = await use_case.execute(value)

    assert first.status == second.status == AnalysisStatus.SUCCESS
    assert first.metrics.tool_calls == second.metrics.tool_calls
    assert first.metrics.iterations == second.metrics.iterations == 1
    assert len(first.analysis_results) == len(second.analysis_results)
    for left, right in zip(first.analysis_results, second.analysis_results, strict=True):
        assert left.method == right.method
        assert left.variables == right.variables
        assert left.result == pytest.approx(right.result)
        assert left.p_value == pytest.approx(right.p_value)
        assert left.effect_size == pytest.approx(right.effect_size)
        assert left.sample_size == right.sample_size


async def test_analysis_preserves_independent_success_after_failure(tmp_path: Path) -> None:
    path = tmp_path / "partial-failure.csv"
    write_validation_csv(path)
    context, datasets = await local_context(path)
    try:
        result = await execute(
            context,
            datasets,
            [
                ("success", "pearson", ["x", "linear"], None),
                ("failure", "pearson", ["x", "missing"], None),
            ],
        )
    finally:
        datasets.clear()

    assert result.status == AnalysisStatus.FAILED
    assert [item.status for item in result.update.analysis_results] == [
        AnalysisStatus.SUCCESS,
        AnalysisStatus.FAILED,
    ]
    assert result.update.analysis_results[0].result["correlation"] == pytest.approx(1.0)
    assert result.update.analysis_results[1].result is None
    assert result.update.metrics.tool_calls == 2


async def test_analysis_rejects_unknown_tool_without_counting_call(tmp_path: Path) -> None:
    path = tmp_path / "unknown-tool.csv"
    write_validation_csv(path)
    context, datasets = await local_context(path)
    plan = analysis_plan(
        context.dataset_id,
        [("unknown", "not_registered", ["x", "linear"], None)],
    )
    result = await AnalysisAgent(NoLLM(), build_statistical_tool_registry(datasets)).run(
        context.model_copy(update={"analysis_plan": plan})
    )
    datasets.clear()

    analysis = result.update.analysis_results[0]
    assert result.status == analysis.status == AnalysisStatus.FAILED
    assert analysis.result is analysis.p_value is analysis.effect_size is None
    assert result.update.metrics.tool_calls == 0


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
    path = tmp_path / "cancel.csv"
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
