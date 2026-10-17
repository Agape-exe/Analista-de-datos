from dataclasses import dataclass
from pathlib import Path

import pytest

from app.agents.analyst import AnalysisAgent
from app.analytics.factory import build_statistical_tool_registry
from app.analytics.registry import ToolRegistry
from app.application.dto.agent import AgentContext
from app.application.dto.analysis_input import AnalysisInput, resolve_configuration
from app.application.dto.datasource import LoadedDataset
from app.application.dto.llm import LLMRequest, LLMResponse
from app.application.services.dataset_registry import DatasetRegistry
from app.config.settings import Settings
from app.domain.enums.statuses import AnalysisStatus
from app.domain.models.analysis import (
    AnalysisPlan,
    AnalysisResult,
    AnalysisStep,
    Hypothesis,
    ToolRequest,
)
from app.domain.models.dataset import DatasetSchema


class MustNotCallLLM:
    async def generate(self, request: LLMRequest) -> LLMResponse:
        raise AssertionError("AnalysisAgent must not call the LLM")


@dataclass(frozen=True)
class MemoryTable:
    columns: dict[str, list[object]]

    def column(self, name: str) -> list[object]:
        return self.columns[name]


class RejectingTool:
    name = "rejecting"

    def supports(self, request: ToolRequest) -> bool:
        return False

    async def execute(self, request: ToolRequest) -> AnalysisResult:
        raise AssertionError("Unsupported tool must not execute")


class FailingTool:
    name = "failing"

    def supports(self, request: ToolRequest) -> bool:
        return request.method == self.name

    async def execute(self, request: ToolRequest) -> AnalysisResult:
        raise RuntimeError("expected failure")


def registry(dataset_id: str = "dataset-analysis") -> DatasetRegistry:
    datasets = DatasetRegistry()
    values = {
        "income": [float(value) for value in range(1, 31)],
        "spend": [float(value * 2) for value in range(1, 31)],
        "segment": ["a"] * 15 + ["b"] * 15,
        "region": ["north", "south"] * 15,
    }
    datasets.register(
        LoadedDataset(
            dataset_id=dataset_id,
            schema=DatasetSchema(
                columns=[{"name": name, "data_type": "number"} for name in values]
            ),
            row_count=30,
            table=MemoryTable(values),
        )
    )
    return datasets


def context(
    plan: AnalysisPlan | None,
    *,
    dataset_id: str = "dataset-analysis",
    configuration: dict[str, object] | None = None,
) -> AgentContext:
    value = AnalysisInput(
        source={"kind": "csv", "path": Path("analysis-agent.csv")},
        configuration=configuration or {},
    )
    return AgentContext(
        run_id="analysis-run",
        input=value,
        configuration=resolve_configuration(Settings(_env_file=None), value.configuration),
        dataset_id=dataset_id,
        analysis_plan=plan,
    )


def plan(*steps: AnalysisStep, hypotheses: list[Hypothesis] | None = None) -> AnalysisPlan:
    return AnalysisPlan(
        hypotheses=hypotheses or [Hypothesis(hypothesis_id="h-1", statement="Evaluate")],
        steps=list(steps),
    )


def step(
    step_id: str,
    method: str,
    variables: list[str],
    *,
    depends_on: list[str] | None = None,
    dataset_id: str = "dataset-analysis",
) -> AnalysisStep:
    return AnalysisStep(
        step_id=step_id,
        hypothesis_id="h-1",
        depends_on=depends_on or [],
        request=ToolRequest(dataset_id=dataset_id, method=method, variables=variables),
    )


async def test_analysis_agent_skips_without_plan() -> None:
    result = await AnalysisAgent(MustNotCallLLM(), build_statistical_tool_registry(registry())).run(
        context(None)
    )

    assert result.status == AnalysisStatus.SKIPPED
    assert result.update.analysis_results == []
    assert result.update.metrics.tool_calls == 0


async def test_analysis_agent_skips_empty_plan() -> None:
    result = await AnalysisAgent(MustNotCallLLM(), build_statistical_tool_registry(registry())).run(
        context(AnalysisPlan())
    )

    assert result.status == AnalysisStatus.SKIPPED
    assert result.update.analysis_results == []


