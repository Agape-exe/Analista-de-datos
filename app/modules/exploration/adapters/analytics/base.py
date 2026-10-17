import asyncio
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from time import perf_counter
from typing import ClassVar

from pydantic import JsonValue

from app.modules.data_intake.ports.dataset_provider import DatasetProvider
from app.shared.application.errors import (
    AnalysisNotApplicableError,
    DatasetNotFoundError,
    ToolInputError,
)
from app.shared.config.settings import EdaSettings
from app.shared.contracts.datasource import RegisteredDataset
from app.shared.domain.enums.statuses import AnalysisStatus
from app.shared.domain.models.analysis import AnalysisResult, ToolRequest


@dataclass
class ToolOutput:
    """Values computed by a tool before they are wrapped in AnalysisResult."""

    result: JsonValue
    variables: list[str]
    p_value: float | None = None
    effect_size: float | None = None
    sample_size: int | None = None
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, JsonValue] = field(default_factory=dict)


def finite(value: float | None, digits: int = 6) -> float | None:
    """JSON-safe rounding; NaN and infinities become None instead of invalid JSON."""
    if value is None:
        return None
    number = float(value)
    return round(number, digits) if math.isfinite(number) else None


def probability(value: float | None) -> float | None:
    number = finite(value, 12)
    return None if number is None else min(max(number, 0.0), 1.0)


class DatasetTool(ABC):
    """Deterministic tool over a registered dataset, executed off the event loop."""

    name: ClassVar[str]
    min_variables: ClassVar[int] = 0
    max_variables: ClassVar[int | None] = None

    def __init__(
        self, datasets: DatasetProvider, options: EdaSettings, minimum_sample_size: int
    ) -> None:
        self.datasets = datasets
        self.options = options
        self.minimum_sample_size = minimum_sample_size

    def supports(self, request: ToolRequest) -> bool:
        count = len(request.variables)
        return (
            request.method == self.name
            and count >= self.min_variables
            and (self.max_variables is None or count <= self.max_variables)
        )

    async def execute(self, request: ToolRequest) -> AnalysisResult:
        started = perf_counter()
        status = AnalysisStatus.SUCCESS
        output: ToolOutput | None = None
        warnings: list[str] = []
        try:
            if not self.supports(request):
                raise ToolInputError(
                    f"{self.name} cannot run method={request.method!r} with "
                    f"{len(request.variables)} variable(s); expected {self._arity()}."
                )
            data = await self.datasets.get(request.dataset_id)
            unknown = [name for name in request.variables if not data.has_column(name)]
            if unknown:
                raise ToolInputError(f"Unknown column(s): {', '.join(unknown)}")
            output = await asyncio.to_thread(self.compute, data, request)
        except AnalysisNotApplicableError as error:
            status, warnings = AnalysisStatus.SKIPPED, [str(error)]
        except (DatasetNotFoundError, ToolInputError, ValueError, ArithmeticError) as error:
            status, warnings = AnalysisStatus.FAILED, [str(error)]
        elapsed = perf_counter() - started
        if output is None:
            return AnalysisResult(
                method=self.name,
                variables=list(request.variables),
                status=status,
                warnings=warnings,
                execution_time=elapsed,
            )
        return AnalysisResult(
            method=self.name,
            variables=output.variables,
            status=status,
            result=output.result,
            p_value=probability(output.p_value),
            effect_size=finite(output.effect_size),
            sample_size=output.sample_size,
            warnings=output.warnings,
            execution_time=elapsed,
            metadata=output.metadata,
        )

    def _arity(self) -> str:
        if self.max_variables is None:
            return f"at least {self.min_variables}"
        if self.min_variables == self.max_variables:
            return str(self.min_variables)
        return f"{self.min_variables} to {self.max_variables}"

    @abstractmethod
    def compute(self, data: RegisteredDataset, request: ToolRequest) -> ToolOutput: ...

    def require_sample(self, size: int, label: str) -> None:
        if size < self.minimum_sample_size:
            raise AnalysisNotApplicableError(
                f"{label}: {size} complete observations; "
                f"at least {self.minimum_sample_size} are required."
            )
