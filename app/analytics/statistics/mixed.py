from collections import defaultdict
from math import isfinite, isnan, sqrt
from numbers import Integral, Real
from time import perf_counter

from scipy.stats import chi2_contingency, f_oneway

from app.application.dto.planning import AnovaGroupSummaries, AnovaGroupSummary
from app.application.errors import DatasetRegistryError
from app.application.services.dataset_registry import DatasetRegistry
from app.domain.enums.statuses import AnalysisStatus
from app.domain.models.analysis import AnalysisResult, ToolRequest

ASSOCIATION_WARNING = "Statistical association does not establish causation."
ANOVA_ASSUMPTION_WARNING = (
    "ANOVA assumes independent observations, approximately normal residuals, and similar variances."
)


class MixedStatisticsInputError(ValueError):
    """The requested local columns cannot produce a valid statistical result."""


class _MixedStatisticsTool:
    name: str

    def __init__(self, datasets: DatasetRegistry) -> None:
        self.datasets = datasets

    def _columns(self, request: ToolRequest) -> list[list[object]]:
        try:
            dataset = self.datasets.get(request.dataset_id)
            columns = [dataset.table.column(name) for name in request.variables]
        except (DatasetRegistryError, KeyError, TypeError, ValueError) as error:
            raise MixedStatisticsInputError(str(error)) from error
        if any(len(column) != dataset.row_count for column in columns):
            raise MixedStatisticsInputError("Requested columns have inconsistent row counts")
        return columns

    def _failed(self, request: ToolRequest, message: str, started: float) -> AnalysisResult:
        return AnalysisResult(
            method=self.name,
            variables=request.variables,
            status=AnalysisStatus.FAILED,
            warnings=[message],
            execution_time=perf_counter() - started,
        )


class _ContingencyTool(_MixedStatisticsTool):
    def _contingency(self, request: ToolRequest) -> "Contingency":
        first, second = self._columns(request)
        counts: dict[tuple[str | int, str | int], int] = defaultdict(int)
        first_categories: set[str | int] = set()
        second_categories: set[str | int] = set()
        sample_size = 0
        for left, right in zip(first, second, strict=True):
            if _is_missing(left) or _is_missing(right):
                continue
            first_value = _categorical(left, request.variables[0])
            second_value = _categorical(right, request.variables[1])
            first_categories.add(first_value)
            second_categories.add(second_value)
            counts[(first_value, second_value)] += 1
            sample_size += 1
        if sample_size == 0:
            raise MixedStatisticsInputError("Contingency table has no complete observations")
        if len(first_categories) < 2 or len(second_categories) < 2:
            raise MixedStatisticsInputError(
                "Chi-square independence requires at least two categories per variable"
            )
        rows = tuple(sorted(first_categories, key=_category_sort_key))
        columns = tuple(sorted(second_categories, key=_category_sort_key))
        observed = [[counts[(row, column)] for column in columns] for row in rows]
        try:
            calculation = chi2_contingency(observed, correction=False)
        except ValueError as error:
            raise MixedStatisticsInputError(f"Invalid contingency table: {error}") from error
        expected = calculation.expected_freq
        if (expected <= 0).any():
            raise MixedStatisticsInputError(
                "Contingency table has non-positive expected frequencies"
            )
        low_expected = int((expected < 5).sum())
        return Contingency(
            statistic=float(calculation.statistic),
            p_value=float(calculation.pvalue),
            degrees_of_freedom=int(calculation.dof),
            sample_size=sample_size,
            row_count=len(rows),
            column_count=len(columns),
            low_expected_cells=low_expected,
        )


class ChiSquareIndependenceTool(_ContingencyTool):
    name = "chi_square"

    def supports(self, request: ToolRequest) -> bool:
        return _two_variables(request) and request.method == self.name

    async def execute(self, request: ToolRequest) -> AnalysisResult:
        started = perf_counter()
        if not self.supports(request):
            return self._failed(
                request, "Chi-square requires exactly two distinct categorical variables", started
            )
        try:
            table = self._contingency(request)
            return _contingency_result(request, self.name, table, started)
        except MixedStatisticsInputError as error:
            return self._failed(request, str(error), started)


