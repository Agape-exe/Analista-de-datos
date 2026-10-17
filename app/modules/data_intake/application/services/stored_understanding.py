from app.modules.data_intake.ports.data_understanding import DataUnderstanding
from app.modules.data_intake.ports.dataset_provider import DatasetProvider
from app.shared.application.errors import DatasetNotFoundError, DataSourceError
from app.shared.contracts.analysis_input import AnalysisInput, StoredSourceSpec
from app.shared.contracts.data_understanding import DataUnderstandingResult
from app.shared.domain.models.data_dictionary import DataDictionary


class StoredDataUnderstanding:
    """Reuse an intake result for stored sources; delegate every other source.

    The stored profile and dictionary are returned as-is, so an analysis of an uploaded
    dataset neither re-reads the file nor re-classifies its columns.
    """

    def __init__(self, inner: DataUnderstanding, datasets: DatasetProvider) -> None:
        self.inner = inner
        self.datasets = datasets

    async def understand(self, analysis_input: AnalysisInput) -> DataUnderstandingResult:
        source = analysis_input.source
        if not isinstance(source, StoredSourceSpec):
            return await self.inner.understand(analysis_input)
        try:
            stored = await self.datasets.get(source.dataset_id)
        except DatasetNotFoundError as error:
            raise DataSourceError(str(error)) from error
        return DataUnderstandingResult(
            dataset=stored.dataset,
            profile=stored.profile,
            data_dictionary=stored.data_dictionary or DataDictionary(),
            profiling_time=0.0,
            warnings=list(stored.warnings),
        )
