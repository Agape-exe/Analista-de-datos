import asyncio

from app.modules.data_intake.adapters.datasource.delimited_source import read_delimited
from app.shared.application.errors import DataSourceError
from app.shared.contracts.analysis_input import SourceSpec, TsvSourceSpec
from app.shared.contracts.datasource import LoadedDataset


class TsvDataSource:
    """TSV adapter sharing the same validation and local table contract as CSV."""

    async def read(self, source: SourceSpec) -> LoadedDataset:
        if not isinstance(source, TsvSourceSpec):
            raise DataSourceError("TsvDataSource supports only TSV sources")
        return await asyncio.to_thread(read_delimited, source.path, "\t", source.encoding)
