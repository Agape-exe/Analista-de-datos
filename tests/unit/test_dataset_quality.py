import asyncio
import sys
import threading
from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import numpy as np
import pandas as pd
import pytest
from preview_support import registered_frame

from app.modules.data_intake.adapters.datasource.dataset_quality import PandasDatasetQualityReader
from app.modules.data_intake.adapters.datasource.delimited_source import PandasLocalTable
from app.modules.data_intake.application.use_cases.evaluate_dataset_quality import (
    EvaluateDatasetQuality,
)
from app.modules.data_intake.domain.quality import (
    QualityCounts,
    QualityLimits,
    QualityTooLargeError,
    QualityUnsupportedError,
    evaluate_quality_rules,
)
from app.shared.application.errors import DatasetNotFoundError


async def quality(frame, limits=None):
    registered = registered_frame(frame)
    provider = AsyncMock()
    provider.get.return_value = registered
    return await EvaluateDatasetQuality(provider, PandasDatasetQualityReader(), limits).execute(
        registered.dataset_id
    )


async def test_use_case_resolves_through_ports_and_builds_exact_contract():
    provider, reader = AsyncMock(), AsyncMock()
    registered = registered_frame(pd.DataFrame({"id": ["001", "002", "002"], "v": [1, None, None]}))
    provider.get.return_value = registered
    reader.measure.return_value = QualityCounts((0, 2), 2, 1, 1)
    result = await EvaluateDatasetQuality(provider, reader).execute(registered.dataset_id)
    provider.get.assert_awaited_once_with(registered.dataset_id)
    reader.measure.assert_awaited_once_with(registered, QualityLimits())
    assert result.total_rows == 3 and result.total_columns == 2 and result.total_cells == 6
    assert result.missing.missing_cells == result.missing.incomplete_rows == 2
    assert result.missing.complete_rows == 1
    assert result.missing.missing_percentage == pytest.approx(100 / 3)
    assert result.missing.columns[1].missing_percentage == pytest.approx(200 / 3)
    assert result.duplicates.duplicate_rows == result.duplicates.duplicate_groups == 1
    assert result.duplicates.duplicate_percentage == pytest.approx(100 / 3)
    assert [r.status for r in result.rules] == ["FAIL", "FAIL"]


@pytest.mark.parametrize(
    "frame,missing,incomplete,duplicates,groups",
    [
        (pd.DataFrame({"a": [1, 2], "b": [3, 4]}), (0, 0), 0, 0, 0),
        (pd.DataFrame({"a": [1, None, None], "b": [None, 2, None]}), (2, 2), 3, 0, 0),
        (pd.DataFrame({"a": [1, None, 2], "b": [3, 4, None]}), (1, 1), 2, 0, 0),
        (pd.DataFrame({"a": [1, 1, 1], "b": [2, 3, 4]}), (0, 0), 0, 0, 0),
        (pd.DataFrame({"a": [1, 1, 1, 2, 2, 3]}), (0,), 0, 3, 2),
        (
            pd.DataFrame({"id": ["001", "002", "002"], "n": ["Ana", "Luis", "Luis"]}),
            (0, 0),
            0,
            1,
            1,
        ),
        (
            pd.DataFrame({"a": pd.Series([None, pd.NA, float("nan"), pd.NaT], dtype=object)}),
            (4,),
            4,
            3,
            1,
        ),
        (
            pd.DataFrame({"a": pd.Series([None, "NA", "NULL", "NaN", "nan", ""], dtype=object)}),
            (1,),
            1,
            0,
            0,
        ),
        (
            pd.DataFrame({"a": pd.Series([True, 1, 1.0, "1", Decimal("1"), True], dtype=object)}),
            (0,),
            0,
            1,
            1,
        ),
        (pd.DataFrame({"a": pd.Series([True, False, True], dtype="boolean")}), (0,), 0, 1, 1),
        (pd.DataFrame({"a": pd.Series([1, None, 1], dtype="Int64")}), (1,), 1, 1, 1),
        (pd.DataFrame({"a": pd.Series([1.25, None, 1.25], dtype="Float64")}), (1,), 1, 1, 1),
        (pd.DataFrame({"a": pd.Series(["001", "1", "001"], dtype="string")}), (0,), 0, 1, 1),
        (
            pd.DataFrame({"a": pd.to_datetime(["2026-01-01", None, "2026-01-01"], utc=True)}),
            (1,),
            1,
            1,
            1,
        ),
        (pd.DataFrame({"a": pd.to_timedelta([1, None, 1], unit="D")}), (1,), 1, 1, 1),
        (
            pd.DataFrame(
                {"a": pd.Series([Decimal("1.20"), Decimal("1.2"), Decimal("NaN")], dtype=object)}
            ),
            (1,),
            1,
            1,
            1,
        ),
    ],
)
async def test_exact_metrics_and_type_preserving_duplicates(
    frame, missing, incomplete, duplicates, groups
):
    result = await quality(frame)
    assert tuple(c.missing_count for c in result.missing.columns) == missing
    assert result.missing.missing_cells == sum(missing)
    assert result.missing.incomplete_rows == incomplete
    assert result.missing.complete_rows == len(frame) - incomplete
    assert result.duplicates.duplicate_rows == duplicates
    assert result.duplicates.duplicate_groups == groups


