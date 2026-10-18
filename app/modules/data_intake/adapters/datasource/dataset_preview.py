import asyncio
import math
from datetime import date, datetime, time
from decimal import Decimal

import numpy as np
import pandas as pd

from app.modules.data_intake.adapters.datasource.delimited_source import PandasLocalTable
from app.modules.data_intake.domain.preview import (
    MAX_PREVIEW_BYTES,
    MAX_PREVIEW_CELLS,
    MAX_PREVIEW_COLUMNS,
    MAX_PREVIEW_LIMIT,
    MAX_PREVIEW_VALUE_BYTES,
    PreviewTooLargeError,
    PreviewUnsupportedError,
    PreviewValue,
    preview_value_size,
)
from app.shared.contracts.datasource import LoadedDataset


def _json_scalar(value: object) -> PreviewValue:
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        if isinstance(value, np.floating) and value.dtype.itemsize > 8:
            raise PreviewUnsupportedError
        number = float(value)
        if math.isnan(number):
            return None
        if not math.isfinite(number):
            raise PreviewUnsupportedError
        return number
    if isinstance(value, str):
        return value
    if isinstance(value, Decimal):
        if value.is_nan():
            return None
        if not value.is_finite():
            raise PreviewUnsupportedError
        if value.__sizeof__() > MAX_PREVIEW_VALUE_BYTES:
            raise PreviewTooLargeError
        return str(value)
    if isinstance(value, np.datetime64):
        return None if np.isnat(value) else pd.Timestamp(value).isoformat()
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    raise PreviewUnsupportedError


class PandasDatasetPreviewReader:
    """Slice before iterating; bounded tuples avoid full column/table conversion."""

    async def read(
        self, dataset: LoadedDataset, offset: int, limit: int
    ) -> list[list[PreviewValue]]:
        return await asyncio.to_thread(self._read, dataset, offset, limit)

    def _read(self, dataset: LoadedDataset, offset: int, limit: int) -> list[list[PreviewValue]]:
        if offset < 0 or not 0 <= limit <= MAX_PREVIEW_LIMIT:
            raise PreviewTooLargeError
        width = len(dataset.schema.columns)
        if width > MAX_PREVIEW_COLUMNS or width * limit > MAX_PREVIEW_CELLS:
            raise PreviewTooLargeError
        if not isinstance(dataset.table, PandasLocalTable):
            raise PreviewUnsupportedError
        frame = dataset.table.frame
        if frame.shape != (dataset.row_count, width) or list(frame.columns) != [
            column.name for column in dataset.schema.columns
        ]:
            raise PreviewUnsupportedError
        rows: list[list[PreviewValue]] = []
        size = 2
        for values in frame.iloc[offset : offset + limit].itertuples(index=False, name=None):
            row: list[PreviewValue] = []
            size += 3
            for value in values:
                try:
                    normalized = _json_scalar(value)
                    size += preview_value_size(normalized) + 1
                except (ValueError, OverflowError, UnicodeError) as error:
                    raise PreviewUnsupportedError from error
                if size > MAX_PREVIEW_BYTES:
                    raise PreviewTooLargeError
                row.append(normalized)
            rows.append(row)
        return rows
