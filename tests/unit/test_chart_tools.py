import pytest
from eda_support import planted_dataset, store_with

from app.bootstrap import build_tool_registry
from app.modules.exploration.adapters.visualization.charts import (
    BoxPlotChart,
    HeatmapChart,
    HistogramChart,
    ScatterChart,
)
from app.shared.application.tool_registry import ToolRegistry
from app.shared.config.settings import Settings
from app.shared.domain.models.analysis import AnalysisResult, ToolRequest


@pytest.fixture
async def registry() -> ToolRegistry:
    settings = Settings(_env_file=None, eda={"max_scatter_points": 50})
    return build_tool_registry(settings, await store_with(planted_dataset()))


async def run(registry: ToolRegistry, method: str, *variables: str) -> AnalysisResult:
    request = ToolRequest(dataset_id="ds", method=method, variables=list(variables))
    return await registry.get(method).execute(request)


async def test_heatmap_chart(registry: ToolRegistry) -> None:
    result = await run(registry, "chart_correlation_heatmap", "devengado", "girado", "ruido")
    chart = HeatmapChart.model_validate(result.result)
    assert chart.columns == ["devengado", "girado", "ruido"]
    assert chart.values[0][1] > 0.9
    assert result.metadata == {"chart": "heatmap"}


async def test_scatter_chart_is_sampled_deterministically(registry: ToolRegistry) -> None:
    first = await run(registry, "chart_scatter", "devengado", "girado")
    second = await run(registry, "chart_scatter", "devengado", "girado")
    chart = ScatterChart.model_validate(first.result)
    assert len(chart.points) == 50 and chart.total_points == 299 and chart.sampled
    assert chart.trend is not None and 0.8 < chart.trend.slope < 1.0
    assert first.result == second.result
    assert "sample of 50" in first.warnings[0]


async def test_histogram_chart(registry: ToolRegistry) -> None:
    chart = HistogramChart.model_validate((await run(registry, "chart_histogram", "monto")).result)
    assert len(chart.edges) == len(chart.counts) + 1
    assert sum(chart.counts) == 300


async def test_boxplot_chart_grouped_and_ungrouped(registry: ToolRegistry) -> None:
    grouped = BoxPlotChart.model_validate(
        (await run(registry, "chart_boxplot", "monto", "region")).result
    )
    assert grouped.group_by == "region"
    assert {box.label for box in grouped.boxes} == {"norte", "sur", "este"}
    for box in grouped.boxes:
        assert box.lower_whisker <= box.q1 <= box.median <= box.q3 <= box.upper_whisker
    medians = {box.label: box.median for box in grouped.boxes}
    assert medians["norte"] < medians["sur"] < medians["este"]
    single = BoxPlotChart.model_validate((await run(registry, "chart_boxplot", "monto")).result)
    assert [box.label for box in single.boxes] == ["all"] and single.boxes[0].count == 300


async def test_chart_rejects_wrong_types(registry: ToolRegistry) -> None:
    assert (await run(registry, "chart_histogram", "region")).status == "SKIPPED"
    assert (await run(registry, "chart_boxplot", "monto", "girado")).status == "SKIPPED"
