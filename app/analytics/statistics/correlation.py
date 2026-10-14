from math import isfinite, isnan, sqrt
from numbers import Real
from time import perf_counter

from scipy.stats import linregress, pearsonr, spearmanr, t

from app.application.errors import DatasetRegistryError
from app.application.services.dataset_registry import DatasetRegistry
from app.domain.enums.statuses import AnalysisStatus
from app.domain.models.analysis import AnalysisResult, ToolRequest

CAUSALITY_WARNING = "Correlation measures association and does not establish causation."


class CorrelationInputError(ValueError):
    """The requested columns cannot produce a valid correlation."""


class _CorrelationTool:
    name: str

    def __init__(self, datasets: DatasetRegistry) -> None:
        self.datasets = datasets

    def _values(self, request: ToolRequest, names: list[str]) -> list[list[float]]:
        try:
            dataset = self.datasets.get(request.dataset_id)
            columns = [dataset.table.column(name) for name in names]
        except (DatasetRegistryError, KeyError, ValueError, TypeError) as error:
            raise CorrelationInputError(str(error)) from error
        if any(len(column) != dataset.row_count for column in columns):
            raise CorrelationInputError("Requested columns have inconsistent row counts")

        complete: list[list[float]] = [[] for _ in columns]
        for row in zip(*columns, strict=True):
            if any(_is_missing(value) for value in row):
                continue
            converted = [_numeric(value, name) for value, name in zip(row, names, strict=True)]
            if not all(isfinite(value) for value in converted):
                raise CorrelationInputError("Correlation columns cannot contain infinite values")
            for values, value in zip(complete, converted, strict=True):
                values.append(value)
        return complete

    def _failed(self, request: ToolRequest, message: str, started: float) -> AnalysisResult:
        return AnalysisResult(
            method=self.name,
            variables=request.variables,
            status=AnalysisStatus.FAILED,
            warnings=[message],
            execution_time=perf_counter() - started,
        )


class PearsonCorrelationTool(_CorrelationTool):
    name = "pearson"

    def supports(self, request: ToolRequest) -> bool:
        return (
            request.method == self.name
            and len(request.variables) == 2
            and _two_distinct(request)
            and not request.parameters
        )

    async def execute(self, request: ToolRequest) -> AnalysisResult:
        started = perf_counter()
        if not self.supports(request):
            return self._failed(
                request, "Pearson requires exactly two distinct numeric variables", started
            )
        try:
            first, second = self._values(request, request.variables)
            _validate_correlation_sample(first, second, minimum_size=3)
            calculation = pearsonr(first, second)
            return _success(
                request,
                self.name,
                float(calculation.statistic),
                float(calculation.pvalue),
                len(first),
                started,
            )
        except CorrelationInputError as error:
            return self._failed(request, str(error), started)


class SpearmanCorrelationTool(_CorrelationTool):
    name = "spearman"

    def supports(self, request: ToolRequest) -> bool:
        return (
            request.method == self.name
            and len(request.variables) == 2
            and _two_distinct(request)
            and not request.parameters
        )

    async def execute(self, request: ToolRequest) -> AnalysisResult:
        started = perf_counter()
        if not self.supports(request):
            return self._failed(
                request, "Spearman requires exactly two distinct numeric variables", started
            )
        try:
            first, second = self._values(request, request.variables)
            _validate_correlation_sample(first, second, minimum_size=3)
            calculation = spearmanr(first, second)
            return _success(
                request,
                self.name,
                float(calculation.statistic),
                float(calculation.pvalue),
                len(first),
                started,
            )
        except CorrelationInputError as error:
            return self._failed(request, str(error), started)


