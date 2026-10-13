from pathlib import Path

from app.analytics.registry import ToolRegistry
from app.application.dto.agent import AgentContext
from app.application.dto.analysis_input import AnalysisInput, resolve_configuration
from app.application.dto.llm import LLMRequest, LLMResponse
from app.bootstrap import build_agents, build_data_understanding
from app.config.settings import Settings


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
        else:
            assert result.status == "SKIPPED"
            assert result.warnings
