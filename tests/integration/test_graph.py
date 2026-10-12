import asyncio

import pytest

from app.adapters.llm.disabled import DisabledLLMProvider
from app.analytics.registry import ToolRegistry
from app.application.dto.agent import AgentContext, AgentResult
from app.application.dto.analysis_input import AnalysisInput
from app.bootstrap import build_agents, build_use_case
from app.config.settings import Settings
from app.orchestration.graph import LangGraphWorkflow, initial_state


async def test_linear_graph_and_report() -> None:
    settings = Settings(_env_file=None)
    value = AnalysisInput(
        source={"kind": "csv", "path": "not-read.csv"},
        data_dictionary={"entries": [{"column_name": "age", "source": "manual"}]},
    )
    workflow = LangGraphWorkflow(settings, build_agents(DisabledLLMProvider(), ToolRegistry()))
    completed = await workflow.graph.ainvoke(initial_state(value, settings))
    assert list(completed["stage_statuses"]) == [
        "DataUnderstanding",
        "Planner",
        "Analysis",
        "Critic",
        "Insight",
    ]
    assert completed["data_dictionary"] == value.data_dictionary
    assert len(completed["stage_durations"]) == 5
    report = await build_use_case(settings).execute(value)
    assert report.status == "SKIPPED"
    assert report.insights == report.analysis_results == []
    assert report.metrics.total_response_time >= 0
    assert report.metrics.time_to_first_insight is None
    assert report.metrics.tool_calls == report.metrics.llm_calls == 0
    assert report.model_validate_json(report.model_dump_json()) == report


async def test_independent_runs_have_different_ids() -> None:
    use_case = build_use_case(Settings(_env_file=None))
    value = AnalysisInput(source={"kind": "csv", "path": "not-read.csv"})
    first = await use_case.execute(value)
    second = await use_case.execute(value)
    assert first.run_id != second.run_id


def test_unimplemented_provider_is_not_silently_disabled() -> None:
    from app.application.errors import LLMDisabledError

    settings = Settings(llm={"provider": "unknown"}, _env_file=None)
    with pytest.raises(LLMDisabledError):
        build_use_case(settings)


class FailingAgent:
    name = "Failure"

    async def run(self, context: AgentContext) -> AgentResult:
        raise RuntimeError("Expected stage failure")


class WaitingAgent:
    name = "Waiting"

    async def run(self, context: AgentContext) -> AgentResult:
        await asyncio.Event().wait()
        raise AssertionError("Unreachable")


@pytest.mark.parametrize("agent", [FailingAgent(), WaitingAgent()])
async def test_workflow_failure_and_timeout_record_elapsed(
    agent: FailingAgent | WaitingAgent,
) -> None:
    settings = Settings(performance={"timeout_seconds": 0.05}, _env_file=None)
    workflow = LangGraphWorkflow(settings, [agent])
    report = await workflow.run(AnalysisInput(source={"kind": "csv", "path": "not-read.csv"}))
    assert report.status == "FAILED"
    assert report.errors
    assert report.metrics.total_response_time >= 0
    assert report.insights == []
