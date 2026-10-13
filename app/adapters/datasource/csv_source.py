import asyncio

from app.adapters.datasource.delimited_source import read_delimited
from app.application.dto.analysis_input import CsvSourceSpec, SourceSpec
from app.application.dto.datasource import LoadedDataset
from app.application.errors import DataSourceError


class CsvDataSource:
    """Read and validate CSV locally, preserving lexical identifiers."""

    async def read(self, source: SourceSpec) -> LoadedDataset:
        if not isinstance(source, CsvSourceSpec):
            raise DataSourceError("CsvDataSource supports only CSV sources")
        return await asyncio.to_thread(
            read_delimited, source.path, source.delimiter, source.encoding
        )
