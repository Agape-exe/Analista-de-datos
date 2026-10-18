import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from eda_support import make_dataset, store_with

from app.bootstrap import build_tool_registry
from app.modules.data_intake.adapters.datasource.delimited_source import PandasLocalTable
from app.modules.exploration.adapters.analytics.profiling.measures import outliers
from app.shared.config.settings import Settings
from app.shared.domain.enums.semantic_type import SemanticType
from app.shared.domain.models.analysis import ToolRequest

LEGACY = json.loads(
    (Path(__file__).parents[1] / "fixtures/outliers_before_aud018.json").read_text(encoding="utf-8")
)
NORMAL = list(range(-20, 21))
MAD_DETAIL_FIELDS = ("median", "mad", "lower_bound", "upper_bound", "examples", "example_rows")


@pytest.mark.parametrize("case", LEGACY, ids=lambda case: case["name"])
def test_all_existing_iqr_and_mad_results_match_frozen_preimplementation_results(case):
    values = np.asarray([np.nan if value is None else value for value in case["values"]])
    before = values.copy()
    actual = outliers(values, case["multiplier"], case["threshold"], case["limit"])
    rows = actual["iqr"].pop("example_rows")
    # AUD-017 adds MAD detail fields; every field that existed before stays identical.
    for key in MAD_DETAIL_FIELDS:
        actual["mad"].pop(key)
    assert actual == case["expected"]
    assert [row["value"] for row in rows] == actual["iqr"]["examples"]
    assert len(rows) <= case["limit"]
    np.testing.assert_array_equal(values, before)


@pytest.mark.parametrize(
    "values,positions",
    [
        ([500] + NORMAL + [-400], [0, 42]),
        ([None, 500] + NORMAL + [-400], [1, 43]),
        ([None, 500, None] + NORMAL + [-400, None], [1, 44]),
        ([None, None, 500] + NORMAL + [-400], [2, 44]),
        ([500] + NORMAL + [-400, None, None], [0, 42]),
        ([500] + NORMAL + [500, -400], [0, 42, 43]),
        (NORMAL * 2 + [-400, 500], [83, 82]),
        ([500, -500] + NORMAL + [500, -500], [0, 1, 43, 44]),
        ([-500] + NORMAL + [400], [0, 42]),
        ([500] + NORMAL[::-1] + [-400], [0, 42]),
        ([7] * 40, []),
        (NORMAL, []),
    ],
)
def test_positions_survive_nulls_repetitions_and_stable_ties(values, positions):
    numeric = np.asarray([np.nan if value is None else value for value in values])
    result = outliers(numeric, 1.5, 3.5, 20)
    rows = result["iqr"]["example_rows"]
    assert [row["row_index"] for row in rows] == positions
    assert len({row["row_index"] for row in rows}) == len(rows)
    assert [row["value"] for row in rows] == result["iqr"]["examples"]
    for row in rows:
        assert type(row["row_index"]) is int and 0 <= row["row_index"] < len(values)
        assert row["value"] == values[row["row_index"]]
        assert (
            row["value"] < result["iqr"]["lower_fence"]
            or row["value"] > result["iqr"]["upper_fence"]
        )


@pytest.mark.parametrize("limit", [0, 1, 2, 3])
def test_max_examples_bounds_both_arrays_without_affecting_counts(limit):
    values = np.asarray([500, -500] + NORMAL + [500, -500], dtype=float)
    result = outliers(values, 1.5, 3.5, limit)
    assert result["iqr"]["count"] == 4
    assert result["iqr"]["percentage"] == round(400 / len(values), 6)
    assert len(result["iqr"]["examples"]) == len(result["iqr"]["example_rows"]) == limit
    assert [row["row_index"] for row in result["iqr"]["example_rows"]] == [0, 1, 43, 44][:limit]


@pytest.mark.parametrize("values", [[], [None, None], [None, 500], list(range(19))])
async def test_tool_preserves_insufficient_sample_behavior(values):
    registered = make_dataset({"v": values}, {"v": SemanticType.NUMERIC})
    registry = build_tool_registry(Settings(_env_file=None), await store_with(registered))
    result = await registry.get("outliers").execute(
        ToolRequest(dataset_id="ds", method="outliers", variables=["v"])
    )
    assert result.status == "SKIPPED"
    assert result.result is None
    assert result.column_results["v"].status == "SKIPPED"
    assert result.column_results["v"].warnings == ["insufficient observations"]


async def test_multiple_columns_use_positions_not_dataframe_index_and_never_mutate():
    values = [None, 500] + NORMAL + [500, -400]
    other = values[2:] + values[:2]
    registered = make_dataset(
        {"a": values, "b": other}, {"a": SemanticType.NUMERIC, "b": SemanticType.NUMERIC}
    )
    frame = pd.DataFrame({"a": values, "b": other}, index=["same-label"] * len(values))
    before = frame.copy(deep=True)
    registered = replace(
        registered, dataset=replace(registered.dataset, table=PandasLocalTable(frame))
    )
    registry = build_tool_registry(
        Settings(_env_file=None, eda={"max_outlier_examples": 2}), await store_with(registered)
    )
    result = await registry.get("outliers").execute(
        ToolRequest(dataset_id="ds", method="outliers", variables=["a", "b"])
    )
    assert result.status == "SUCCESS"
    assert [row["row_index"] for row in result.result["a"]["iqr"]["example_rows"]] == [1, 43]
    assert [row["row_index"] for row in result.result["b"]["iqr"]["example_rows"]] == [41, 44]
    for name in ("a", "b"):
        for row in result.result[name]["iqr"]["example_rows"]:
            assert row["value"] == frame[name].iloc[row["row_index"]]
    pd.testing.assert_frame_equal(frame, before)


def test_legacy_json_safe_rounding_is_shared_by_values_and_references():
    result = outliers(np.asarray(NORMAL + [500.123456789]), 1.5, 3.5, 20)
    assert result["iqr"]["examples"] == [500.123457]
    assert result["iqr"]["example_rows"] == [{"row_index": 41, "value": 500.123457}]
