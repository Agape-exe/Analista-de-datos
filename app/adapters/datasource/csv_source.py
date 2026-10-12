import asyncio
from dataclasses import dataclass
from uuid import uuid4

import pandas as pd

from app.application.dto.analysis_input import CsvSourceSpec, SourceSpec
from app.application.dto.datasource import LoadedDataset
from app.application.errors import DataSourceError
from app.domain.models.dataset import ColumnSchema, DatasetSchema


@dataclass(frozen=True)
class PandasLocalTable:
    """Keep pandas confined to the local data adapter."""

    frame: pd.DataFrame

    def column(self, name: str) -> list[object]:
        return self.frame[name].tolist()


class CsvDataSource:
    """Minimal CSV reader; no semantic inference or statistical profiling."""

    async def read(self, source: SourceSpec) -> LoadedDataset:
        if not isinstance(source, CsvSourceSpec):
            raise DataSourceError("CsvDataSource supports only CSV sources")
        return await asyncio.to_thread(self._read, source)

    def _read(self, source: CsvSourceSpec) -> LoadedDataset:
        try:
            frame = pd.read_csv(
                source.path, sep=source.delimiter, encoding=source.encoding, on_bad_lines="error"
            )
        except (OSError, UnicodeError, LookupError, ValueError, pd.errors.ParserError) as error:
            raise DataSourceError(f"Unable to read CSV: {source.path} ({error})") from error
        if frame.empty:
            raise DataSourceError(f"CSV contains no data rows: {source.path}")
        schema = DatasetSchema(
            columns=[
                ColumnSchema(
                    name=str(name), data_type=str(dtype), nullable=bool(frame[name].isna().any())
                )
                for name, dtype in frame.dtypes.items()
            ]
        )
        return LoadedDataset(
            dataset_id=str(uuid4()),
            schema=schema,
            row_count=len(frame),
            table=PandasLocalTable(frame),
        )
