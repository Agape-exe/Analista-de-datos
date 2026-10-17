from app.agents.base import SkeletonAgent
from app.application.dto.agent import AgentContext, AgentResult, AgentUpdate
from app.application.services.analysis_planning import DeterministicAnalysisPlanner
from app.domain.enums.statuses import AnalysisStatus
from app.ports.llm_provider import LLMProvider


class PlannerAgent(SkeletonAgent):
    name = "Planner"

    def __init__(
        self, llm: LLMProvider, planner: DeterministicAnalysisPlanner | None = None
    ) -> None:
        super().__init__(llm)
        self.planner = planner or DeterministicAnalysisPlanner()

    async def run(self, context: AgentContext) -> AgentResult:
        try:
            outcome = self.planner.plan(context)
        except ValueError as error:
            return AgentResult(
                agent_name=self.name,
                status=AnalysisStatus.FAILED,
                errors=[str(error)],
            )
        if outcome.plan is None:
            return AgentResult(
                agent_name=self.name,
                status=AnalysisStatus.SKIPPED,
                warnings=outcome.warnings,
            )
        return AgentResult(
            agent_name=self.name,
            status=AnalysisStatus.SUCCESS,
            update=AgentUpdate(analysis_plan=outcome.plan),
            warnings=outcome.warnings,
        )
