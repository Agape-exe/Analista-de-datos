from app.modules.analysis.ports.relationship_screening import RelationshipScreening
from app.shared.application.errors import DatasetRegistryError
from app.shared.contracts.agent import AgentContext, AgentResult, AgentUpdate
from app.shared.domain.enums.statuses import AnalysisStatus
from app.shared.domain.models.analysis import AssociationResult, RankedRelationship


class AssociationAgent:
    """Screen every eligible column pair so planning starts from ranked candidates.

    Screening is advisory: when it cannot run, the workflow continues without it.
    """

    name = "Association"

    def __init__(self, screening: RelationshipScreening) -> None:
        self.screening = screening

    async def run(self, context: AgentContext) -> AgentResult:
        profile = context.dataset_profile
        if context.dataset_id is None or profile is None:
            return self._skipped("Association screening requires dataset metadata.")
        try:
            result = await self.screening.screen(
                context.dataset_id, profile, context.configuration.analysis.minimum_sample_size
            )
        except DatasetRegistryError as error:
            return self._skipped(f"Association screening unavailable: {error}")
        if result.status != AnalysisStatus.SUCCESS or not isinstance(result.result, dict):
            return self._skipped(*(f"Association screening: {item}" for item in result.warnings))
        top = result.result.get("top_relationships")
        ranked = (
            [RankedRelationship.model_validate(item) for item in top]
            if isinstance(top, list)
            else []
        )
        if not ranked:
            return AgentResult(
                agent_name=self.name,
                status=AnalysisStatus.SKIPPED,
                update=AgentUpdate(screening_summary=result.result),
                warnings=result.warnings
                + ["Association screening found no significant relationships."],
            )
        return AgentResult(
            agent_name=self.name,
            status=AnalysisStatus.SUCCESS,
            update=AgentUpdate(
                associations=to_associations(ranked), screening_summary=result.result
            ),
            warnings=result.warnings,
        )

    def _skipped(self, *warnings: str) -> AgentResult:
        return AgentResult(
            agent_name=self.name, status=AnalysisStatus.SKIPPED, warnings=list(warnings)
        )


def to_associations(ranked: list[RankedRelationship]) -> list[AssociationResult]:
    """Flatten ranked pairs, strongest first; each primary test precedes its supporting ones."""
    associations: list[AssociationResult] = []
    for relationship in ranked:
        associations.append(
            AssociationResult(
                method=relationship.method,
                variables=[relationship.x, relationship.y],
                strength=relationship.strength,
                p_value=relationship.p_value,
            )
        )
        associations.extend(relationship.supporting)
    return associations
