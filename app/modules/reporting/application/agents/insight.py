import json

from app.modules.reporting.application.services.insights import generate_insights
from app.shared.contracts.agent import AgentContext, AgentResult, AgentUpdate
from app.shared.contracts.llm import LLMRequest
from app.shared.domain.enums.statuses import AnalysisStatus
from app.shared.domain.models.metrics import ExperimentMetrics
from app.shared.ports.llm_provider import LLMProvider


class InsightAgent:
    """Evidence-first insights. Optional LLM selects existing, validated insights only."""

    name = "Insight"

    def __init__(self, llm: LLMProvider, *, use_llm: bool = False) -> None:
        self.llm = llm
        self.use_llm = use_llm

    async def run(self, context: AgentContext) -> AgentResult:
        try:
            insights, warnings = generate_insights(
                context.analysis_results,
                context.evidence,
                context.relationship_assessments,
                context.data_dictionary,
            )
        except ValueError as error:
            return AgentResult(
                agent_name=self.name, status=AnalysisStatus.FAILED, errors=[str(error)]
            )
        metrics = context.metrics.model_copy(deep=True)
        if insights and self.use_llm:
            metrics.llm_calls = (metrics.llm_calls or 0) + 1
            try:
                response = await self.llm.generate(
                    LLMRequest(
                        run_id=context.run_id,
                        instructions=(
                            'Prioritize insights. Return JSON {"insight_ids": [...]} '
                            "containing each supplied ID exactly once. Do not write new statements."
                        ),
                        summary={
                            "user_question": context.input.user_question,
                            "insights": [item.model_dump(mode="json") for item in insights],
                        },
                    )
                )
                if response.tokens_used is not None:
                    metrics.tokens_used = (metrics.tokens_used or 0) + response.tokens_used
                payload = json.loads(response.content)
                ids = payload["insight_ids"]
                known = {item.insight_id: item for item in insights}
                if not isinstance(ids, list) or len(ids) != len(known) or set(ids) != set(known):
                    raise ValueError("LLM must return each existing insight ID exactly once")
                insights = [known[item_id] for item_id in ids]
            except Exception as error:
                warnings.append(f"LLM unavailable; deterministic order: {type(error).__name__}")
        status = AnalysisStatus.SUCCESS if insights else AnalysisStatus.SKIPPED
        return AgentResult(
            agent_name=self.name,
            status=status,
            update=AgentUpdate(
                insights=insights, metrics=ExperimentMetrics.model_validate(metrics.model_dump())
            ),
            warnings=warnings,
        )
