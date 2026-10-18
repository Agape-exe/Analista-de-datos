import numpy as np
import pytest
from eda_support import make_dataset, planted_dataset, store_with

from app.bootstrap import build_tool_registry
from app.modules.exploration.adapters.analytics.association import measures
from app.modules.exploration.adapters.visualization.charts import ContingencyChart
from app.shared.application.tool_registry import ToolRegistry
from app.shared.config.settings import Settings
from app.shared.domain.enums.semantic_type import SemanticType
from app.shared.domain.models.analysis import AnalysisResult, ToolRequest

CATEGORICAL = SemanticType.CATEGORICAL


async def run(registry: ToolRegistry, *variables: str) -> AnalysisResult:
    request = ToolRequest(dataset_id="ds", method="chart_contingency", variables=list(variables))
    return await registry.get("chart_contingency").execute(request)


async def registry_for(dataset=None, **eda: object) -> ToolRegistry:
    settings = Settings(_env_file=None, eda=eda)
    return build_tool_registry(settings, await store_with(dataset or planted_dataset()))


async def test_counts_totals_and_expected_frequencies_match_the_existing_chi_square() -> None:
    result = await run(await registry_for(), "region", "canal")
    assert result.status == "SUCCESS" and result.warnings == []
    chart = ContingencyChart.model_validate(result.result)
    counts = np.asarray(chart.counts)
    assert chart.total == counts.sum() == 300 and chart.excluded_rows == 0
    assert chart.row_totals == counts.sum(axis=1).tolist()
    assert chart.column_totals == counts.sum(axis=0).tolist()
    assert chart.row_totals == sorted(chart.row_totals, reverse=True)
    expected = np.asarray(chart.expected, dtype=float)
    assert np.allclose(expected.sum(axis=1), chart.row_totals, atol=1e-3)
    table, _, _ = measures.contingency_table(
        np.asarray(planted_dataset().values("region"), dtype=object),
        np.asarray(planted_dataset().values("canal"), dtype=object),
    )
    _, _, _, reference = measures._chi_square(table)
    assert chart.min_expected == round(float(reference.min()), 4)
    assert chart.cells == 9 and chart.expected_below_5 == 0 and chart.empty_cells == 0


async def test_folds_the_smallest_categories_for_display_only() -> None:
    result = await run(await registry_for(top_categories=2), "region", "canal")
    chart = ContingencyChart.model_validate(result.result)
    assert len(chart.row_labels) == len(chart.column_labels) == 2
    assert chart.folded_rows == chart.folded_columns == 2
    assert np.asarray(chart.counts).sum() == chart.total == 300
    assert chart.cells == 9


async def test_warns_about_small_expected_frequencies_and_counts_excluded_rows() -> None:
    x = ["a"] * 18 + ["b"] * 2 + [None]
    y = ["u"] * 9 + ["v"] * 9 + ["u", "v", "u"]
    dataset = make_dataset({"x": x, "y": y}, {"x": CATEGORICAL, "y": CATEGORICAL})
    result = await run(await registry_for(dataset), "x", "y")
    chart = ContingencyChart.model_validate(result.result)
    assert chart.excluded_rows == 1 and chart.total == 20
    assert chart.expected_below_5 == 2 and chart.expected_below_1 == 0
    assert "expected frequencies are below 5" in result.warnings[0]


@pytest.mark.parametrize(
    ("variables", "settings"),
    [
        (("region", "monto"), {}),
        (("region", "region"), {}),
        (("color", "codigo_id"), {}),
        (("region", "canal"), {"max_categories": 2}),
    ],
)
async def test_is_not_applicable_outside_two_bounded_categorical_columns(
    variables: tuple[str, str], settings: dict[str, object]
) -> None:
    assert (await run(await registry_for(**settings), *variables)).status == "SKIPPED"
