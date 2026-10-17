from pathlib import Path

from app.bootstrap import build_agents, build_data_understanding
from app.modules.analysis.application.state import AgentState
from app.shared.application.tool_registry import ToolRegistry
from app.shared.config.settings import Settings
from app.shared.contracts.agent import AgentContext
from app.shared.contracts.analysis_input import AnalysisInput, resolve_configuration
from app.shared.contracts.llm import LLMRequest, LLMResponse


class MustNotCallLLM:
    async def generate(self, request: LLMRequest) -> LLMResponse:
        raise AssertionError("Skeleton must not call the LLM")


async def test_intake_succeeds_and_other_agents_skip_without_llm_calls() -> None:
    path = Path(__file__).parents[1] / "fixtures" / "sample.csv"
    value = AnalysisInput(source={"kind": "csv", "path": path})
    settings = Settings(_env_file=None)
    context = AgentContext(
        run_id="test",
        input=value,
        configuration=resolve_configuration(settings, value.configuration),
    )
    agents = build_agents(MustNotCallLLM(), ToolRegistry(), build_data_understanding(settings))
    assert len(agents) == 5
    for agent in agents:
        result = await agent.run(context)
        assert result.agent_name == agent.name
        if agent.name == "DataUnderstanding":
            assert result.status == "SUCCESS"
            assert result.update.dataset_profile.row_count == 3
            assert result.update.dataset_id == result.update.dataset_profile.dataset_id
            assert result.update.metrics.profiling_time >= 0
            assert "dataset" not in type(result.update).model_fields
            assert "table" not in result.update.model_dump_json()
        else:
            assert result.status == "SKIPPED"
            assert result.warnings


def test_agent_contracts_exclude_local_table_data() -> None:
    assert "dataset" not in AgentContext.model_fields
    assert "table" not in AgentContext.model_fields
    assert "dataset" not in AgentState.__annotations__
    assert "table" not in AgentState.__annotations__
