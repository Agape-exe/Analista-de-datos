from dataclasses import dataclass

import pytest

from app.modules.analysis.adapters.analytics.factory import build_statistical_tool_registry
from app.shared.application.dataset_registry import DatasetRegistry
from app.shared.application.errors import DatasetRegistryError, ToolRegistryError
from app.shared.contracts.datasource import LoadedDataset
from app.shared.domain.enums.statuses import AnalysisStatus
from app.shared.domain.models.analysis import ToolRequest
from app.shared.domain.models.dataset import DatasetSchema


@dataclass(frozen=True)
class MemoryTable:
    columns: dict[str, list[object]]

    def column(self, name: str) -> list[object]:
        return self.columns[name]


def registry() -> DatasetRegistry:
    datasets = DatasetRegistry()
    columns = {
        "x": list(range(1, 21)),
        "y": [value * 2 for value in range(1, 21)],
        "control": [value // 2 for value in range(1, 21)],
        "category_a": ["a"] * 10 + ["b"] * 10,
        "category_b": ["yes"] * 10 + ["no"] * 10,
        "outcome": [1, 2] * 5 + [8, 9] * 5,
    }
    datasets.register(
        LoadedDataset(
            dataset_id="statistics",
            schema=DatasetSchema(
                columns=[{"name": name, "data_type": "unknown"} for name in columns]
            ),
            row_count=20,
            table=MemoryTable(columns),
        )
    )
    return datasets


async def test_statistical_registry_executes_six_supported_methods() -> None:
    datasets = registry()
    tools = build_statistical_tool_registry(datasets)
    requests = [
        ToolRequest(dataset_id="statistics", method="pearson", variables=["x", "y"]),
        ToolRequest(dataset_id="statistics", method="spearman", variables=["x", "y"]),
        ToolRequest(
            dataset_id="statistics",
            method="partial_correlation",
            variables=["x", "y"],
            parameters={"control_variable": "control"},
        ),
        ToolRequest(
            dataset_id="statistics", method="chi_square", variables=["category_a", "category_b"]
        ),
        ToolRequest(
            dataset_id="statistics", method="cramers_v", variables=["category_a", "category_b"]
        ),
        ToolRequest(
            dataset_id="statistics", method="anova_one_way", variables=["category_a", "outcome"]
        ),
    ]

    results = [await tools.execute(request) for request in requests]

    assert tools.names() == (
        "additive_identity",
        "analyze_subgroups",
        "anova_one_way",
        "chi_square",
        "correlation_without_outliers",
        "cramers_v",
        "partial_correlation",
        "pearson",
        "spearman",
    )
    assert all(result.status == AnalysisStatus.SUCCESS for result in results)
    assert all(result.sample_size == 20 for result in results)
    assert results[0].effect_size == pytest.approx(1.0)
    assert results[4].effect_size == pytest.approx(1.0)
    assert results[5].effect_size is not None and results[5].effect_size > 0


async def test_statistical_tools_fail_without_fabricated_statistics() -> None:
    datasets = registry()
    tools = build_statistical_tool_registry(datasets)
    result = await tools.execute(
        ToolRequest(dataset_id="statistics", method="pearson", variables=["x", "missing"])
    )

    assert result.status == AnalysisStatus.FAILED
    assert result.result is result.p_value is result.effect_size is None
    with pytest.raises(ToolRegistryError, match="Unknown"):
        tools.resolve(ToolRequest(dataset_id="statistics", method="unknown"))


def test_dataset_registry_is_isolated_and_releases_references() -> None:
    first = registry()
    second = DatasetRegistry()

    assert first.ids() == ("statistics",)
    with pytest.raises(DatasetRegistryError, match="Unknown"):
        second.get("statistics")
    first.clear()
    assert first.ids() == ()
