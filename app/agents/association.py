from app.analytics.association.ranking import RelationshipRankingTool
from app.application.dto.agent import AgentContext, AgentResult, AgentUpdate
from app.application.dto.datasource import RegisteredDataset
from app.application.errors import DatasetNotFoundError, DatasetRegistryError
from app.application.services.dataset_registry import DatasetRegistry
from app.config.settings import EdaSettings
from app.domain.enums.statuses import AnalysisStatus
from app.domain.models.analysis import AssociationResult, RankedRelationship, ToolRequest


class _ExecutionDatasetProvider:
    """Expose the execution-local dataset to EDA tools under the DatasetProvider port."""

    def __init__(self, dataset: RegisteredDataset) -> None:
        self.dataset = dataset

    async def get(self, dataset_id: str) -> RegisteredDataset:
        if dataset_id != self.dataset.dataset_id:
            raise DatasetNotFoundError(f"Dataset not available: {dataset_id}")
        return self.dataset


class AssociationAgent:
    """Screen every eligible column pair so planning starts from ranked candidates.

    Screening is advisory: when it cannot run, the workflow continues without it.
    """

    name = "Association"

    def __init__(self, datasets: DatasetRegistry, options: EdaSettings) -> None:
        self.datasets = datasets
        self.options = options

    async def run(self, context: AgentContext) -> AgentResult:
        profile = context.dataset_profile
        if context.dataset_id is None or profile is None:
            return self._skipped("Association screening requires dataset metadata.")
        try:
            loaded = self.datasets.get(context.dataset_id)
        except DatasetRegistryError as error:
            return self._skipped(f"Association screening unavailable: {error}")
        # Not instrumented: tool_calls measures the analysis plan budget, not screening.
        tool = RelationshipRankingTool(
            _ExecutionDatasetProvider(RegisteredDataset(loaded, profile)),
            self.options,
            context.configuration.analysis.minimum_sample_size,
        )
        result = await tool.execute(
            ToolRequest(dataset_id=context.dataset_id, method=RelationshipRankingTool.name)
        )
        if result.status != AnalysisStatus.SUCCESS or not isinstance(result.result, dict):
            return self._skipped(*(f"Association screening: {item}" for item in result.warnings))
        top = result.result.get("top_relationships")
        ranked = (
            [RankedRelationship.model_validate(item) for item in top]
            if isinstance(top, list)
            else []
        )
        if not ranked:
            return self._skipped("Association screening found no significant relationships.")
        return AgentResult(
            agent_name=self.name,
            status=AnalysisStatus.SUCCESS,
            update=AgentUpdate(associations=to_associations(ranked)),
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
