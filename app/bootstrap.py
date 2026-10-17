from collections.abc import Callable

from app.adapters.datasource.csv_source import CsvDataSource
from app.adapters.datasource.router import DataSourceRouter
from app.adapters.datasource.tsv_source import TsvDataSource
from app.adapters.datasource.upload_storage import TemporaryUploadStorage
from app.adapters.llm.disabled import DisabledLLMProvider
from app.agents.analyst import AnalysisAgent
from app.agents.critic import CriticAgent
from app.agents.data_understanding import DataUnderstandingAgent
from app.agents.insight import InsightAgent
from app.agents.planner import PlannerAgent
from app.analytics.factory import build_statistical_tool_registry
from app.analytics.registry import ToolRegistry
from app.application.errors import LLMDisabledError
from app.application.services.data_understanding import DataUnderstandingService
from app.application.services.dataset_registry import DatasetRegistry
from app.application.use_cases.analyze_dataset import AnalyzeDataset
from app.application.use_cases.intake_uploaded_dataset import IntakeUploadedDataset
from app.config.settings import Settings
from app.orchestration.graph import LangGraphWorkflow
from app.ports.agent import Agent
from app.ports.data_understanding import DataUnderstanding
from app.ports.datasource import DataSource
from app.ports.llm_provider import LLMProvider


def build_llm(settings: Settings) -> LLMProvider:
    if settings.llm.provider != "disabled":
        raise LLMDisabledError("Only the disabled provider adapter exists in this skeleton")
    return DisabledLLMProvider()


def build_datasource() -> DataSource:
    return DataSourceRouter({"csv": CsvDataSource(), "tsv": TsvDataSource()})


def build_data_understanding(settings: Settings) -> DataUnderstanding:
    return DataUnderstandingService(build_datasource(), settings.data_intake)


def build_intake_use_case(settings: Settings) -> IntakeUploadedDataset:
    return IntakeUploadedDataset(
        build_data_understanding(settings),
        TemporaryUploadStorage(
            settings.uploads.chunk_size_bytes, settings.uploads.temporary_directory
        ),
        settings.uploads.max_dataset_bytes,
        settings.uploads.max_dictionary_bytes,
    )


def build_agents(
    llm: LLMProvider,
    tools: ToolRegistry,
    understanding: DataUnderstanding,
    datasets: DatasetRegistry | None = None,
) -> list[Agent]:
    return [
        DataUnderstandingAgent(understanding, datasets),
        PlannerAgent(llm),
        AnalysisAgent(llm, tools),
        CriticAgent(llm),
        InsightAgent(llm),
    ]


def build_use_case(settings: Settings) -> AnalyzeDataset:
    build_llm(settings)

    def build_run() -> tuple[list[Agent], Callable[[], None]]:
        datasets = DatasetRegistry()
        return (
            build_agents(
                build_llm(settings),
                build_statistical_tool_registry(datasets),
                build_data_understanding(settings),
                datasets,
            ),
            datasets.clear,
        )

    return AnalyzeDataset(LangGraphWorkflow(settings, run_factory=build_run))
