from app.agents.base import SkeletonAgent
from app.application.dto.agent import AgentContext, AgentResult, AgentUpdate
from app.application.dto.planning import AnovaGroupSummarizer
from app.application.services.analysis_planning import DeterministicAnalysisPlanner
from app.domain.enums.statuses import AnalysisStatus
from app.ports.llm_provider import LLMProvider


class PlannerAgent(SkeletonAgent):
    name = "Planner"

    def __init__(
        self,
        llm: LLMProvider,
        planner: DeterministicAnalysisPlanner | None = None,
        summarize_anova: AnovaGroupSummarizer | None = None,
    ) -> None:
        super().__init__(llm)
        self.planner = planner or DeterministicAnalysisPlanner()
        self.summarize_anova = summarize_anova

    async def run(self, context: AgentContext) -> AgentResult:
        try:
            if self.summarize_anova is not None and context.dataset_id is not None:
                pairs = self.planner.anova_pairs(context)
                summaries = self.summarize_anova(context.dataset_id, pairs)
                outcome = self.planner.plan(context, anova_groups=summaries)
            else:
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
