"""Chart data for the web client: Python computes, the frontend only draws.

Each tool returns a typed chart specification in AnalysisResult.result. Specs hold
aggregated or sampled values, never the full dataset.
"""

from typing import Literal

import numpy as np
from pydantic import Field

from app.analytics.association.matrix import correlation_matrix
from app.analytics.base import DatasetTool, ToolOutput, finite
from app.analytics.columns import column_array, numeric_array, require_role
from app.analytics.profiling.measures import histogram
from app.application.dto.datasource import RegisteredDataset
from app.application.errors import AnalysisNotApplicableError
from app.domain.enums.semantic_type import SemanticType
from app.domain.models.analysis import ToolRequest
from app.domain.models.base import DomainModel

NUMERIC = SemanticType.NUMERIC


class HeatmapChart(DomainModel):
    kind: Literal["heatmap"] = "heatmap"
    method: str
    columns: list[str]
    values: list[list[float | None]]
    p_values: list[list[float | None]]
    sample_sizes: list[list[int]]


class TrendLine(DomainModel):
    slope: float
    intercept: float


class ScatterChart(DomainModel):
    kind: Literal["scatter"] = "scatter"
    x: str
    y: str
    points: list[tuple[float, float]]
    total_points: int = Field(ge=0)
    sampled: bool
    trend: TrendLine | None = None


class HistogramChart(DomainModel):
    kind: Literal["histogram"] = "histogram"
    column: str
    edges: list[float]
    counts: list[int]


class BoxStats(DomainModel):
    label: str
    count: int = Field(ge=0)
    lower_whisker: float
    q1: float
    median: float
    q3: float
    upper_whisker: float
    outliers: list[float] = Field(default_factory=list)
    outlier_count: int = Field(ge=0)


class BoxPlotChart(DomainModel):
    kind: Literal["boxplot"] = "boxplot"
    column: str
    group_by: str | None = None
    boxes: list[BoxStats]


def _chart_output(chart: DomainModel, variables: list[str], size: int, notes: list[str]):
    return ToolOutput(
        result=chart.model_dump(mode="json"),
        variables=variables,
        sample_size=size,
        warnings=notes,
        metadata={"chart": chart.kind},
    )


class CorrelationHeatmapTool(DatasetTool):
    name = "chart_correlation_heatmap"

    def supports(self, request: ToolRequest) -> bool:
        return super().supports(request) and len(request.variables) != 1

    def compute(self, data: RegisteredDataset, request: ToolRequest) -> ToolOutput:
        columns = list(request.variables) or data.columns_of_type(NUMERIC)
        for name in columns:
            require_role(data, name, NUMERIC)
        if len(columns) < 2:
            raise AnalysisNotApplicableError("A heatmap needs 2+ numeric columns.")
        matrix = correlation_matrix(data, columns, str(request.parameters.get("method", "pearson")))
        chart = HeatmapChart.model_validate(matrix)
        return _chart_output(chart, columns, data.dataset.row_count, [])


class ScatterTool(DatasetTool):
    name = "chart_scatter"
    min_variables = 2
    max_variables = 2

    def compute(self, data: RegisteredDataset, request: ToolRequest) -> ToolOutput:
        x, y = request.variables
        require_role(data, x, NUMERIC)
        require_role(data, y, NUMERIC)
        xs, ys = column_array(data, x), column_array(data, y)
        mask = ~np.isnan(xs) & ~np.isnan(ys)
        xs, ys = xs[mask], ys[mask]
        total = len(xs)
        if total < 2:
            raise AnalysisNotApplicableError("A scatter plot needs 2+ complete pairs.")
        trend = None
        if np.ptp(xs) > 0:
            slope, intercept = np.polyfit(xs, ys, 1)
            if np.isfinite(slope) and np.isfinite(intercept):
                trend = TrendLine(slope=float(slope), intercept=float(intercept))
        limit = self.options.max_scatter_points
        sampled = total > limit
        if sampled:
            rng = np.random.default_rng(self.options.random_seed)
            keep = np.sort(rng.choice(total, size=limit, replace=False))
            xs, ys = xs[keep], ys[keep]
        notes = [f"Showing a random sample of {limit} of {total} points."] if sampled else []
        chart = ScatterChart(
            x=x,
            y=y,
            points=[(float(a), float(b)) for a, b in zip(xs, ys, strict=True)],
            total_points=total,
            sampled=sampled,
            trend=trend,
        )
        return _chart_output(chart, [x, y], total, notes)


class HistogramTool(DatasetTool):
    name = "chart_histogram"
    min_variables = 1
    max_variables = 1

    def compute(self, data: RegisteredDataset, request: ToolRequest) -> ToolOutput:
        (column,) = request.variables
        require_role(data, column, NUMERIC)
        values = numeric_array(data.values(column))
        observed = int((~np.isnan(values)).sum())
        if not observed:
            raise AnalysisNotApplicableError(f"{column}: no observed values.")
        bins = histogram(values, self.options.max_histogram_bins)
        chart = HistogramChart(column=column, edges=bins["edges"], counts=bins["counts"])
        return _chart_output(chart, [column], observed, [])


class BoxPlotTool(DatasetTool):
    """Box plot of a numeric column, optionally grouped by a categorical column."""

    name = "chart_boxplot"
    min_variables = 1
    max_variables = 2

    def compute(self, data: RegisteredDataset, request: ToolRequest) -> ToolOutput:
        column, *rest = request.variables
        require_role(data, column, NUMERIC)
        values = numeric_array(data.values(column))
        group_by = rest[0] if rest else None
        notes: list[str] = []
        if group_by is None:
            groups = {"all": values[~np.isnan(values)]}
        else:
            require_role(data, group_by, SemanticType.CATEGORICAL)
            groups, notes = self._groups(values, column_array(data, group_by))
        boxes = [self._box(label, group) for label, group in groups.items() if len(group)]
        if not boxes:
            raise AnalysisNotApplicableError(f"{column}: no observed values.")
        chart = BoxPlotChart(column=column, group_by=group_by, boxes=boxes)
        return _chart_output(chart, list(request.variables), sum(box.count for box in boxes), notes)

    def _groups(
        self, values: np.ndarray, labels: np.ndarray
    ) -> tuple[dict[str, np.ndarray], list[str]]:
        grouped: dict[str, list[float]] = {}
        for value, label in zip(values, labels, strict=True):
            if label is not None and not np.isnan(value):
                grouped.setdefault(str(label), []).append(float(value))
        ordered = sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0]))
        limit = self.options.max_categories
        notes = []
        if len(ordered) > limit:
            notes.append(f"Showing the {limit} largest of {len(ordered)} groups.")
        return {label: np.asarray(items) for label, items in ordered[:limit]}, notes

    def _box(self, label: str, values: np.ndarray) -> BoxStats:
        q1, median, q3 = np.percentile(values, [25, 50, 75])
        iqr = q3 - q1
        multiplier = self.options.outlier_iqr_multiplier
        lower, upper = q1 - multiplier * iqr, q3 + multiplier * iqr
        inside = values[(values >= lower) & (values <= upper)]
        outside = values[(values < lower) | (values > upper)]
        extremes = outside[np.argsort(-np.abs(outside - median), kind="stable")]
        return BoxStats(
            label=label,
            count=len(values),
            lower_whisker=float(inside.min()),
            q1=float(q1),
            median=float(median),
            q3=float(q3),
            upper_whisker=float(inside.max()),
            outliers=[finite(v) for v in extremes[: self.options.max_box_outliers]],
            outlier_count=len(outside),
        )
