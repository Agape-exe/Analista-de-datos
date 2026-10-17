from dataclasses import dataclass
from pathlib import Path

import pytest

from app.agents.analyst import AnalysisAgent
from app.agents.planner import PlannerAgent
from app.analytics.factory import build_statistical_tool_registry
from app.analytics.registry import ToolRegistry
from app.application.dto.agent import AgentContext
from app.application.dto.analysis_input import AnalysisInput, resolve_configuration
from app.application.dto.datasource import LoadedDataset
from app.application.services.dataset_registry import DatasetRegistry
from app.config.settings import Settings
from app.domain.enums.semantic_type import SemanticType
from app.domain.enums.statuses import AnalysisStatus
from app.domain.models.analysis import AnalysisPlan, AnalysisStep, Hypothesis, ToolRequest
from app.domain.models.dataset import ColumnProfile, DatasetProfile, DatasetSchema


class NoLLM:
    async def generate(self, request):
        raise AssertionError("Planner and Analysis must not call an LLM")


@dataclass(frozen=True)
class MemoryTable:
    columns: dict[str, list[object]]

    def column(self, name: str) -> list[object]:
        return self.columns[name]


def context(
    columns: list[tuple[str, SemanticType]],
    *,
    question: str | None = None,
    configuration: dict[str, object] | None = None,
) -> AgentContext:
    value = AnalysisInput(
        source={"kind": "csv", "path": Path("metadata.csv")},
        user_question=question,
        configuration=configuration or {},
    )
    profile = DatasetProfile(
        dataset_id="dataset",
        row_count=40,
        columns=[
            ColumnProfile(
                column_name=name,
                data_type="number" if kind == SemanticType.NUMERIC else "string",
                semantic_type=kind,
                unique_count=10,
            )
            for name, kind in columns
        ],
    )
    return AgentContext(
        run_id="planner-analysis-main",
        input=value,
        configuration=resolve_configuration(Settings(_env_file=None), value.configuration),
        dataset_id="dataset",
        dataset_profile=profile,
    )


async def test_planner_selects_supported_methods_and_respects_fast_budget() -> None:
    result = await PlannerAgent(NoLLM()).run(
        context(
            [
                ("income", SemanticType.NUMERIC),
                ("spending", SemanticType.NUMERIC),
                ("region", SemanticType.CATEGORICAL),
                ("segment", SemanticType.CATEGORICAL),
            ],
            question="Evaluate spending and income by region and segment.",
            configuration={"analysis": {"max_hypotheses": 3, "max_tool_calls": 8}},
        )
    )

    assert result.status == AnalysisStatus.SUCCESS
    assert result.update.analysis_plan is not None
    assert len(result.update.analysis_plan.hypotheses) <= 3
    assert len(result.update.analysis_plan.steps) <= 8
    assert {step.request.method for step in result.update.analysis_plan.steps} >= {
        "pearson",
        "spearman",
        "chi_square",
        "cramers_v",
        "anova_one_way",
    }


async def test_planner_only_adds_partial_correlation_for_exact_control() -> None:
    planned = await PlannerAgent(NoLLM()).run(
        context(
            [
                ("x", SemanticType.NUMERIC),
                ("y", SemanticType.NUMERIC),
                ("age", SemanticType.NUMERIC),
            ],
            question="Evaluar x e y controlando por age.",
        )
    )
    methods = {step.request.method for step in planned.update.analysis_plan.steps}
    assert "partial_correlation" in methods
    partial = next(
        step
        for step in planned.update.analysis_plan.steps
        if step.request.method == "partial_correlation"
    )
    assert partial.request.parameters == {"control_variable": "age"}

    ambiguous = await PlannerAgent(NoLLM()).run(
        context(
            [
                ("x", SemanticType.NUMERIC),
                ("y", SemanticType.NUMERIC),
                ("age", SemanticType.NUMERIC),
            ],
            question="The controllerage metric is relevant to x and y.",
        )
    )
    assert all(
        step.request.method != "partial_correlation"
        for step in ambiguous.update.analysis_plan.steps
    )


async def test_analysis_executes_registered_tool_and_preserves_trace() -> None:
    datasets = DatasetRegistry()
    datasets.register(
        LoadedDataset(
            dataset_id="dataset",
            schema=DatasetSchema(
                columns=[{"name": "x", "data_type": "number"}, {"name": "y", "data_type": "number"}]
            ),
            row_count=4,
            table=MemoryTable({"x": [1, 2, 3, 4], "y": [2, 4, 6, 8]}),
        )
    )
    value = context([("x", SemanticType.NUMERIC), ("y", SemanticType.NUMERIC)])
    plan = AnalysisPlan(
        hypotheses=[Hypothesis(hypothesis_id="h1", statement="Evaluate x and y")],
        steps=[
            AnalysisStep(
                step_id="pearson-step",
                hypothesis_id="h1",
                request=ToolRequest(dataset_id="dataset", method="pearson", variables=["x", "y"]),
            )
        ],
    )
    result = await AnalysisAgent(NoLLM(), build_statistical_tool_registry(datasets)).run(
        value.model_copy(update={"analysis_plan": plan})
    )

    assert result.status == AnalysisStatus.SUCCESS
    analysis = result.update.analysis_results[0]
    assert analysis.result == {"correlation": pytest.approx(1.0)}
    assert analysis.metadata["step_id"] == "pearson-step"
    assert analysis.metadata["hypothesis_id"] == "h1"
    assert result.update.metrics.tool_calls == 1
    datasets.clear()


async def test_analysis_rejects_invalid_plan_before_invoking_tools() -> None:
    value = context([("x", SemanticType.NUMERIC), ("y", SemanticType.NUMERIC)])
    plan = AnalysisPlan(
        hypotheses=[
            Hypothesis(hypothesis_id="duplicate", statement="one"),
            Hypothesis(hypothesis_id="duplicate", statement="two"),
        ],
        steps=[
            AnalysisStep(
                step_id="unknown",
                hypothesis_id="duplicate",
                request=ToolRequest(dataset_id="dataset", method="unknown", variables=[]),
            )
        ],
    )
    result = await AnalysisAgent(NoLLM(), ToolRegistry()).run(
        value.model_copy(update={"analysis_plan": plan})
    )

    assert result.status == AnalysisStatus.FAILED
    assert result.update.analysis_results == []
    assert "duplicate hypothesis ids" in result.errors[0]


async def test_analysis_zero_budget_skips_without_calling_tools() -> None:
    value = context(
        [("x", SemanticType.NUMERIC), ("y", SemanticType.NUMERIC)],
        configuration={"analysis": {"max_tool_calls": 0}},
    )
    plan = AnalysisPlan(
        hypotheses=[Hypothesis(hypothesis_id="h1", statement="Evaluate x and y")],
        steps=[
            AnalysisStep(
                step_id="step",
                hypothesis_id="h1",
                request=ToolRequest(dataset_id="dataset", method="unknown", variables=[]),
            )
        ],
    )
    result = await AnalysisAgent(NoLLM(), ToolRegistry()).run(
        value.model_copy(update={"analysis_plan": plan})
    )

    assert result.status == AnalysisStatus.SKIPPED
    assert result.update.analysis_results[0].status == AnalysisStatus.SKIPPED
    assert result.update.metrics.tool_calls == 0