async def test_analysis_agent_executes_pearson() -> None:
    result = await AnalysisAgent(MustNotCallLLM(), build_statistical_tool_registry(registry())).run(
        context(plan(step("pearson", "pearson", ["income", "spend"])))
    )

    assert result.status == AnalysisStatus.SUCCESS
    assert result.update.analysis_results[0].status == AnalysisStatus.SUCCESS
    assert result.update.analysis_results[0].result["correlation"] == pytest.approx(1.0)
    assert result.update.analysis_results[0].metadata["step_id"] == "pearson"
    assert result.update.metrics.tool_calls == 1


async def test_analysis_agent_executes_multiple_tools() -> None:
    result = await AnalysisAgent(MustNotCallLLM(), build_statistical_tool_registry(registry())).run(
        context(
            plan(
                step("pearson", "pearson", ["income", "spend"]),
                step("spearman", "spearman", ["income", "spend"]),
            )
        )
    )

    assert result.status == AnalysisStatus.SUCCESS
    assert [item.method for item in result.update.analysis_results] == ["pearson", "spearman"]
    assert result.update.metrics.tool_calls == 2


async def test_analysis_agent_executes_mixed_statistics() -> None:
    steps = [
        step("chi", "chi_square", ["segment", "region"]),
        step("cramers", "cramers_v", ["segment", "region"]),
        step("anova", "anova_one_way", ["segment", "income"]),
    ]
    result = await AnalysisAgent(MustNotCallLLM(), build_statistical_tool_registry(registry())).run(
        context(plan(*steps, hypotheses=[Hypothesis(hypothesis_id="h-1", statement="Evaluate")]))
    )

    assert result.status == AnalysisStatus.SUCCESS
    assert all(item.status == AnalysisStatus.SUCCESS for item in result.update.analysis_results)
    assert {item.method for item in result.update.analysis_results} == {
        "chi_square",
        "cramers_v",
        "anova_one_way",
    }


async def test_analysis_agent_rejects_unknown_tool() -> None:
    result = await AnalysisAgent(MustNotCallLLM(), build_statistical_tool_registry(registry())).run(
        context(plan(step("unknown", "unknown", ["income", "spend"])))
    )

    assert result.status == AnalysisStatus.FAILED
    assert result.update.analysis_results[0].status == AnalysisStatus.FAILED
    assert result.update.metrics.tool_calls == 0


async def test_analysis_agent_rejects_unsupported_tool_request() -> None:
    tools = ToolRegistry()
    tools.register(RejectingTool())
    result = await AnalysisAgent(MustNotCallLLM(), tools).run(
        context(plan(step("rejecting", "rejecting", [])))
    )

    assert result.status == AnalysisStatus.FAILED
    assert result.update.analysis_results[0].status == AnalysisStatus.FAILED
    assert result.update.metrics.tool_calls == 0


async def test_analysis_agent_handles_failed_tool() -> None:
    tools = ToolRegistry()
    tools.register(FailingTool())
    result = await AnalysisAgent(MustNotCallLLM(), tools).run(
        context(plan(step("failing", "failing", [])))
    )

    assert result.status == AnalysisStatus.FAILED
    assert result.update.analysis_results[0].result is None
    assert result.update.analysis_results[0].p_value is None
    assert result.update.metrics.tool_calls == 1


async def test_analysis_agent_respects_tool_call_limit() -> None:
    result = await AnalysisAgent(MustNotCallLLM(), build_statistical_tool_registry(registry())).run(
        context(
            plan(
                step("first", "pearson", ["income", "spend"]),
                step("second", "spearman", ["income", "spend"]),
            ),
            configuration={"analysis": {"max_tool_calls": 1}},
        )
    )

    assert result.status == AnalysisStatus.SUCCESS
    assert [item.status for item in result.update.analysis_results] == [
        AnalysisStatus.SUCCESS,
        AnalysisStatus.SKIPPED,
    ]
    assert result.update.metrics.tool_calls == 1


async def test_analysis_agent_respects_dependencies() -> None:
    result = await AnalysisAgent(MustNotCallLLM(), build_statistical_tool_registry(registry())).run(
        context(
            plan(
                step("after", "spearman", ["income", "spend"], depends_on=["before"]),
                step("before", "pearson", ["income", "spend"]),
            )
        )
    )

    assert result.status == AnalysisStatus.SUCCESS
    assert [item.metadata["step_id"] for item in result.update.analysis_results] == [
        "before",
        "after",
    ]


