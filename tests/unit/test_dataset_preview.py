from dataclasses import replace
from datetime import UTC, date, datetime, time
from decimal import Decimal
from unittest.mock import AsyncMock

import numpy as np
import pandas as pd
import pytest
from preview_support import registered_frame
from pydantic import ValidationError

from app.modules.data_intake.adapters.datasource.dataset_preview import PandasDatasetPreviewReader
from app.modules.data_intake.adapters.datasource.delimited_source import PandasLocalTable
from app.modules.data_intake.application.dto import DatasetPreviewQuery
from app.modules.data_intake.application.use_cases.preview_dataset import PreviewDataset
from app.modules.data_intake.domain.preview import (
    MAX_PREVIEW_BYTES,
    MAX_PREVIEW_OFFSET,
    MAX_PREVIEW_VALUE_BYTES,
    PreviewTooLargeError,
    PreviewUnsupportedError,
)
from app.shared.application.errors import DatasetNotFoundError
from app.shared.contracts.datasource import LoadedDataset


async def test_use_case_resolves_via_provider_and_requests_only_range() -> None:
    registered = registered_frame(pd.DataFrame({"b": [3, 2, 1], "a": ["003", "002", "001"]}))
    provider = AsyncMock()
    provider.get.return_value = registered
    reader = AsyncMock()
    reader.read.return_value = [[2, "002"]]
    result = await PreviewDataset(provider, reader).execute(
        registered.dataset_id, DatasetPreviewQuery(offset=1, limit=1)
    )
    provider.get.assert_awaited_once_with(registered.dataset_id)
    reader.read.assert_awaited_once_with(registered.dataset, 1, 1)
    assert [column.name for column in result.columns] == ["b", "a"]
    assert result.rows == [[2, "002"]]
    assert result.returned_rows == 1 and result.total_rows == 3
    assert result.has_more and result.next_offset == 2


@pytest.mark.parametrize("offset", [3, 4, MAX_PREVIEW_OFFSET])
async def test_out_of_range_never_reads_table(offset: int) -> None:
    provider, reader = AsyncMock(), AsyncMock()
    provider.get.return_value = registered_frame(pd.DataFrame({"a": [1, 2, 3]}))
    result = await PreviewDataset(provider, reader).execute(
        "synthetic-preview", DatasetPreviewQuery(offset=offset)
    )
    assert result.rows == [] and result.returned_rows == 0
    assert result.offset == offset and result.limit == 20
    assert not result.has_more and result.next_offset is None
    reader.read.assert_not_awaited()


@pytest.mark.parametrize("frame", [pd.DataFrame(), pd.DataFrame({"a": pd.Series(dtype="string")})])
async def test_empty_provider_datasets(frame: pd.DataFrame) -> None:
    provider, reader = AsyncMock(), AsyncMock()
    provider.get.return_value = registered_frame(frame)
    result = await PreviewDataset(provider, reader).execute(
        "synthetic-preview", DatasetPreviewQuery()
    )
    assert result.rows == [] and result.total_rows == result.returned_rows == 0
    assert not result.has_more and result.next_offset is None
    reader.read.assert_not_awaited()


async def test_unknown_dataset_propagates_existing_error_without_reading() -> None:
    provider, reader = AsyncMock(), AsyncMock()
    provider.get.side_effect = DatasetNotFoundError("private internal detail")
    with pytest.raises(DatasetNotFoundError):
        await PreviewDataset(provider, reader).execute("missing", DatasetPreviewQuery())
    reader.read.assert_not_awaited()


@pytest.mark.parametrize(
    "query",
    [
        {"limit": 0},
        {"limit": -1},
        {"limit": 101},
        {"offset": -1},
        {"offset": MAX_PREVIEW_OFFSET + 1},
        {"limit": 1.5},
    ],
)
def test_query_rejects_invalid_paging(query: dict) -> None:
    with pytest.raises(ValidationError):
        DatasetPreviewQuery(**query)


@pytest.mark.parametrize("width,rows", [(1_001, 1), (501, 20)])
async def test_cell_and_column_budgets_reject_before_reader(width: int, rows: int) -> None:
    provider, reader = AsyncMock(), AsyncMock()
    provider.get.return_value = registered_frame(
        pd.DataFrame({f"c{i}": [1] * rows for i in range(width)})
    )
    with pytest.raises(PreviewTooLargeError):
        await PreviewDataset(provider, reader).execute("synthetic-preview", DatasetPreviewQuery())
    reader.read.assert_not_awaited()


async def test_schema_budget_checked_before_reader() -> None:
    provider, reader = AsyncMock(), AsyncMock()
    provider.get.return_value = registered_frame(
        pd.DataFrame({"x" * 60_000 + str(i): [1] for i in range(20)})
    )
    with pytest.raises(PreviewTooLargeError):
        await PreviewDataset(provider, reader).execute("synthetic-preview", DatasetPreviewQuery())
    reader.read.assert_not_awaited()


@pytest.mark.parametrize("rows", [[], [[1, 2]], [[1], [2]]])
async def test_inconsistent_reader_page_is_rejected(rows: list) -> None:
    provider, reader = AsyncMock(), AsyncMock()
    provider.get.return_value = registered_frame(pd.DataFrame({"a": [1]}))
    reader.read.return_value = rows
    with pytest.raises(PreviewUnsupportedError):
        await PreviewDataset(provider, reader).execute("synthetic-preview", DatasetPreviewQuery())


