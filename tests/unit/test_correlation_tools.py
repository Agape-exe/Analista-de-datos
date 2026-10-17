from dataclasses import dataclass

import pytest

from app.modules.analysis.adapters.analytics.correlation import (
    PartialCorrelationTool,
    PearsonCorrelationTool,
    SpearmanCorrelationTool,
)
from app.shared.application.dataset_registry import DatasetRegistry
from app.shared.application.tool_registry import ToolRegistry
from app.shared.contracts.datasource import LoadedDataset
from app.shared.domain.models.analysis import ToolRequest
from app.shared.domain.models.dataset import DatasetSchema


@dataclass(frozen=True)
class MemoryTable:
    columns: dict[str, list[object]]

    def column(self, name: str) -> list[object]:
        return self.columns[name]


def tools(
    columns: dict[str, list[object]], dataset_id: str = "sample"
) -> tuple[
    DatasetRegistry, PearsonCorrelationTool, SpearmanCorrelationTool, PartialCorrelationTool
]:
    datasets = DatasetRegistry()
    datasets.register(
        LoadedDataset(
            dataset_id=dataset_id,
            schema=DatasetSchema(
                columns=[{"name": name, "data_type": "number"} for name in columns]
            ),
            row_count=len(next(iter(columns.values()))),
            table=MemoryTable(columns),
        )
    )
    return (
        datasets,
        PearsonCorrelationTool(datasets),
        SpearmanCorrelationTool(datasets),
        PartialCorrelationTool(datasets),
    )


async def test_pearson_detects_positive_relationship() -> None:
    _, pearson, _, _ = tools({"x": [1, 2, 3, 4, 5], "y": [2, 4, 6, 8, 10]})

    result = await pearson.execute(
        ToolRequest(dataset_id="sample", method="pearson", variables=["x", "y"])
    )

    assert result.status == "SUCCESS"
    assert result.result == {"correlation": pytest.approx(1.0)}
    assert result.sample_size == 5
    assert result.p_value == pytest.approx(0.0)


async def test_pearson_detects_negative_relationship() -> None:
    _, pearson, _, _ = tools({"x": [1, 2, 3, 4, 5], "y": [10, 8, 6, 4, 2]})

    result = await pearson.execute(
        ToolRequest(dataset_id="sample", method="pearson", variables=["x", "y"])
    )

    assert result.status == "SUCCESS"
    assert result.effect_size == pytest.approx(-1.0)


async def test_spearman_detects_monotonic_relationship() -> None:
    _, pearson, spearman, _ = tools({"x": [1, 2, 3, 4, 5], "y": [1, 4, 9, 16, 25]})
    request = ToolRequest(dataset_id="sample", method="spearman", variables=["x", "y"])

    spearman_result = await spearman.execute(request)
    pearson_result = await pearson.execute(
        ToolRequest(dataset_id="sample", method="pearson", variables=["x", "y"])
    )

    assert spearman_result.status == "SUCCESS"
    assert spearman_result.effect_size == pytest.approx(1.0)
    assert abs(pearson_result.effect_size or 0) < abs(spearman_result.effect_size or 0)


async def test_partial_correlation_reduces_confounded_association() -> None:
    controls = list(range(1, 13))
    first = [control + noise for control, noise in zip(controls, [-1, 1, 0] * 4, strict=True)]
    second = [3 * control + noise for control, noise in zip(controls, [1, 0, -1] * 4, strict=True)]
    _, pearson, _, partial = tools({"x": first, "y": second, "z": controls})

    marginal = await pearson.execute(
        ToolRequest(dataset_id="sample", method="pearson", variables=["x", "y"])
    )
    result = await partial.execute(
        ToolRequest(
            dataset_id="sample",
            method="partial_correlation",
            variables=["x", "y"],
            parameters={"control_variable": "z"},
        )
    )

    assert result.status == "SUCCESS"
    assert abs(result.effect_size or 0) < abs(marginal.effect_size or 0)
    assert result.metadata == {"control_variable": "z", "degrees_of_freedom": 9}


