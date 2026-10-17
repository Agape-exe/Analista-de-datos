from pathlib import Path

from app.modules.analysis.application.agents.analyst import AnalysisAgent
from app.shared.application.tool_registry import ToolRegistry
from app.shared.config.settings import Settings
from app.shared.contracts.agent import AgentContext
from app.shared.contracts.analysis_input import AnalysisInput, resolve_configuration
from app.shared.contracts.llm import LLMRequest, LLMResponse
from app.shared.domain.enums.statuses import AnalysisStatus
from app.shared.domain.models.analysis import AnalysisPlan, AnalysisStep, Hypothesis, ToolRequest


class MustNotCallLLM:
    async def generate(self, request: LLMRequest) -> LLMResponse:
        raise AssertionError("AnalysisAgent must not call the LLM")


def context(plan: AnalysisPlan, configuration: dict[str, object] | None = None) -> AgentContext:
    value = AnalysisInput(
        source={"kind": "csv", "path": Path("validation.csv")},
        configuration=configuration or {},
    )
    return AgentContext(
        run_id="robustness",
        input=value,
        configuration=resolve_configuration(Settings(_env_file=None), value.configuration),
        dataset_id="dataset",
        analysis_plan=plan,
    )


def step() -> AnalysisStep:
    return AnalysisStep(
        step_id="step",
        hypothesis_id="duplicate",
        request=ToolRequest(dataset_id="dataset", method="unknown", variables=[]),
    )


async def test_analysis_rejects_duplicate_hypothesis_ids() -> None:
    value = context(
        AnalysisPlan(
            hypotheses=[
                Hypothesis(hypothesis_id="duplicate", statement="first"),
                Hypothesis(hypothesis_id="duplicate", statement="second"),
            ],
            steps=[step()],
        )
    )

    result = await AnalysisAgent(MustNotCallLLM(), ToolRegistry()).run(value)

    assert result.status == AnalysisStatus.FAILED
    assert result.update.analysis_results == []
    assert "duplicate hypothesis ids" in result.errors[0]


async def test_analysis_zero_tool_budget() -> None:
    value = context(
        AnalysisPlan(
            hypotheses=[Hypothesis(hypothesis_id="duplicate", statement="valid")],
            steps=[step()],
        ),
        {"analysis": {"max_tool_calls": 0}},
    )

    result = await AnalysisAgent(MustNotCallLLM(), ToolRegistry()).run(value)

    assert result.status == AnalysisStatus.SKIPPED
    assert result.update.analysis_results[0].status == AnalysisStatus.SKIPPED
    assert result.update.metrics.tool_calls == 0