async def test_adapter_slices_large_frame_before_iteration_and_preserves_data(monkeypatch) -> None:
    frame = pd.DataFrame({"value": range(500_000), "id": ["001"] * 500_000})
    registered = registered_frame(frame)
    before = frame.iloc[123_456:123_459].to_dict("split")
    original_iter = pd.DataFrame.itertuples
    observed_shapes = []

    def bounded_iter(page, *args, **kwargs):
        observed_shapes.append(page.shape)
        assert len(page) == 3
        return original_iter(page, *args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("Full-table or full-column conversion is forbidden")

    with monkeypatch.context() as patch:
        patch.setattr(pd.DataFrame, "itertuples", bounded_iter)
        patch.setattr(pd.DataFrame, "to_dict", forbidden)
        patch.setattr(pd.DataFrame, "to_json", forbidden)
        patch.setattr(PandasLocalTable, "column", forbidden)
        result = await PandasDatasetPreviewReader().read(registered.dataset, 123_456, 3)
    assert result == [[123_456, "001"], [123_457, "001"], [123_458, "001"]]
    assert observed_shapes == [(3, 2)]
    assert frame.iloc[123_456:123_459].to_dict("split") == before
    assert frame.shape == (500_000, 2)


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
        (pd.NA, None),
        (pd.NaT, None),
        (float("nan"), None),
        (np.float64("nan"), None),
        (np.int64(42), 42),
        (np.uint64(2**63), 2**63),
        (np.float64(1.25), 1.25),
        (np.bool_(True), True),
        ("001", "001"),
        ("nan", "nan"),
        ("café", "café"),
        (Decimal("1.2300"), "1.2300"),
        (Decimal("NaN"), None),
        (date(2026, 10, 17), "2026-10-17"),
        (time(12, 30), "12:30:00"),
        (datetime(2026, 10, 17, 12, tzinfo=UTC), "2026-10-17T12:00:00+00:00"),
        (pd.Timestamp("2026-10-17T12:00:00.123456789Z"), "2026-10-17T12:00:00.123456789+00:00"),
        (np.datetime64("2026-10-17"), "2026-10-17T00:00:00"),
        (np.datetime64("NaT", "ns"), None),
    ],
)
async def test_adapter_normalizes_scalars(value: object, expected: object) -> None:
    registered = registered_frame(pd.DataFrame({"value": pd.Series([value], dtype=object)}))
    rows = await PandasDatasetPreviewReader().read(registered.dataset, 0, 1)
    assert rows == [[expected]]
    assert type(rows[0][0]) is type(expected)


@pytest.mark.parametrize(
    "value",
    [
        float("inf"),
        float("-inf"),
        Decimal("Infinity"),
        complex(1, 2),
        b"bytes",
        [1, 2],
        {"path": "private"},
        "\ud800",
    ],
)
async def test_unsupported_values_are_not_coerced_or_leaked(value: object) -> None:
    registered = registered_frame(pd.DataFrame({"value": pd.Series([value], dtype=object)}))
    with pytest.raises(PreviewUnsupportedError) as error:
        await PandasDatasetPreviewReader().read(registered.dataset, 0, 1)
    assert str(error.value) == ""


@pytest.mark.parametrize(
    "value",
    ["x" * MAX_PREVIEW_VALUE_BYTES, "ñ" * 40_000, "\n" * 40_000],
    ids=["oversized-ascii", "oversized-utf8", "oversized-json-escapes"],
)
async def test_large_cells_are_rejected_without_truncating(value: str) -> None:
    registered = registered_frame(pd.DataFrame({"value": [value]}))
    with pytest.raises(PreviewTooLargeError):
        await PandasDatasetPreviewReader().read(registered.dataset, 0, 1)
    assert registered.dataset.table.frame.iloc[0, 0] == value


async def test_total_page_budget_stops_before_reading_remaining_rows() -> None:
    registered = registered_frame(pd.DataFrame({"value": ["x" * 60_000] * 100}))
    with pytest.raises(PreviewTooLargeError):
        await PandasDatasetPreviewReader().read(registered.dataset, 0, 100)


async def test_final_response_includes_metadata_in_byte_budget() -> None:
    provider, reader = AsyncMock(), AsyncMock()
    provider.get.return_value = registered_frame(
        pd.DataFrame({"x" * 60_000 + str(i): [1] for i in range(10)})
    )
    reader.read.return_value = [["v" * 60_000] * 10]
    assert 600_000 < MAX_PREVIEW_BYTES
    with pytest.raises(PreviewTooLargeError):
        await PreviewDataset(provider, reader).execute(
            "synthetic-preview", DatasetPreviewQuery(limit=1)
        )


async def test_reader_rejects_legacy_tables_without_changing_localtable() -> None:
    class LegacyTable:
        def column(self, name):
            raise AssertionError("No full-column fallback allowed")

    dataset = replace(registered_frame(pd.DataFrame({"a": [1]})).dataset, table=LegacyTable())
    with pytest.raises(PreviewUnsupportedError):
        await PandasDatasetPreviewReader().read(dataset, 0, 1)


@pytest.mark.parametrize("offset,limit", [(-1, 1), (0, 101), (0, -1)])
async def test_reader_also_guards_internal_callers(offset: int, limit: int) -> None:
    dataset = registered_frame(pd.DataFrame({"a": [1]})).dataset
    with pytest.raises(PreviewTooLargeError):
        await PandasDatasetPreviewReader().read(dataset, offset, limit)


async def test_reader_rejects_schema_frame_mismatch() -> None:
    dataset = registered_frame(pd.DataFrame({"a": [1]})).dataset
    mismatch = LoadedDataset(dataset.dataset_id, dataset.schema, 2, dataset.table)
    with pytest.raises(PreviewUnsupportedError):
        await PandasDatasetPreviewReader().read(mismatch, 0, 1)
