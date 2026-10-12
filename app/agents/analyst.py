from app.agents.base import SkeletonAgent
from app.analytics.registry import ToolRegistry
from app.ports.llm_provider import LLMProvider


class AnalysisAgent(SkeletonAgent):
    name = "Analysis"

    def __init__(self, llm: LLMProvider, tools: ToolRegistry) -> None:
        super().__init__(llm)
        self.tools = tools