@pytest.mark.parametrize(
    "value",
    [
        np.int64(3),
        np.float64(1.2),
        np.bool_(True),
        date(2026, 1, 1),
        datetime(2026, 1, 1),
        timedelta(days=1),
    ],
)
async def test_supported_object_scalar_families(value):
    result = await quality(pd.DataFrame({"a": pd.Series([value, value], dtype=object)}))
    assert result.duplicates.duplicate_rows == 1


@pytest.mark.parametrize(
    "frame",
    [pd.DataFrame(), pd.DataFrame({"a": pd.Series(dtype="string")}), pd.DataFrame(index=range(2))],
)
async def test_empty_provider_tables_have_no_invented_passes(frame):
    result = await quality(frame)
    assert result.status == "NOT_EVALUATED"
    assert result.missing.missing_percentage == result.duplicates.duplicate_percentage == 0
    assert all(
        rule.status == "NOT_EVALUATED" and rule.observed_count is None and rule.reason
        for rule in result.rules
    )


@pytest.mark.parametrize(
    "missing,duplicates,expected",
    [(0, 0, ["PASS", "PASS"]), (2, 0, ["FAIL", "PASS"]), (0, 1, ["PASS", "FAIL"])],
)
def test_pure_rules_separate_evidence_from_decisions(missing, duplicates, expected):
    rules = evaluate_quality_rules(3, 2, missing, duplicates)
    assert [rule.status for rule in rules] == expected
    assert [rule.observed_count for rule in rules] == [missing, duplicates]
    assert [rule.rule_id for rule in rules] == ["NO_MISSING_VALUES", "NO_DUPLICATE_ROWS"]


async def test_missing_dataset_does_not_call_reader():
    provider, reader = AsyncMock(), AsyncMock()
    provider.get.side_effect = DatasetNotFoundError("private detail")
    with pytest.raises(DatasetNotFoundError):
        await EvaluateDatasetQuality(provider, reader).execute("missing")
    reader.measure.assert_not_awaited()


@pytest.mark.parametrize(
    "value",
    [
        [1],
        {"private": 1},
        b"bytes",
        complex(1, 2),
        float("inf"),
        Decimal("Infinity"),
        Decimal("sNaN"),
        object(),
    ],
)
async def test_unsupported_values_fail_without_leaking_content(value):
    with pytest.raises(QualityUnsupportedError) as error:
        await quality(pd.DataFrame({"a": pd.Series([value], dtype=object)}))
    assert str(error.value) == ""


@pytest.mark.parametrize(
    "frame",
    [
        pd.DataFrame({"a": [np.inf]}),
        pd.DataFrame({"a": pd.Categorical(["a"])}),
        pd.DataFrame({"a": [complex(1, 2)]}),
    ],
)
async def test_unsupported_native_types_and_non_finite_values(frame):
    with pytest.raises(QualityUnsupportedError):
        await quality(frame)


@pytest.mark.parametrize(
    "limits", [QualityLimits(max_rows=1), QualityLimits(max_columns=1), QualityLimits(max_cells=3)]
)
async def test_shape_limits_reject_before_reader(limits):
    provider, reader = AsyncMock(), AsyncMock()
    provider.get.return_value = registered_frame(pd.DataFrame({"a": [1, 2], "b": [1, 2]}))
    with pytest.raises(QualityTooLargeError):
        await EvaluateDatasetQuality(provider, reader, limits).execute("synthetic-preview")
    reader.measure.assert_not_awaited()


@pytest.mark.parametrize(
    "limits",
    [
        QualityLimits(max_data_bytes=1),
        QualityLimits(max_value_chars=3),
        QualityLimits(max_response_bytes=30),
    ],
)
async def test_memory_value_and_response_budgets(limits):
    with pytest.raises(QualityTooLargeError):
        await quality(pd.DataFrame({"a": ["value"]}), limits)


def test_invalid_policy_is_configuration_error():
    with pytest.raises(ValueError):
        QualityLimits(max_cells=0)


async def test_cached_profile_counts_remain_consistent_with_row_masks():
    registered = registered_frame(pd.DataFrame({"a": [1, None]}))
    registered.profile.columns[0].missing_count = 1
    counts = await PandasDatasetQualityReader().measure(registered, QualityLimits())
    assert counts == QualityCounts((1,), 1, 0, 0)


