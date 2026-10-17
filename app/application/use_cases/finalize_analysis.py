from time import perf_counter

from app.agents.insight import InsightAgent
from app.application.dto.agent import AgentContext
from app.application.dto.analysis_input import (
    AnalysisConfiguration,
    AnalysisInput,
    resolve_configuration,
)
from app.application.dto.finalization import FinalizationInput
from app.config.settings import Settings
from app.domain.models.report import AnalysisReport
from app.ports.repository import AnalysisRepository


class FinalizeAnalysis:
    """Integrate evidence delivered by other members; has no datasource or analytics calls."""

    def __init__(
        self, agent: InsightAgent, settings: Settings, repository: AnalysisRepository | None = None
    ) -> None:
        self.agent = agent
        self.settings = settings
        self.repository = repository

    async def execute(self, packet: FinalizationInput) -> AnalysisReport:
        started = perf_counter()
        # This source is only required by the common AgentContext. No file is read here.
        context = AgentContext(
            run_id=packet.run_id,
            input=AnalysisInput(
                source={"kind": "csv", "path": "not-read-by-finalization.csv"},
                user_question=packet.user_question,
            ),
            configuration=resolve_configuration(self.settings, AnalysisConfiguration()),
            dataset_profile=packet.dataset_profile,
            data_dictionary=packet.data_dictionary,
            analysis_results=packet.analysis_results,
            evidence=packet.evidence,
            relationship_assessments=packet.relationship_assessments,
            metrics=packet.metrics,
        )
        result = await self.agent.run(context)
        duration = perf_counter() - started
        metrics = result.update.metrics or packet.metrics.model_copy(deep=True)
        # Duration is only finalization when upstream timing is absent; scope is explicit below.
        previous_time = metrics.total_response_time
        metrics.total_response_time = (previous_time or 0) + duration
        if result.update.insights and metrics.time_to_first_insight is None:
            metrics.time_to_first_insight = (previous_time or 0) + duration
        report = AnalysisReport(
            run_id=packet.run_id,
            status=result.status,
            dataset_profile=packet.dataset_profile,
            data_dictionary=packet.data_dictionary,
            analysis_results=packet.analysis_results,
            evidence=packet.evidence,
            relationship_assessments=packet.relationship_assessments,
            insights=result.update.insights or [],
            metrics=metrics,
            warnings=packet.warnings + result.warnings,
            errors=result.errors,
            stage_statuses={"Insight": result.status},
            stage_durations={"Insight": duration},
            configuration={
                "execution_scope": "finalization_only"
                if previous_time is None
                else "upstream_plus_finalization"
            },
        )
        if self.repository is not None:
            await self.repository.save(report)
        return report
