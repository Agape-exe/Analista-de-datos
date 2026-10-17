"""Measured sensitivity and structural checks on execution-local data."""

from collections import defaultdict
from math import isfinite
from time import perf_counter

import numpy as np
from scipy.stats import pearsonr

from app.analytics.statistics.correlation import (
    CAUSALITY_WARNING,
    CorrelationInputError,
    _CorrelationTool,
    _is_missing,
    _numeric,
    _validate_correlation_sample,
)
from app.application.errors import DatasetRegistryError
from app.domain.models.analysis import AnalysisResult, ToolRequest


class OutlierCorrelationTool(_CorrelationTool):
    name = "correlation_without_outliers"

    def supports(self, request: ToolRequest) -> bool:
        return (
            request.method == self.name
            and len(request.variables) == 2
            and len(set(request.variables)) == 2
            and not request.parameters
        )

    async def execute(self, request: ToolRequest) -> AnalysisResult:
        started = perf_counter()
        if not self.supports(request):
            return self._failed(
                request, "Outlier sensitivity requires two numeric variables", started
            )
        try:
            first, second = self._values(request, request.variables)
            _validate_correlation_sample(first, second, 3)
            arrays = np.asarray([first, second], dtype=float)
            q1, q3 = np.quantile(arrays, [0.25, 0.75], axis=1)
            spread = q3 - q1
            keep = (
                (arrays >= (q1 - 1.5 * spread)[:, None]) & (arrays <= (q3 + 1.5 * spread)[:, None])
            ).all(axis=0)
            retained = arrays[:, keep]
            metadata = {
                "outlier_method": "joint IQR (1.5 x IQR)",
                "removed_count": int((~keep).sum()),
                "original_sample_size": len(first),
            }
            try:
                _validate_correlation_sample(retained[0].tolist(), retained[1].tolist(), 3)
            except CorrelationInputError as error:
                return AnalysisResult(
                    method=self.name,
                    variables=request.variables,
                    status="SKIPPED",
                    warnings=[f"IQR sensitivity is not applicable after filtering: {error}"],
                    metadata=metadata,
                    execution_time=perf_counter() - started,
                )
            calculation = pearsonr(*retained)
            coefficient, p_value = float(calculation.statistic), float(calculation.pvalue)
            if not isfinite(coefficient) or not isfinite(p_value):
                raise CorrelationInputError("Outlier sensitivity produced non-finite results")
            return AnalysisResult(
                method=self.name,
                variables=request.variables,
                status="SUCCESS",
                result={"correlation": coefficient},
                effect_size=coefficient,
                p_value=p_value,
                sample_size=int(keep.sum()),
                metadata=metadata,
                warnings=[
                    CAUSALITY_WARNING,
                    "IQR exclusion is a sensitivity check; valid observations may be excluded. "
                    "The original dataset is unchanged.",
                ],
                execution_time=perf_counter() - started,
            )
        except CorrelationInputError as error:
            return self._failed(request, str(error), started)