async def test_no_mutation_no_full_column_or_json_conversion(monkeypatch):
    frame = pd.DataFrame(
        {"id": pd.Series(["001", "001", "002"], dtype="string"), "a": [1, 1, None]}
    )
    before = frame.copy(deep=True)

    def forbidden(*args, **kwargs):
        raise AssertionError("No full-frame copy, column materialization or JSON")

    with monkeypatch.context() as patch:
        patch.setattr(PandasLocalTable, "column", forbidden)
        patch.setattr(pd.DataFrame, "to_json", forbidden)
        patch.setattr(pd.DataFrame, "to_dict", forbidden)
        patch.setattr(pd.DataFrame, "copy", forbidden)
        result = await quality(frame)
    pd.testing.assert_frame_equal(frame, before)
    assert result.duplicates.duplicate_rows == 1


async def test_incompatible_table_and_schema_return_controlled_errors():
    registered = registered_frame(pd.DataFrame({"a": [1]}))
    reader = PandasDatasetQualityReader()
    for dataset in [
        replace(registered.dataset, row_count=2),
        replace(registered.dataset, table=object()),
    ]:
        with pytest.raises(QualityUnsupportedError):
            await reader.measure(replace(registered, dataset=dataset), QualityLimits())


@pytest.mark.parametrize(
    "counts",
    [
        QualityCounts((), 0, 0, 0),
        QualityCounts((3,), 1, 0, 0),
        QualityCounts((0,), 3, 0, 0),
        QualityCounts((0,), 0, 2, 1),
        QualityCounts((0,), 0, 0, 1),
        QualityCounts((1,), 0, 0, 0),
    ],
)
async def test_inconsistent_port_measurements_are_rejected(counts):
    provider, reader = AsyncMock(), AsyncMock()
    provider.get.return_value = registered_frame(pd.DataFrame({"a": [1, 2]}))
    reader.measure.return_value = counts
    with pytest.raises(QualityUnsupportedError):
        await EvaluateDatasetQuality(provider, reader).execute("synthetic-preview")


async def test_cancellation_waits_for_worker_before_releasing_caller(monkeypatch):
    started, release = threading.Event(), threading.Event()
    reader = PandasDatasetQualityReader()
    original = reader._measure

    def blocked(*args):
        started.set()
        release.wait(5)
        return original(*args)

    monkeypatch.setattr(reader, "_measure", blocked)
    task = asyncio.create_task(
        reader.measure(registered_frame(pd.DataFrame({"a": [1]})), QualityLimits())
    )
    try:
        assert await asyncio.to_thread(started.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_hash_collisions_do_not_create_false_duplicate_rows():
    first, second = 1, 1 + sys.hash_info.modulus
    assert hash(first) == hash(second)
    result = await quality(pd.DataFrame({"a": pd.Series([first, second, first], dtype=object)}))
    assert result.duplicates.duplicate_rows == result.duplicates.duplicate_groups == 1


@pytest.mark.parametrize(
    "value",
    [
        np.datetime64("NaT", "ns"),
        np.timedelta64("NaT", "ns"),
        np.datetime64("2026-01-01"),
        np.timedelta64(1, "D"),
        np.str_("001"),
    ],
)
async def test_numpy_temporal_and_text_scalars_in_object_columns(value):
    result = await quality(pd.DataFrame({"a": pd.Series([value, value], dtype=object)}))
    assert result.duplicates.duplicate_rows == 1
    expected_missing = (
        2 if isinstance(value, (np.datetime64, np.timedelta64)) and np.isnat(value) else 0
    )
    assert result.missing.missing_cells == expected_missing


@pytest.mark.parametrize("dtype", [object, "string"])
async def test_default_oversized_text_cell_is_rejected(dtype):
    with pytest.raises(QualityTooLargeError):
        await quality(pd.DataFrame({"a": pd.Series(["x" * 65_537], dtype=dtype)}))


async def test_default_row_budget_rejects_without_factorization(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No factorization beyond row budget")

    monkeypatch.setattr(pd, "factorize", forbidden)
    with pytest.raises(QualityTooLargeError):
        await quality(pd.DataFrame({"a": range(250_001)}))


async def test_final_response_budget_includes_rules_and_metrics():
    with pytest.raises(QualityTooLargeError):
        await quality(pd.DataFrame({"a": [1]}), QualityLimits(max_response_bytes=512))


async def test_schema_budget_precedes_data_reader():
    provider, reader = AsyncMock(), AsyncMock()
    provider.get.return_value = registered_frame(pd.DataFrame({"x" * 500: [1]}))
    with pytest.raises(QualityTooLargeError):
        await EvaluateDatasetQuality(
            provider, reader, QualityLimits(max_response_bytes=100)
        ).execute("synthetic-preview")
    reader.measure.assert_not_awaited()


async def test_profile_from_another_dataset_is_not_used():
    registered = registered_frame(pd.DataFrame({"a": [1, None]}))
    registered.profile.dataset_id = "other"
    registered.profile.columns[0].missing_count = 0
    counts = await PandasDatasetQualityReader().measure(registered, QualityLimits())
    assert counts.missing_by_column == (1,)