async def test_correlation_rejects_invalid_columns() -> None:
    _, pearson, _, _ = tools({"x": [1, 2, 3], "y": [3, 2, 1]})

    result = await pearson.execute(
        ToolRequest(dataset_id="sample", method="pearson", variables=["x", "missing"])
    )

    assert result.status == "FAILED"
    assert "missing" in result.warnings[0]


@pytest.mark.parametrize(
    ("columns", "message"),
    [
        ({"x": [1, 2, 3], "y": ["a", "b", "c"]}, "numeric"),
        ({"x": [1, 1, 1], "y": [1, 2, 3]}, "constant"),
        ({"x": [1, 2], "y": [2, 3]}, "at least 3"),
        ({"x": [1, 2, float("inf")], "y": [2, 3, 4]}, "infinite"),
    ],
)
async def test_correlation_rejects_invalid_values(
    columns: dict[str, list[object]], message: str
) -> None:
    _, pearson, _, _ = tools(columns)

    result = await pearson.execute(
        ToolRequest(dataset_id="sample", method="pearson", variables=["x", "y"])
    )

    assert result.status == "FAILED"
    assert message in result.warnings[0]


async def test_correlation_uses_complete_numeric_observations() -> None:
    _, pearson, _, _ = tools({"x": [1, 2, None, 4], "y": [2, 4, 100, 8]})

    result = await pearson.execute(
        ToolRequest(dataset_id="sample", method="pearson", variables=["x", "y"])
    )

    assert result.status == "SUCCESS"
    assert result.sample_size == 3
    assert result.effect_size == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("columns", "message"),
    [
        (
            {"x": [1, 2, 3, 4], "y": [4, 3, 2, 1], "z": [1, 1, 1, 1]},
            "Control variable",
        ),
        ({"x": [1, 2, 3], "y": [3, 2, 1], "z": [1, 2, 3]}, "at least 4"),
    ],
)
async def test_partial_correlation_rejects_invalid_control_data(
    columns: dict[str, list[object]], message: str
) -> None:
    _, _, _, partial = tools(columns)

    result = await partial.execute(
        ToolRequest(
            dataset_id="sample",
            method="partial_correlation",
            variables=["x", "y"],
            parameters={"control_variable": "z"},
        )
    )

    assert result.status == "FAILED"
    assert message in result.warnings[0]


async def test_registry_executes_all_registered_correlation_tools_for_requested_dataset() -> None:
    datasets, pearson, spearman, partial = tools(
        {"x": [1, 2, 3, 4], "y": [2, 3, 5, 7], "z": [4, 3, 2, 1]}
    )
    datasets.register(
        LoadedDataset(
            dataset_id="other",
            schema=DatasetSchema(
                columns=[
                    {"name": "x", "data_type": "number"},
                    {"name": "y", "data_type": "number"},
                    {"name": "z", "data_type": "number"},
                ]
            ),
            row_count=6,
            table=MemoryTable(
                {
                    "x": [2, 1, 4, 3, 6, 5],
                    "y": [2, 5, 5, 10, 10, 15],
                    "z": [1, 2, 3, 4, 5, 6],
                }
            ),
        )
    )
    registry = ToolRegistry()
    for tool in (pearson, spearman, partial):
        registry.register(tool)

    pearson_result = await registry.execute(
        ToolRequest(dataset_id="other", method="pearson", variables=["x", "y"])
    )
    spearman_result = await registry.execute(
        ToolRequest(dataset_id="other", method="spearman", variables=["x", "y"])
    )
    partial_result = await registry.execute(
        ToolRequest(
            dataset_id="other",
            method="partial_correlation",
            variables=["x", "y"],
            parameters={"control_variable": "z"},
        )
    )

    assert pearson_result.status == "SUCCESS"
    assert pearson_result.sample_size == 6
    assert spearman_result.status == "SUCCESS"
    assert partial_result.status == "SUCCESS"