async def test_analysis_agent_skips_dependents_after_failure() -> None:
    tools = build_statistical_tool_registry(registry())
    tools.register(FailingTool())
    result = await AnalysisAgent(MustNotCallLLM(), tools).run(
        context(
            plan(
                step("bad", "failing", []),
                step("blocked", "pearson", ["income", "spend"], depends_on=["bad"]),
            )
        )
    )

    assert result.status == AnalysisStatus.FAILED
    assert [item.status for item in result.update.analysis_results] == [
        AnalysisStatus.FAILED,
        AnalysisStatus.SKIPPED,
    ]
    assert result.update.metrics.tool_calls == 1


async def test_analysis_agent_rejects_cyclic_dependencies() -> None:
    result = await AnalysisAgent(MustNotCallLLM(), build_statistical_tool_registry(registry())).run(
        context(
            plan(
                step("first", "pearson", ["income", "spend"], depends_on=["second"]),
                step("second", "spearman", ["income", "spend"], depends_on=["first"]),
            )
        )
    )

    assert result.status == AnalysisStatus.FAILED
    assert result.update.analysis_results == []
    assert result.update.metrics.tool_calls == 0


async def test_analysis_agent_rejects_invalid_plan_references() -> None:
    result = await AnalysisAgent(MustNotCallLLM(), build_statistical_tool_registry(registry())).run(
        context(
            plan(
                step("duplicate", "pearson", ["income", "spend"]),
                step(
                    "duplicate",
                    "spearman",
                    ["income", "spend"],
                    depends_on=["missing"],
                ).model_copy(update={"hypothesis_id": "unknown"}),
            )
        )
    )

    assert result.status == AnalysisStatus.FAILED
    assert result.update.analysis_results == []
    assert any("duplicate" in error for error in result.errors)
    assert any("unknown hypothesis" in error for error in result.errors)
    assert any("does not exist" in error for error in result.errors)


async def test_analysis_agent_rejects_dataset_id_mismatch() -> None:
    result = await AnalysisAgent(MustNotCallLLM(), build_statistical_tool_registry(registry())).run(
        context(plan(step("pearson", "pearson", ["income", "spend"], dataset_id="other")))
    )

    assert result.status == AnalysisStatus.FAILED
    assert result.update.analysis_results == []


async def test_analysis_agent_preserves_success_when_another_step_fails() -> None:
    result = await AnalysisAgent(MustNotCallLLM(), build_statistical_tool_registry(registry())).run(
        context(
            plan(
                step("success", "pearson", ["income", "spend"]),
                step("failure", "pearson", ["income", "missing"]),
            )
        )
    )

    assert result.status == AnalysisStatus.FAILED
    assert [item.status for item in result.update.analysis_results] == [
        AnalysisStatus.SUCCESS,
        AnalysisStatus.FAILED,
    ]


async def test_analysis_agent_tracks_execution_metrics() -> None:
    result = await AnalysisAgent(MustNotCallLLM(), build_statistical_tool_registry(registry())).run(
        context(plan(step("pearson", "pearson", ["income", "spend"])))
    )

    assert result.update.metrics.analytics_time is not None
    assert result.update.metrics.analytics_time >= 0
    assert result.update.metrics.tool_calls == 1
    assert "table" not in result.update.model_dump_json()


def test_statistical_tool_registry_registers_all_authorized_tools() -> None:
    tools = build_statistical_tool_registry(registry())

    assert tools.names() == (
        "additive_identity",
        "analyze_subgroups",
        "anova_one_way",
        "chi_square",
        "correlation_without_outliers",
        "cramers_v",
        "partial_correlation",
        "pearson",
        "spearman",
    )


async def test_analysis_agent_preserves_dataset_isolation() -> None:
    first_datasets = registry("first")
    second_datasets = registry("second")
    first = AnalysisAgent(MustNotCallLLM(), build_statistical_tool_registry(first_datasets))
    second = AnalysisAgent(MustNotCallLLM(), build_statistical_tool_registry(second_datasets))

    first_result = await first.run(
        context(
            plan(step("first", "pearson", ["income", "spend"], dataset_id="first")),
            dataset_id="first",
        )
    )
    second_result = await second.run(
        context(
            plan(step("second", "pearson", ["income", "spend"], dataset_id="second")),
            dataset_id="second",
        )
    )

    assert first_result.status == second_result.status == AnalysisStatus.SUCCESS
    first_datasets.clear()
    assert second_datasets.ids() == ("second",)