class CramersVTool(_ContingencyTool):
    name = "cramers_v"

    def supports(self, request: ToolRequest) -> bool:
        return _two_variables(request) and request.method == self.name

    async def execute(self, request: ToolRequest) -> AnalysisResult:
        started = perf_counter()
        if not self.supports(request):
            return self._failed(
                request, "Cramer's V requires exactly two distinct categorical variables", started
            )
        try:
            table = self._contingency(request)
            denominator = table.sample_size * min(table.row_count - 1, table.column_count - 1)
            if denominator <= 0:
                raise MixedStatisticsInputError("Cramer's V has an invalid contingency table shape")
            effect_size = sqrt(table.statistic / denominator)
            if not isfinite(effect_size) or not 0 <= effect_size <= 1:
                raise MixedStatisticsInputError("Cramer's V produced an out-of-range result")
            metadata = _contingency_metadata(table) | {"variant": "standard"}
            return AnalysisResult(
                method=self.name,
                variables=request.variables,
                status=AnalysisStatus.SUCCESS,
                result={"cramers_v": effect_size},
                p_value=table.p_value,
                effect_size=effect_size,
                sample_size=table.sample_size,
                warnings=_contingency_warnings(table),
                execution_time=perf_counter() - started,
                metadata=metadata,
            )
        except MixedStatisticsInputError as error:
            return self._failed(request, str(error), started)


class OneWayAnovaTool(_MixedStatisticsTool):
    name = "anova_one_way"

    def supports(self, request: ToolRequest) -> bool:
        return _two_variables(request) and request.method == self.name

    async def execute(self, request: ToolRequest) -> AnalysisResult:
        started = perf_counter()
        if not self.supports(request):
            return self._failed(
                request,
                "One-way ANOVA requires a categorical group and a distinct numeric outcome",
                started,
            )
        try:
            groups = self._groups(request)
            values_by_group = list(groups.values())
            sample_size = sum(len(values) for values in values_by_group)
            group_count = len(values_by_group)
            if group_count < 2:
                raise MixedStatisticsInputError("One-way ANOVA requires at least two valid groups")
            if any(len(values) < 2 for values in values_by_group):
                raise MixedStatisticsInputError(
                    "Each ANOVA group requires at least two observations"
                )
            if sample_size <= group_count:
                raise MixedStatisticsInputError("One-way ANOVA has insufficient observations")
            total_mean = sum(sum(values) for values in values_by_group) / sample_size
            total_sum_squares = sum(
                (value - total_mean) ** 2 for values in values_by_group for value in values
            )
            if total_sum_squares == 0:
                raise MixedStatisticsInputError(
                    "One-way ANOVA is undefined when total variance is zero"
                )
            calculation = f_oneway(*values_by_group)
            statistic = float(calculation.statistic)
            p_value = float(calculation.pvalue)
            if not isfinite(statistic) or not isfinite(p_value):
                raise MixedStatisticsInputError("One-way ANOVA produced a non-finite result")
            between_sum_squares = sum(
                len(values) * ((sum(values) / len(values)) - total_mean) ** 2
                for values in values_by_group
            )
            effect_size = between_sum_squares / total_sum_squares
            if not isfinite(effect_size) or not 0 <= effect_size <= 1:
                raise MixedStatisticsInputError("One-way ANOVA produced an invalid eta squared")
            return AnalysisResult(
                method=self.name,
                variables=request.variables,
                status=AnalysisStatus.SUCCESS,
                result={"f_statistic": statistic},
                p_value=p_value,
                effect_size=effect_size,
                sample_size=sample_size,
                warnings=[ANOVA_ASSUMPTION_WARNING, ASSOCIATION_WARNING],
                execution_time=perf_counter() - started,
                metadata={
                    "group_count": group_count,
                    "degrees_of_freedom_between": group_count - 1,
                    "degrees_of_freedom_within": sample_size - group_count,
                    "effect_size": "eta_squared",
                },
            )
        except MixedStatisticsInputError as error:
            return self._failed(request, str(error), started)

    def _groups(self, request: ToolRequest) -> dict[str | int, list[float]]:
        categories, outcomes = self._columns(request)
        return _anova_groups(categories, outcomes, request.variables)


