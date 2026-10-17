import asyncio

from app.modules.data_intake.adapters.datasource.delimited_source import read_delimited
from app.shared.application.errors import DataSourceError
from app.shared.contracts.analysis_input import CsvSourceSpec, SourceSpec
from app.shared.contracts.datasource import LoadedDataset


class CsvDataSource:
    """Read and validate CSV locally, preserving lexical identifiers."""

    async def read(self, source: SourceSpec) -> LoadedDataset:
        if not isinstance(source, CsvSourceSpec):
            raise DataSourceError("CsvDataSource supports only CSV sources")
        return await asyncio.to_thread(
            read_delimited, source.path, source.delimiter, source.encoding
        )
