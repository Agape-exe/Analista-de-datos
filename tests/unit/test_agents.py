from app.analytics.registry import ToolRegistry
from app.application.dto.agent import AgentContext
from app.application.dto.analysis_input import AnalysisInput, resolve_configuration
from app.application.dto.llm import LLMRequest, LLMResponse
from app.bootstrap import build_agents
from app.config.settings import Settings


class MustNotCallLLM:
    async def generate(self, request: LLMRequest) -> LLMResponse:
        raise AssertionError("Skeleton must not call the LLM")


async def test_all_agents_skip_without_llm_calls() -> None:
    value = AnalysisInput(source={"kind": "csv", "path": "not-read.csv"})
    context = AgentContext(
        run_id="test",
        input=value,
        configuration=resolve_configuration(Settings(_env_file=None), value.configuration),
    )
    agents = build_agents(MustNotCallLLM(), ToolRegistry())
    assert len(agents) == 5
    for agent in agents:
        result = await agent.run(context)
        assert result.status == "SKIPPED"
        assert result.agent_name == agent.name
        assert result.warnings