def _anova_groups(
    categories: list[object], outcomes: list[object], variables: list[str]
) -> dict[str | int, list[float]]:
    groups: dict[str | int, list[float]] = defaultdict(list)
    for category, outcome in zip(categories, outcomes, strict=True):
        if _is_missing(category) or _is_missing(outcome):
            continue
        groups[_categorical(category, variables[0])].append(_numeric(outcome, variables[1]))
    return dict(groups)


class AnovaGroupProfiler(_MixedStatisticsTool):
    """Summarize bounded candidate pairs locally without executing an analysis tool."""

    def summarize(self, dataset_id: str, pairs: list[tuple[str, str]]) -> AnovaGroupSummaries:
        summaries: AnovaGroupSummaries = {}
        for category, outcome in pairs:
            request = ToolRequest(
                dataset_id=dataset_id, method="anova_one_way", variables=[category, outcome]
            )
            try:
                groups = _anova_groups(*self._columns(request), request.variables)
            except MixedStatisticsInputError:
                # Preserve data/type errors for the tool's normal validation boundary.
                continue
            summaries[(category, outcome)] = AnovaGroupSummary(
                group_count=len(groups),
                minimum_group_size=min(map(len, groups.values()), default=0),
            )
        return summaries


class Contingency:
    def __init__(
        self,
        statistic: float,
        p_value: float,
        degrees_of_freedom: int,
        sample_size: int,
        row_count: int,
        column_count: int,
        low_expected_cells: int,
    ) -> None:
        self.statistic = statistic
        self.p_value = p_value
        self.degrees_of_freedom = degrees_of_freedom
        self.sample_size = sample_size
        self.row_count = row_count
        self.column_count = column_count
        self.low_expected_cells = low_expected_cells


def _two_variables(request: ToolRequest) -> bool:
    return (
        len(request.variables) == 2 and len(set(request.variables)) == 2 and not request.parameters
    )


def _is_missing(value: object) -> bool:
    return value is None or (isinstance(value, Real) and isnan(float(value)))


def _categorical(value: object, name: str) -> str | int:
    if isinstance(value, bool):
        raise MixedStatisticsInputError(f"Column '{name}' cannot use boolean category labels")
    if isinstance(value, str):
        if not value.strip():
            raise MixedStatisticsInputError(f"Column '{name}' cannot use empty category labels")
        return value
    if isinstance(value, Integral):
        return int(value)
    raise MixedStatisticsInputError(
        f"Column '{name}' must contain text labels or integer-coded categories"
    )


def _numeric(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise MixedStatisticsInputError(f"Column '{name}' must contain only numeric values")
    numeric = float(value)
    if not isfinite(numeric):
        raise MixedStatisticsInputError(f"Column '{name}' cannot contain infinite values")
    return numeric


def _category_sort_key(value: str | int) -> tuple[int, str | int]:
    return (0, value) if isinstance(value, int) else (1, value)


def _contingency_warnings(table: Contingency) -> list[str]:
    warnings = [ASSOCIATION_WARNING]
    if table.low_expected_cells:
        warnings.append(
            f"{table.low_expected_cells} expected cells are below 5; "
            "chi-square approximation may be unreliable."
        )
    return warnings


def _contingency_metadata(table: Contingency) -> dict[str, int | bool]:
    return {
        "degrees_of_freedom": table.degrees_of_freedom,
        "row_categories": table.row_count,
        "column_categories": table.column_count,
        "low_expected_cells": table.low_expected_cells,
        "continuity_correction": False,
    }


def _contingency_result(
    request: ToolRequest, method: str, table: Contingency, started: float
) -> AnalysisResult:
    if not isfinite(table.statistic) or not isfinite(table.p_value):
        raise MixedStatisticsInputError("Chi-square produced a non-finite result")
    return AnalysisResult(
        method=method,
        variables=request.variables,
        status=AnalysisStatus.SUCCESS,
        result={"chi_square": table.statistic},
        p_value=table.p_value,
        sample_size=table.sample_size,
        warnings=_contingency_warnings(table),
        execution_time=perf_counter() - started,
        metadata=_contingency_metadata(table),
    )
