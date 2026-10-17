from dataclasses import dataclass

import pytest

from app.analytics.registry import ToolRegistry
from app.analytics.statistics.mixed import (
    ChiSquareIndependenceTool,
    CramersVTool,
    OneWayAnovaTool,
)
from app.application.dto.datasource import LoadedDataset
from app.application.services.dataset_registry import DatasetRegistry
from app.domain.models.analysis import ToolRequest
from app.domain.models.dataset import DatasetSchema


@dataclass(frozen=True)
class MemoryTable:
    columns: dict[str, list[object]]

    def column(self, name: str) -> list[object]:
        return self.columns[name]


def tools(
    columns: dict[str, list[object]], dataset_id: str = "sample"
) -> tuple[DatasetRegistry, ChiSquareIndependenceTool, CramersVTool, OneWayAnovaTool]:
    datasets = DatasetRegistry()
    datasets.register(
        LoadedDataset(
            dataset_id=dataset_id,
            schema=DatasetSchema(
                columns=[{"name": name, "data_type": "unknown"} for name in columns]
            ),
            row_count=len(next(iter(columns.values()))),
            table=MemoryTable(columns),
        )
    )
    return (
        datasets,
        ChiSquareIndependenceTool(datasets),
        CramersVTool(datasets),
        OneWayAnovaTool(datasets),
    )


async def test_chi_square_detects_categorical_association() -> None:
    _, chi_square, _, _ = tools(
        {"source": ["A"] * 10 + ["B"] * 10, "outcome": ["yes"] * 10 + ["no"] * 10}
    )

    result = await chi_square.execute(
        ToolRequest(dataset_id="sample", method="chi_square", variables=["source", "outcome"])
    )

    assert result.status == "SUCCESS"
    assert result.result == {"chi_square": pytest.approx(20.0)}
    assert result.p_value is not None and result.p_value < 0.001
    assert result.sample_size == 20
    assert result.metadata["degrees_of_freedom"] == 1
    assert result.metadata["continuity_correction"] is False


async def test_chi_square_accepts_independent_categories() -> None:
    _, chi_square, _, _ = tools(
        {
            "source": ["A"] * 10 + ["B"] * 10,
            "outcome": ["yes"] * 5 + ["no"] * 5 + ["yes"] * 5 + ["no"] * 5,
        }
    )

    result = await chi_square.execute(
        ToolRequest(dataset_id="sample", method="chi_square", variables=["source", "outcome"])
    )

    assert result.status == "SUCCESS"
    assert result.result == {"chi_square": pytest.approx(0.0)}
    assert result.p_value == pytest.approx(1.0)


async def test_cramers_v_returns_bounded_effect_size() -> None:
    _, _, cramers_v, _ = tools(
        {"source": ["A"] * 10 + ["B"] * 10, "outcome": ["yes"] * 10 + ["no"] * 10}
    )

    result = await cramers_v.execute(
        ToolRequest(dataset_id="sample", method="cramers_v", variables=["source", "outcome"])
    )

    assert result.status == "SUCCESS"
    assert result.result == {"cramers_v": pytest.approx(1.0)}
    assert result.effect_size is not None and 0 <= result.effect_size <= 1
    assert result.metadata["variant"] == "standard"


async def test_anova_detects_group_mean_differences() -> None:
    _, _, _, anova = tools({"group": ["A"] * 4 + ["B"] * 4, "score": [1, 2, 1, 2, 5, 6, 5, 6]})

    result = await anova.execute(
        ToolRequest(dataset_id="sample", method="anova_one_way", variables=["group", "score"])
    )

    assert result.status == "SUCCESS"
    assert result.result == {"f_statistic": pytest.approx(96.0)}
    assert result.p_value is not None and result.p_value < 0.001
    assert result.effect_size == pytest.approx(32 / 34)
    assert result.metadata["degrees_of_freedom_between"] == 1
    assert result.metadata["degrees_of_freedom_within"] == 6


async def test_anova_accepts_similar_group_means() -> None:
    _, _, _, anova = tools({"group": ["A"] * 4 + ["B"] * 4, "score": [1, 2, 1, 2, 1, 2, 2, 1]})

    result = await anova.execute(
        ToolRequest(dataset_id="sample", method="anova_one_way", variables=["group", "score"])
    )

    assert result.status == "SUCCESS"
    assert result.result == {"f_statistic": pytest.approx(0.0)}
    assert result.p_value == pytest.approx(1.0)


