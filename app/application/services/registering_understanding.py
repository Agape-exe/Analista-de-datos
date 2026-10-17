from app.application.dto.analysis_input import AnalysisInput
from app.application.dto.data_understanding import DataUnderstandingResult
from app.application.dto.datasource import RegisteredDataset
from app.ports.data_understanding import DataUnderstanding
from app.ports.dataset_provider import DatasetStore


class RegisteringDataUnderstanding:
    """Decorate any understanding port so its datasets become resolvable by tools."""

    def __init__(self, inner: DataUnderstanding, store: DatasetStore) -> None:
        self.inner = inner
        self.store = store

    async def understand(self, analysis_input: AnalysisInput) -> DataUnderstandingResult:
        result = await self.inner.understand(analysis_input)
        await self.store.register(RegisteredDataset(result.dataset, result.profile))
        return result
