from dataclasses import dataclass

import pytest

from app.analytics.factory import build_statistical_tool_registry
from app.application.dto.datasource import LoadedDataset
from app.application.services.dataset_registry import DatasetRegistry
from app.domain.models.analysis import ToolRequest
from app.domain.models.dataset import DatasetSchema


@dataclass
class Table:
    columns: dict[str, list[object]]

    def column(self, name):
        return self.columns[name]


def setup(columns):
    datasets = DatasetRegistry()
    datasets.register(
        LoadedDataset(
            dataset_id="local",
            row_count=len(next(iter(columns.values()))),
            schema=DatasetSchema(
                columns=[{"name": key, "data_type": "unknown"} for key in columns]
            ),
            table=Table(columns),
        )
    )
    return build_statistical_tool_registry(datasets)


def request(method, variables=None, parameters=None):
    return ToolRequest(
        dataset_id="local",
        method=method,
        variables=variables or ["x", "y"],
        parameters=parameters or {},
    )


async def test_outlier_check_measures_change_without_modifying_source():
    columns = {"x": list(range(20)) + [1000], "y": list(range(20)) + [-1000]}
    tool = setup(columns)
    result = await tool.execute(request("correlation_without_outliers"))
    assert result.status == "SUCCESS"
    assert result.effect_size == pytest.approx(1)
    assert result.sample_size == 20
    assert result.metadata["removed_count"] == 1
    assert result.metadata["original_sample_size"] == 21
    assert columns["x"][-1] == 1000 and len(columns["x"]) == 21


async def test_zero_outliers_is_a_measured_check():
    result = await setup({"x": list(range(20)), "y": list(range(20))}).execute(
        request("correlation_without_outliers")
    )
    assert result.status == "SUCCESS"
    assert result.metadata["removed_count"] == 0
    assert result.sample_size == 20 and result.effect_size == pytest.approx(1)


async def test_degenerate_filtered_sample_stays_unmeasured():
    result = await setup({"x": [0] * 20 + [1, 2, 3], "y": [0] * 20 + [3, 2, 1]}).execute(
        request("correlation_without_outliers")
    )
    assert result.status == "SKIPPED"
    assert result.result is result.p_value is result.effect_size is None
    assert result.metadata["removed_count"] == 3


async def test_subgroups_measure_known_opposing_correlations():
    result = await setup(
        {
            "x": list(range(10)) * 2,
            "y": list(range(10)) + list(range(0, -10, -1)),
            "district": ["a"] * 10 + ["b"] * 10,
        }
    ).execute(request("analyze_subgroups", parameters={"group_by": "district"}))
    assert result.status == "SUCCESS" and result.sample_size == 20
    assert [item["correlation"] for item in result.result["groups"]] == pytest.approx([1, -1])
    assert result.metadata["excluded_groups"] == []


async def test_small_and_constant_subgroups_are_explicitly_excluded():
    result = await setup(
        {
            "x": [1, 2] + list(range(10)) + [1] * 10,
            "y": [1, 2] + list(range(10)) + list(range(10)),
            "district": ["a"] * 2 + ["b"] * 10 + ["c"] * 10,
        }
    ).execute(request("analyze_subgroups", parameters={"group_by": "district"}))
    assert result.status == "SKIPPED" and result.result is None
    assert {item["group"] for item in result.metadata["excluded_groups"]} == {"a", "c"}


@pytest.mark.parametrize(
    "total,confirmed,count", [([4.0, 6.0, 8.0], True, 3), ([4.0, 6.0, 9.0], False, 2)]
)
async def test_additive_identity_is_measured_not_assumed_from_its_name(total, confirmed, count):
    result = await setup({"x": [1.0, 2.0, 3.0], "y": [3.0, 4.0, 5.0], "total": total}).execute(
        request("additive_identity", ["x", "y", "total"])
    )
    assert result.status == "SUCCESS"
    assert result.result["identity_confirmed"] is confirmed
    assert result.result["matched_rows"] == count
    assert result.sample_size == 3
    assert result.p_value is result.effect_size is None


@pytest.mark.parametrize(
    "method,variables,parameters",
    [
        ("correlation_without_outliers", ["x", "y"], {}),
        ("analyze_subgroups", ["x", "y"], {"group_by": "district"}),
        ("additive_identity", ["x", "y", "total"], {}),
    ],
)
async def test_invalid_numeric_data_does_not_create_diagnostic_statistics(
    method, variables, parameters
):
    result = await setup(
        {
            "x": [1.0, float("inf"), 3.0],
            "y": [2.0, 3.0, 4.0],
            "total": [3.0, 4.0, 5.0],
            "district": ["a", "a", "b"],
        }
    ).execute(request(method, variables, parameters))
    assert result.status == "FAILED"
    assert result.result is result.effect_size is result.p_value is None
