import asyncio
import math
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd

from app.modules.data_intake.adapters.datasource.delimited_source import PandasLocalTable
from app.modules.data_intake.domain.quality import (
    QualityCounts,
    QualityLimits,
    QualityTooLargeError,
    QualityUnsupportedError,
)
from app.shared.contracts.datasource import RegisteredDataset


def _object_key(value: object, limits: QualityLimits) -> tuple:
    """Equality keys preserve scalar families; all genuine nulls share one key.

    Never coerce text to numbers or stringify arbitrary objects. In mixed object
    columns True, 1, 1.0, Decimal('1') and '1' are distinct scalar families.
    """
    if value is None or value is pd.NA or value is pd.NaT:
        return ("missing",)
    if isinstance(value, (np.datetime64, np.timedelta64)):
        if np.isnat(value):
            return ("missing",)
        try:
            value = pd.Timestamp(value) if isinstance(value, np.datetime64) else pd.Timedelta(value)
        except (ValueError, OverflowError) as error:
            raise QualityUnsupportedError from error
    if isinstance(value, np.bool_):
        value = bool(value)
    elif isinstance(value, np.integer):
        value = int(value)
    elif isinstance(value, np.floating) and value.dtype.itemsize <= 8:
        value = float(value)
    if type(value) in (str, np.str_):
        if len(value) > limits.max_value_chars:
            raise QualityTooLargeError
        return ("text", value)
    if type(value) is bool:
        return ("boolean", value)
    if type(value) is int:
        if value.bit_length() > limits.max_value_chars * 8:
            raise QualityTooLargeError
        return ("integer", value)
    if type(value) is float:
        if math.isnan(value):
            return ("missing",)
        if not math.isfinite(value):
            raise QualityUnsupportedError
        return ("float", value)
    if type(value) is Decimal:
        if value.is_snan():
            raise QualityUnsupportedError
        if value.is_nan():
            return ("missing",)
        if not value.is_finite():
            raise QualityUnsupportedError
        if value.__sizeof__() > limits.max_value_chars:
            raise QualityTooLargeError
        return ("decimal", value)
    if type(value) in (datetime, date, time, timedelta, pd.Timestamp, pd.Timedelta):
        return (type(value).__name__, value)
    raise QualityUnsupportedError


class PandasDatasetQualityReader:
    """Exact per-column factorization then full-row equality on integer codes.

    Pandas factorization resolves hash collisions by equality; this is not a hash
    estimate. Missing masks and object keys are allocated one column at a time.
    No full DataFrame copy, JSON conversion, column() materialization or source I/O.
    """

    async def measure(self, dataset: RegisteredDataset, limits: QualityLimits) -> QualityCounts:
        # Await the worker to completion so shared capacity remains reserved for its lifetime.
        worker = asyncio.create_task(asyncio.to_thread(self._measure, dataset, limits))
        try:
            return await asyncio.shield(worker)
        except asyncio.CancelledError:
            # Repeated cancellation must not let the still-running thread escape
            # the HTTP operation-capacity reservation.
            while not worker.done():
                try:
                    await asyncio.shield(worker)
                except asyncio.CancelledError:
                    continue
            worker.result()
            raise

    def _measure(self, registered: RegisteredDataset, limits: QualityLimits) -> QualityCounts:
        dataset = registered.dataset
        limits.check_shape(dataset.row_count, len(dataset.schema.columns))
        if not isinstance(dataset.table, PandasLocalTable):
            raise QualityUnsupportedError
        frame = dataset.table.frame
        names = [column.name for column in dataset.schema.columns]
        if frame.shape != (dataset.row_count, len(names)) or list(frame.columns) != names:
            raise QualityUnsupportedError
        if int(frame.memory_usage(index=False, deep=True).sum()) > limits.max_data_bytes:
            raise QualityTooLargeError
        if not names or not len(frame):
            return QualityCounts((0,) * len(names), 0, 0, 0)
        profile = registered.profile
        cached = (
            {column.column_name: column.missing_count for column in profile.columns}
            if profile.dataset_id == dataset.dataset_id
            and profile.row_count == len(frame)
            and [column.column_name for column in profile.columns] == names
            else {}
        )
        incomplete = np.zeros(len(frame), dtype=bool)
        missing_counts = []
        codes = {}
        for name in names:
            series = frame[name]
            dtype = series.dtype
            if pd.api.types.is_object_dtype(dtype):
                keys = [_object_key(value, limits) for value in series.array]
                mask = np.fromiter((key == ("missing",) for key in keys), bool, len(keys))
                values = pd.Series(keys, dtype=object)
            elif isinstance(dtype, pd.StringDtype):
                if series.str.len().gt(limits.max_value_chars).any():
                    raise QualityTooLargeError
                mask = series.isna().to_numpy(dtype=bool)
                values = series
            elif (
                pd.api.types.is_integer_dtype(dtype)
                or pd.api.types.is_bool_dtype(dtype)
                or pd.api.types.is_float_dtype(dtype)
                or pd.api.types.is_datetime64_any_dtype(dtype)
                or pd.api.types.is_timedelta64_dtype(dtype)
            ):
                if pd.api.types.is_float_dtype(dtype) and (
                    dtype.itemsize > 8 or series.isin([np.inf, -np.inf]).any()
                ):
                    raise QualityUnsupportedError
                mask = series.isna().to_numpy(dtype=bool)
                values = series
            else:
                raise QualityUnsupportedError
            count = cached.get(name)
            missing_counts.append(int(mask.sum()) if count is None else count)
            incomplete |= mask
            try:
                codes[name] = pd.factorize(values, sort=False)[0]
            except (TypeError, ValueError, OverflowError) as error:
                raise QualityUnsupportedError from error
        encoded = pd.DataFrame(codes, copy=False)
        additional = int(encoded.duplicated(keep="first").sum())
        repeated = int(encoded.duplicated(keep=False).sum())
        return QualityCounts(
            tuple(missing_counts), int(incomplete.sum()), additional, repeated - additional
        )
