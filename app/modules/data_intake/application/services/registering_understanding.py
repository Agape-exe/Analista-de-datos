from app.modules.data_intake.ports.data_understanding import DataUnderstanding
from app.modules.data_intake.ports.dataset_provider import DatasetStore
from app.shared.contracts.analysis_input import AnalysisInput
from app.shared.contracts.data_understanding import DataUnderstandingResult
from app.shared.contracts.datasource import RegisteredDataset


class RegisteringDataUnderstanding:
    """Decorate any understanding port so its datasets become resolvable by tools."""

    def __init__(self, inner: DataUnderstanding, store: DatasetStore) -> None:
        self.inner = inner
        self.store = store

    async def understand(self, analysis_input: AnalysisInput) -> DataUnderstandingResult:
        result = await self.inner.understand(analysis_input)
        await self.store.register(
            RegisteredDataset(
                result.dataset, result.profile, result.data_dictionary, tuple(result.warnings)
            )
        )
        return result
