from time import perf_counter

from app.application.dto.agent import AgentContext, AgentResult, AgentUpdate
from app.application.errors import DatasetRegistryError, DataSourceError
from app.application.services.dataset_registry import DatasetRegistry
from app.domain.enums.statuses import AnalysisStatus
from app.ports.data_understanding import DataUnderstanding


class DataUnderstandingAgent:
    """Deterministic intake stage; only metadata crosses the agent boundary."""

    name = "DataUnderstanding"

    def __init__(
        self, understanding: DataUnderstanding, datasets: DatasetRegistry | None = None
    ) -> None:
        self.understanding = understanding
        self.datasets = datasets

    async def run(self, context: AgentContext) -> AgentResult:
        started = perf_counter()
        try:
            result = await self.understanding.understand(context.input)
        except DataSourceError as error:
            return AgentResult(
                agent_name=self.name,
                status=AnalysisStatus.FAILED,
                errors=[str(error)],
                update=AgentUpdate(
                    metrics=context.metrics.model_copy(
                        update={"profiling_time": perf_counter() - started}
                    )
                ),
            )
        if self.datasets is not None:
            try:
                self.datasets.register(result.dataset)
            except DatasetRegistryError as error:
                return AgentResult(
                    agent_name=self.name,
                    status=AnalysisStatus.FAILED,
                    errors=[str(error)],
                    update=AgentUpdate(
                        metrics=context.metrics.model_copy(
                            update={"profiling_time": result.profiling_time}
                        )
                    ),
                )
        return AgentResult(
            agent_name=self.name,
            status=AnalysisStatus.SUCCESS,
            update=AgentUpdate(
                dataset_id=result.dataset.dataset_id,
                dataset_profile=result.profile,
                data_dictionary=result.data_dictionary,
                metrics=context.metrics.model_copy(
                    update={"profiling_time": result.profiling_time}
                ),
            ),
            warnings=result.warnings,
        )
