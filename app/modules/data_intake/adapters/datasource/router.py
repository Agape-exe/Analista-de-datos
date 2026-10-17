from collections.abc import Mapping

from app.modules.data_intake.ports.datasource import DataSource
from app.shared.application.errors import DataSourceError
from app.shared.contracts.analysis_input import SourceSpec
from app.shared.contracts.datasource import LoadedDataset


class DataSourceRouter:
    """Select injected adapters by source kind; SQL can be added without changing agents."""

    def __init__(self, sources: Mapping[str, DataSource]) -> None:
        self._sources = dict(sources)

    async def read(self, source: SourceSpec) -> LoadedDataset:
        adapter = self._sources.get(source.kind)
        if adapter is None:
            raise DataSourceError(f"No data source adapter configured for '{source.kind}'")
        return await adapter.read(source)
