import asyncio
from pathlib import Path

import pytest

from app.adapters.llm.disabled import DisabledLLMProvider
from app.analytics.registry import ToolRegistry
from app.application.dto.agent import AgentContext, AgentResult
from app.application.dto.analysis_input import AnalysisInput
from app.bootstrap import build_agents, build_data_understanding, build_use_case
from app.config.settings import Settings
from app.orchestration.graph import LangGraphWorkflow, initial_state


async def test_linear_graph_and_report() -> None:
    settings = Settings(_env_file=None)
    path = Path(__file__).parents[1] / "fixtures" / "sample.csv"
    value = AnalysisInput(
        source={"kind": "csv", "path": path},
        data_dictionary={"entries": [{"column_name": "age", "source": "manual"}]},
    )
    agents = build_agents(DisabledLLMProvider(), ToolRegistry(), build_data_understanding(settings))
    workflow = LangGraphWorkflow(settings, agents)
    completed = await workflow.graph.ainvoke(initial_state(value, settings))
    assert list(completed["stage_statuses"]) == [
        "DataUnderstanding",
        "Planner",
        "Analysis",
        "Critic",
        "Insight",
    ]
    assert completed["data_dictionary"].entries[0].source == "manual"
    assert len(completed["data_dictionary"].entries) == 3
    assert completed["stage_statuses"]["DataUnderstanding"] == "SUCCESS"
    assert completed["dataset_id"] == completed["dataset_profile"].dataset_id
    assert len(completed["stage_durations"]) == 5
    report = await build_use_case(settings).execute(value)
    assert report.status == "SKIPPED"
    assert report.insights == report.analysis_results == []
    assert report.metrics.total_response_time >= 0
    assert report.metrics.time_to_first_insight is None
    assert report.metrics.tool_calls == report.metrics.llm_calls == 0
    assert report.metrics.profiling_time >= 0
    assert report.dataset_profile.row_count == 3
    assert report.data_dictionary is not None
    assert report.model_validate_json(report.model_dump_json()) == report


async def test_independent_runs_have_different_ids() -> None:
    use_case = build_use_case(Settings(_env_file=None))
    path = Path(__file__).parents[1] / "fixtures" / "sample.csv"
    value = AnalysisInput(source={"kind": "csv", "path": path})
    first = await use_case.execute(value)
    second = await use_case.execute(value)
    assert first.run_id != second.run_id
    assert first.dataset_profile.dataset_id != second.dataset_profile.dataset_id


async def test_unusable_source_stops_before_planner(tmp_path: Path) -> None:
    value = AnalysisInput(source={"kind": "csv", "path": tmp_path / "missing.csv"})
    report = await build_use_case(Settings(_env_file=None)).execute(value)
    assert report.status == "FAILED"
    assert report.stage_statuses == {"DataUnderstanding": "FAILED"}
    assert report.errors
    assert report.dataset_profile is None
    assert report.metrics.profiling_time >= 0


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