async def test_mixed_tools_exclude_missing_observations() -> None:
    _, chi_square, _, anova = tools(
        {
            "category": ["A", "A", "B", "B", None],
            "label": ["yes", "yes", "no", "no", "yes"],
            "score": [1, 2, 5, 6, 100],
        }
    )

    chi_result = await chi_square.execute(
        ToolRequest(dataset_id="sample", method="chi_square", variables=["category", "label"])
    )
    anova_result = await anova.execute(
        ToolRequest(dataset_id="sample", method="anova_one_way", variables=["category", "score"])
    )

    assert chi_result.sample_size == 4
    assert anova_result.sample_size == 4


@pytest.mark.parametrize(
    ("method", "variables", "columns", "message"),
    [
        ("chi_square", ["category", "missing"], {"category": ["A", "B"]}, "missing"),
        (
            "chi_square",
            ["category", "label"],
            {"category": ["A", "A", "A"], "label": ["yes", "no", "yes"]},
            "at least two categories",
        ),
        (
            "anova_one_way",
            ["group", "score"],
            {"group": ["A", "B", "B"], "score": [1, 2, 3]},
            "at least two observations",
        ),
        (
            "anova_one_way",
            ["group", "score"],
            {"group": ["A", "A", "B", "B"], "score": [1, "two", 3, 4]},
            "numeric",
        ),
        (
            "anova_one_way",
            ["group", "score"],
            {"group": ["A", "A", "B", "B"], "score": [1, 1, 1, 1]},
            "total variance",
        ),
    ],
)
async def test_mixed_tools_reject_invalid_data(
    method: str, variables: list[str], columns: dict[str, list[object]], message: str
) -> None:
    _, chi_square, _, anova = tools(columns)
    tool = chi_square if method == "chi_square" else anova

    result = await tool.execute(
        ToolRequest(dataset_id="sample", method=method, variables=variables)
    )

    assert result.status == "FAILED"
    assert message in result.warnings[0]
    assert result.result is None
    assert result.p_value is None
    assert result.effect_size is None


async def test_chi_square_warns_for_small_expected_frequencies() -> None:
    _, chi_square, _, _ = tools(
        {"source": ["A", "A", "B", "B", "B"], "outcome": ["yes", "no", "yes", "no", "no"]}
    )

    result = await chi_square.execute(
        ToolRequest(dataset_id="sample", method="chi_square", variables=["source", "outcome"])
    )

    assert result.status == "SUCCESS"
    assert result.metadata["low_expected_cells"] > 0
    assert any("below 5" in warning for warning in result.warnings)


async def test_mixed_tools_execute_through_registry() -> None:
    datasets, chi_square, cramers_v, anova = tools(
        {"group": ["A", "A", "B", "B"], "label": ["yes", "no", "yes", "no"], "score": [1, 2, 5, 6]}
    )
    datasets.register(
        LoadedDataset(
            dataset_id="other",
            schema=DatasetSchema(
                columns=[
                    {"name": "group", "data_type": "string"},
                    {"name": "label", "data_type": "string"},
                    {"name": "score", "data_type": "number"},
                ]
            ),
            row_count=8,
            table=MemoryTable(
                {
                    "group": ["A"] * 4 + ["B"] * 4,
                    "label": ["yes"] * 4 + ["no"] * 4,
                    "score": [1, 2, 1, 2, 5, 6, 5, 6],
                }
            ),
        )
    )
    registry = ToolRegistry()
    for tool in (chi_square, cramers_v, anova):
        registry.register(tool)

    chi_result = await registry.execute(
        ToolRequest(dataset_id="other", method="chi_square", variables=["group", "label"])
    )
    v_result = await registry.execute(
        ToolRequest(dataset_id="other", method="cramers_v", variables=["group", "label"])
    )
    anova_result = await registry.execute(
        ToolRequest(dataset_id="other", method="anova_one_way", variables=["group", "score"])
    )

    assert chi_result.sample_size == 8
    assert v_result.effect_size == pytest.approx(1.0)
    assert anova_result.sample_size == 8


def test_mixed_tools_reject_incompatible_requests() -> None:
    _, chi_square, cramers_v, anova = tools(
        {"group": ["A", "A", "B", "B"], "label": ["yes", "no", "yes", "no"], "score": [1, 2, 5, 6]}
    )

    invalid = ToolRequest(
        dataset_id="sample", method="chi_square", variables=["group", "label"], parameters={"x": 1}
    )

    assert not chi_square.supports(invalid)
    assert not cramers_v.supports(invalid.model_copy(update={"method": "cramers_v"}))
    assert not anova.supports(invalid.model_copy(update={"method": "anova_one_way"}))
