from app.modules.exploration.adapters.analytics.association.ranking import RelationshipRankingTool
from app.shared.adapters.observability.telemetry import InstrumentedAnalyticsTool
from app.shared.application.dataset_registry import DatasetRegistry
from app.shared.application.errors import DatasetNotFoundError
from app.shared.config.settings import EdaSettings
from app.shared.contracts.datasource import RegisteredDataset
from app.shared.domain.models.analysis import AnalysisResult, ToolRequest
from app.shared.domain.models.dataset import DatasetProfile


class _ExecutionDatasetProvider:
    def __init__(self, dataset: RegisteredDataset) -> None:
        self.dataset = dataset

    async def get(self, dataset_id: str) -> RegisteredDataset:
        if dataset_id != self.dataset.dataset_id:
            raise DatasetNotFoundError(f"Dataset not available: {dataset_id}")
        return self.dataset


class RelationshipScreeningAdapter:
    """Adapt local EDA ranking to the workflow's RelationshipScreening port."""

    def __init__(self, datasets: DatasetRegistry, options: EdaSettings) -> None:
        self.datasets = datasets
        self.options = options

    async def screen(
        self, dataset_id: str, profile: DatasetProfile, minimum_sample_size: int
    ) -> AnalysisResult:
        loaded = self.datasets.get(dataset_id)
        # Preserve the existing analysis budget: screening is not counted as plan calls.
        tool = RelationshipRankingTool(
            _ExecutionDatasetProvider(RegisteredDataset(loaded, profile)),
            self.options,
            minimum_sample_size,
        )
        return await InstrumentedAnalyticsTool(tool, scope="screening").execute(
            ToolRequest(dataset_id=dataset_id, method=RelationshipRankingTool.name)
        )
