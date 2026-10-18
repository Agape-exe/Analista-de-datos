import numpy as np

from app.modules.exploration.adapters.analytics.base import DatasetTool, ToolOutput, finite
from app.modules.exploration.adapters.analytics.columns import (
    label_array,
    numeric_array,
    require_role,
)
from app.modules.exploration.adapters.analytics.profiling import measures
from app.shared.application.errors import AnalysisNotApplicableError, ToolInputError
from app.shared.contracts.datasource import RegisteredDataset
from app.shared.domain.enums.semantic_type import SemanticType
from app.shared.domain.models.analysis import ToolRequest

NUMERIC = SemanticType.NUMERIC
CATEGORICAL = SemanticType.CATEGORICAL


class ColumnsTool(DatasetTool):
    """Per-column profile; defaults to every column of the supported semantic types."""

    roles: tuple[SemanticType, ...] = ()

    def compute(self, data: RegisteredDataset, request: ToolRequest) -> ToolOutput:
        requested = list(request.variables)
        candidates = requested or [column.column_name for column in data.profile.columns]
        columns, notes = [], []
        for name in candidates:
            role = data.semantic_type(name)
            if not self.roles or role in self.roles:
                columns.append(name)
            elif requested:
                notes.append(f"{name}: {self.name} does not apply to {role} columns.")
        if not columns:
            raise AnalysisNotApplicableError(f"No columns suitable for {self.name}.")
        result = {name: self.profile(data, name, data.semantic_type(name)) for name in columns}
        return ToolOutput(
            result=result,
            variables=columns,
            sample_size=data.dataset.row_count,
            warnings=notes,
        )

    def profile(self, data: RegisteredDataset, name: str, role: SemanticType) -> dict:
        raise NotImplementedError

    def labels(self, data: RegisteredDataset, name: str) -> list[str]:
        return [str(value) for value in data.values(name) if value is not None]


class DescriptiveStatisticsTool(ColumnsTool):
    name = "descriptive_statistics"
    roles = (NUMERIC, CATEGORICAL)

    def profile(self, data: RegisteredDataset, name: str, role: SemanticType) -> dict:
        if role == NUMERIC:
            return {
                "semantic_type": role,
                **measures.numeric_summary(numeric_array(data.values(name))),
            }
        summary = measures.frequencies(self.labels(data, name), self.options.top_categories)
        return {
            "semantic_type": role,
            "missing": data.dataset.row_count - summary["count"],
            **summary,
        }


class MissingValuesTool(DatasetTool):
    name = "missing_values"

    def compute(self, data: RegisteredDataset, request: ToolRequest) -> ToolOutput:
        columns = list(request.variables) or [c.column_name for c in data.profile.columns]
        rows = data.dataset.row_count
        masks = {name: [value is None for value in data.values(name)] for name in columns}
        incomplete = sum(any(row) for row in zip(*masks.values(), strict=True)) if masks else 0
        per_column = {
            name: {
                "missing": sum(mask),
                "percentage": finite(100 * sum(mask) / rows if rows else 0),
            }
            for name, mask in masks.items()
        }
        missing = sum(item["missing"] for item in per_column.values())
        cells = rows * len(columns)
        return ToolOutput(
            result={
                "columns": per_column,
                "missing_cells": missing,
                "missing_percentage": finite(100 * missing / cells if cells else 0),
                "complete_rows": rows - incomplete,
                "complete_rows_percentage": finite(100 * (rows - incomplete) / rows if rows else 0),
            },
            variables=columns,
            sample_size=rows,
        )


class DistributionTool(ColumnsTool):
    name = "distribution"
    roles = (NUMERIC, CATEGORICAL)

    def profile(self, data: RegisteredDataset, name: str, role: SemanticType) -> dict:
        if role == CATEGORICAL:
            summary = measures.frequencies(self.labels(data, name), self.options.top_categories)
            return {"semantic_type": role, "frequencies": summary}
        values = numeric_array(data.values(name))
        summary = measures.numeric_summary(values)
        return {
            "semantic_type": role,
            "histogram": measures.histogram(values, self.options.max_histogram_bins),
            "skewness": summary.get("skewness"),
            "kurtosis": summary.get("kurtosis"),
            "shape": measures.shape(summary.get("skewness")),
            "normality": measures.normality(values, self.options.normality_alpha),
        }


class CardinalityTool(ColumnsTool):
    name = "cardinality"

    def profile(self, data: RegisteredDataset, name: str, role: SemanticType) -> dict:
        observed = [value for value in data.values(name) if value is not None]
        unique = len(set(observed))
        ratio = unique / len(observed) if observed else 0
        flags = []
        if unique <= 1:
            flags.append("constant")
        elif unique == 2:
            flags.append("binary")
        if role == CATEGORICAL and unique > self.options.max_categories:
            flags.append("high_cardinality")
        if ratio >= 0.95 and len(observed) > 1 and role != SemanticType.IDENTIFIER:
            flags.append("near_unique")
        return {
            "semantic_type": role,
            "unique": unique,
            "unique_ratio": finite(ratio),
            "flags": flags,
        }


class OutliersTool(ColumnsTool):
    name = "outliers"
    roles = (NUMERIC,)

    def profile(self, data: RegisteredDataset, name: str, role: SemanticType) -> dict:
        values = numeric_array(data.values(name))
        if int((~np.isnan(values)).sum()) < self.minimum_sample_size:
            return {"semantic_type": role, "skipped": "insufficient observations"}
        return {
            "semantic_type": role,
            **measures.outliers(
                values,
                self.options.outlier_iqr_multiplier,
                self.options.outlier_mad_threshold,
                self.options.max_outlier_examples,
            ),
        }


class GroupedSummaryTool(DatasetTool):
    """Count, missing values, centre and spread of a numeric column per existing category."""

    name = "grouped_summary"
    min_variables = 2
    max_variables = 2

    def compute(self, data: RegisteredDataset, request: ToolRequest) -> ToolOutput:
        column, group_by = request.variables
        require_role(data, column, NUMERIC)
        require_role(data, group_by, CATEGORICAL)
        limit = self._max_groups(request)
        values = numeric_array(data.values(column))
        if not int((~np.isnan(values)).sum()):
            raise AnalysisNotApplicableError(f"{column}: no observed values.")
        result = measures.grouped_summary(
            values, label_array(data.values(group_by)), limit, self.minimum_sample_size
        )
        notes = []
        omitted = result["omitted"]
        if isinstance(omitted, dict) and omitted["groups"]:
            notes.append(
                f"Showing the {result['shown_groups']} largest of {result['total_groups']} groups; "
                f"{omitted['groups']} group(s) with {omitted['rows']} row(s) were omitted."
            )
        return ToolOutput(
            result={"column": column, "group_by": group_by, **result},
            variables=[column, group_by],
            sample_size=data.dataset.row_count,
            warnings=notes,
        )

    def _max_groups(self, request: ToolRequest) -> int:
        cap = self.options.max_summary_groups
        raw = request.parameters.get("max_groups", cap)
        if isinstance(raw, bool) or not isinstance(raw, int) or not 1 <= raw <= cap:
            raise ToolInputError(f"max_groups must be an integer between 1 and {cap}.")
        return raw
