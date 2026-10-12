from app.application.dto.agent import AgentContext, AgentResult, AgentUpdate
from app.domain.enums.statuses import AnalysisStatus
from app.ports.llm_provider import LLMProvider


class SkeletonAgent:
    """Invocable stage with explicit omissions until its capability is implemented."""

    name: str

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def run(self, context: AgentContext) -> AgentResult:
        return self.skipped()

    def skipped(self, update: AgentUpdate | None = None) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            status=AnalysisStatus.SKIPPED,
            update=update if update is not None else AgentUpdate(),
            warnings=[f"{self.name}: capability not implemented in the initial skeleton."],
        )
