from app.modules.analysis.application.services.analysis_planning import DeterministicAnalysisPlanner
from app.modules.analysis.ports.planning import AnovaGroupSummarizer
from app.shared.application.base_agent import SkeletonAgent
from app.shared.contracts.agent import AgentContext, AgentResult, AgentUpdate
from app.shared.domain.enums.statuses import AnalysisStatus
from app.shared.ports.llm_provider import LLMProvider


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
            selection = context.input.control_selection
            requested_control = (
                {"variables": selection.variables, "control_variable": selection.control_variable}
                if selection is not None
                else {}
            )
            return AgentResult(
                agent_name=self.name,
                status=AnalysisStatus.SKIPPED,
                update=AgentUpdate(
                    planning_decisions=[
                        {"selected": False, "reason": warning} | requested_control
                        for warning in outcome.warnings
                    ]
                ),
                warnings=outcome.warnings,
            )
        return AgentResult(
            agent_name=self.name,
            status=AnalysisStatus.SUCCESS,
            update=AgentUpdate(
                analysis_plan=outcome.plan, planning_decisions=outcome.plan.decisions
            ),
            warnings=outcome.warnings,
        )