class PartialCorrelationTool(_CorrelationTool):
    name = "partial_correlation"

    def supports(self, request: ToolRequest) -> bool:
        control = request.parameters.get("control_variable")
        return (
            request.method == self.name
            and len(request.variables) == 2
            and _two_distinct(request)
            and set(request.parameters) == {"control_variable"}
            and isinstance(control, str)
            and control not in request.variables
        )

    async def execute(self, request: ToolRequest) -> AnalysisResult:
        started = perf_counter()
        if not self.supports(request):
            return self._failed(
                request,
                "Partial correlation requires two variables and parameters.control_variable",
                started,
            )
        control = request.parameters["control_variable"]
        assert isinstance(control, str)
        try:
            first, second, control_values = self._values(request, [*request.variables, control])
            _validate_correlation_sample(first, second, minimum_size=4)
            if _is_constant(control_values):
                raise CorrelationInputError("Control variable must contain more than one value")
            first_residuals = _residuals(first, control_values)
            second_residuals = _residuals(second, control_values)
            _validate_correlation_sample(first_residuals, second_residuals, minimum_size=4)
            coefficient = float(pearsonr(first_residuals, second_residuals).statistic)
            degrees_of_freedom = len(first) - 3
            if degrees_of_freedom <= 0:
                raise CorrelationInputError(
                    "Partial correlation has insufficient degrees of freedom"
                )
            p_value = _partial_p_value(coefficient, degrees_of_freedom)
            return _success(
                request,
                self.name,
                coefficient,
                p_value,
                len(first),
                started,
                metadata={"control_variable": control, "degrees_of_freedom": degrees_of_freedom},
            )
        except CorrelationInputError as error:
            return self._failed(request, str(error), started)


def _two_distinct(request: ToolRequest) -> bool:
    return len(set(request.variables)) == 2


def _is_missing(value: object) -> bool:
    return value is None or (isinstance(value, Real) and isnan(float(value)))


def _numeric(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise CorrelationInputError(f"Column '{name}' must contain only numeric values")
    return float(value)


def _validate_correlation_sample(
    first: list[float], second: list[float], minimum_size: int
) -> None:
    if len(first) != len(second):
        raise CorrelationInputError("Correlation columns have inconsistent row counts")
    if len(first) < minimum_size:
        raise CorrelationInputError(
            f"Correlation requires at least {minimum_size} complete numeric observations"
        )
    if _is_constant(first) or _is_constant(second):
        raise CorrelationInputError("Correlation is undefined for constant columns")


def _is_constant(values: list[float]) -> bool:
    return min(values) == max(values)


def _residuals(values: list[float], controls: list[float]) -> list[float]:
    regression = linregress(controls, values)
    residuals = [
        value - (regression.slope * control + regression.intercept)
        for value, control in zip(values, controls, strict=True)
    ]
    if not all(isfinite(value) for value in residuals):
        raise CorrelationInputError("Partial correlation regression produced non-finite residuals")
    return residuals


def _partial_p_value(coefficient: float, degrees_of_freedom: int) -> float:
    if not isfinite(coefficient):
        raise CorrelationInputError("Partial correlation produced a non-finite coefficient")
    if abs(coefficient) == 1:
        return 0.0
    statistic = coefficient * sqrt(degrees_of_freedom / (1 - coefficient**2))
    p_value = float(2 * t.sf(abs(statistic), degrees_of_freedom))
    if not isfinite(p_value):
        raise CorrelationInputError("Partial correlation produced a non-finite p-value")
    return p_value


def _success(
    request: ToolRequest,
    method: str,
    coefficient: float,
    p_value: float,
    sample_size: int,
    started: float,
    metadata: dict[str, str | int] | None = None,
) -> AnalysisResult:
    if not isfinite(coefficient) or not isfinite(p_value):
        raise CorrelationInputError("Correlation produced a non-finite result")
    return AnalysisResult(
        method=method,
        variables=request.variables,
        status=AnalysisStatus.SUCCESS,
        result={"correlation": coefficient},
        effect_size=coefficient,
        p_value=p_value,
        sample_size=sample_size,
        warnings=[CAUSALITY_WARNING],
        execution_time=perf_counter() - started,
        metadata=metadata or {},
    )
