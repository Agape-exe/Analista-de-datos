from collections.abc import Mapping

from app.application.dto.analysis_input import SourceSpec
from app.application.dto.datasource import LoadedDataset
from app.application.errors import DataSourceError
from app.ports.datasource import DataSource


class DataSourceRouter:
    """Select injected adapters by source kind; SQL can be added without changing agents."""

    def __init__(self, sources: Mapping[str, DataSource]) -> None:
        self._sources = dict(sources)

    async def read(self, source: SourceSpec) -> LoadedDataset:
        adapter = self._sources.get(source.kind)
        if adapter is None:
            raise DataSourceError(f"No data source adapter configured for '{source.kind}'")
        return await adapter.read(source)
