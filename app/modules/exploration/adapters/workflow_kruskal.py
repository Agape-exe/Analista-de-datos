"""Expose the existing EDA measure as an Analysis tool at the composition boundary."""

from time import perf_counter

import numpy as np

from app.modules.exploration.adapters.analytics.association.measures import kruskal_wallis
from app.shared.application.dataset_registry import DatasetRegistry
from app.shared.application.errors import AnalysisNotApplicableError, DatasetRegistryError
from app.shared.domain.enums.statuses import AnalysisStatus
from app.shared.domain.models.analysis import AnalysisResult, ToolRequest


class WorkflowKruskalTool:
    name = "kruskal_wallis"

    def __init__(self, datasets: DatasetRegistry) -> None:
        self.datasets = datasets

    def supports(self, request: ToolRequest) -> bool:
        return (
            request.method == self.name
            and len(request.variables) == 2
            and len(set(request.variables)) == 2
            and not request.parameters
        )

    async def execute(self, request: ToolRequest) -> AnalysisResult:
        started = perf_counter()
        try:
            if not self.supports(request):
                raise ValueError("Kruskal-Wallis requires a category and a numeric outcome")
            data = self.datasets.get(request.dataset_id)
            labels = np.array(data.table.column(request.variables[0]), dtype=object)
            values = np.array(data.table.column(request.variables[1]), dtype=float)
            measured = kruskal_wallis(values, labels)
            return AnalysisResult(
                method=self.name,
                variables=request.variables,
                status=AnalysisStatus.SUCCESS,
                result={"h_statistic": measured.statistic},
                p_value=measured.p_value,
                effect_size=measured.effect_size,
                sample_size=measured.sample_size,
                metadata=dict(measured.details),
                warnings=measured.warnings
                + ["Statistical association does not establish causation."],
                execution_time=perf_counter() - started,
            )
        except (
            ValueError,
            TypeError,
            KeyError,
            DatasetRegistryError,
            AnalysisNotApplicableError,
        ) as error:
            return AnalysisResult(
                method=self.name,
                variables=request.variables,
                status=AnalysisStatus.SKIPPED
                if isinstance(error, AnalysisNotApplicableError)
                else AnalysisStatus.FAILED,
                warnings=[str(error)],
                execution_time=perf_counter() - started,
            )
