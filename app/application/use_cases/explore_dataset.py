from app.analytics.registry import ToolRegistry
from app.application.dto.exploration import ToolRunRequest
from app.domain.models.analysis import AnalysisResult, ToolRequest
from app.ports.dataset_provider import DatasetProvider


class ExploreDataset:
    """Run registered tools on a dataset kept in memory after intake."""

    def __init__(self, datasets: DatasetProvider, tools: ToolRegistry) -> None:
        self.datasets = datasets
        self.tools = tools

    def tool_names(self) -> list[str]:
        return list(self.tools.names())

    async def run(self, dataset_id: str, tool: str, body: ToolRunRequest) -> AnalysisResult:
        """Raise DatasetNotFoundError or ToolRegistryError before executing anything."""
        await self.datasets.get(dataset_id)
        selected = self.tools.get(tool)
        return await selected.execute(
            ToolRequest(
                dataset_id=dataset_id,
                method=tool,
                variables=body.variables,
                parameters=body.parameters,
            )
        )
