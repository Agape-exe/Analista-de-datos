import asyncio

from app.adapters.datasource.delimited_source import read_delimited
from app.application.dto.analysis_input import SourceSpec, TsvSourceSpec
from app.application.dto.datasource import LoadedDataset
from app.application.errors import DataSourceError


class TsvDataSource:
    """TSV adapter sharing the same validation and local table contract as CSV."""

    async def read(self, source: SourceSpec) -> LoadedDataset:
        if not isinstance(source, TsvSourceSpec):
            raise DataSourceError("TsvDataSource supports only TSV sources")
        return await asyncio.to_thread(read_delimited, source.path, "\t", source.encoding)