class SubgroupCorrelationTool(_CorrelationTool):
    name = "analyze_subgroups"

    def supports(self, request: ToolRequest) -> bool:
        group = request.parameters.get("group_by")
        return (
            request.method == self.name
            and len(request.variables) == 2
            and len(set(request.variables)) == 2
            and set(request.parameters) == {"group_by"}
            and isinstance(group, str)
            and bool(group.strip())
            and group not in request.variables
        )

    async def execute(self, request: ToolRequest) -> AnalysisResult:
        started = perf_counter()
        if not self.supports(request):
            return self._failed(
                request, "Subgroups require two variables and parameters.group_by", started
            )
        try:
            group_by = request.parameters["group_by"]
            dataset = self.datasets.get(request.dataset_id)
            columns = [dataset.table.column(name) for name in [*request.variables, group_by]]
            if any(len(column) != dataset.row_count for column in columns):
                raise CorrelationInputError("Subgroup columns have inconsistent row counts")
            groups = defaultdict(list)
            labels = {}
            for left, right, group in zip(*columns, strict=True):
                if any(_is_missing(value) for value in (left, right, group)):
                    continue
                if (
                    isinstance(group, bool)
                    or not isinstance(group, (str, int))
                    or not str(group).strip()
                ):
                    raise CorrelationInputError(
                        "Subgroups require non-empty text or integer labels"
                    )
                pair = [_numeric(left, request.variables[0]), _numeric(right, request.variables[1])]
                if not all(isfinite(value) for value in pair):
                    raise CorrelationInputError("Subgroup values must be finite")
                label = str(group)
                if label in labels and labels[label] != (type(group), group):
                    raise CorrelationInputError("Ambiguous subgroup labels")
                labels[label] = (type(group), group)
                groups[label].append(pair)
            if len(groups) > 50:
                return AnalysisResult(
                    method=self.name,
                    variables=request.variables,
                    status="SKIPPED",
                    warnings=[
                        "Subgroup sensitivity supports at most 50 complete groups; "
                        "no groups were sampled."
                    ],
                    execution_time=perf_counter() - started,
                )
            calculated, excluded = [], []
            for group, pairs in sorted(groups.items()):
                values = np.asarray(pairs, dtype=float).T
                try:
                    _validate_correlation_sample(values[0].tolist(), values[1].tolist(), 3)
                except CorrelationInputError as error:
                    excluded.append(
                        {"group": group, "sample_size": len(pairs), "reason": str(error)}
                    )
                    continue
                coefficient = float(pearsonr(*values).statistic)
                if not isfinite(coefficient):
                    excluded.append(
                        {
                            "group": group,
                            "sample_size": len(pairs),
                            "reason": "non-finite correlation",
                        }
                    )
                    continue
                calculated.append(
                    {"group": group, "correlation": coefficient, "sample_size": len(pairs)}
                )
            metadata = {"excluded_groups": excluded, "complete_group_count": len(groups)}
            if len(calculated) < 2:
                return AnalysisResult(
                    method=self.name,
                    variables=request.variables,
                    status="SKIPPED",
                    warnings=["Fewer than two subgroups have a valid correlation."],
                    metadata=metadata,
                    execution_time=perf_counter() - started,
                )
            return AnalysisResult(
                method=self.name,
                variables=request.variables,
                status="SUCCESS",
                result={"group_by": group_by, "groups": calculated},
                sample_size=sum(item["sample_size"] for item in calculated),
                metadata=metadata,
                warnings=[
                    CAUSALITY_WARNING,
                    "Subgroup correlations are descriptive; small or constant groups are "
                    "explicitly excluded, and no confidence intervals are calculated.",
                ],
                execution_time=perf_counter() - started,
            )
        except (DatasetRegistryError, KeyError, TypeError, ValueError) as error:
            return self._failed(request, str(error), started)


class AdditiveIdentityTool(_CorrelationTool):
    name = "additive_identity"

    def supports(self, request: ToolRequest) -> bool:
        return (
            request.method == self.name
            and len(request.variables) == 3
            and len(set(request.variables)) == 3
            and not request.parameters
        )

    async def execute(self, request: ToolRequest) -> AnalysisResult:
        started = perf_counter()
        if not self.supports(request):
            return self._failed(
                request, "Identity check requires two components and a total", started
            )
        try:
            first, second, total = self._values(request, request.variables)
            if not first:
                return AnalysisResult(
                    method=self.name,
                    variables=request.variables,
                    status="SKIPPED",
                    warnings=["No complete observations for the proposed additive identity."],
                    execution_time=perf_counter() - started,
                )
            residuals = np.abs(np.asarray(first) + np.asarray(second) - np.asarray(total))
            if not np.isfinite(residuals).all():
                raise CorrelationInputError("Identity residuals are non-finite")
            tolerance = 1e-8
            matched = int((residuals <= tolerance).sum())
            return AnalysisResult(
                method=self.name,
                variables=request.variables,
                status="SUCCESS",
                result={
                    "identity_confirmed": matched == len(first),
                    "matched_rows": matched,
                    "complete_rows": len(first),
                    "max_absolute_residual": float(residuals.max()),
                    "absolute_tolerance": tolerance,
                },
                sample_size=len(first),
                warnings=[
                    "Only the proposed sum is tested on complete observations; "
                    "an arithmetic relationship is not independent causal evidence."
                ],
                execution_time=perf_counter() - started,
            )
        except CorrelationInputError as error:
            return self._failed(request, str(error), started)
