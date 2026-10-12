from app.adapters.datasource.csv_source import CsvDataSource
from app.adapters.llm.disabled import DisabledLLMProvider
from app.agents.analyst import AnalysisAgent
from app.agents.critic import CriticAgent
from app.agents.data_understanding import DataUnderstandingAgent
from app.agents.insight import InsightAgent
from app.agents.planner import PlannerAgent
from app.analytics.registry import ToolRegistry
from app.application.errors import LLMDisabledError
from app.application.use_cases.analyze_dataset import AnalyzeDataset
from app.config.settings import Settings
from app.orchestration.graph import LangGraphWorkflow
from app.ports.agent import Agent
from app.ports.datasource import DataSource
from app.ports.llm_provider import LLMProvider


def build_llm(settings: Settings) -> LLMProvider:
    if settings.llm.provider != "disabled":
        raise LLMDisabledError("Only the disabled provider adapter exists in this skeleton")
    return DisabledLLMProvider()


def build_datasource() -> DataSource:
    return CsvDataSource()


def build_agents(llm: LLMProvider, tools: ToolRegistry) -> list[Agent]:
    return [
        DataUnderstandingAgent(llm),
        PlannerAgent(llm),
        AnalysisAgent(llm, tools),
        CriticAgent(llm),
        InsightAgent(llm),
    ]


def build_use_case(settings: Settings) -> AnalyzeDataset:
    agents = build_agents(build_llm(settings), ToolRegistry())
    return AnalyzeDataset(LangGraphWorkflow(settings, agents))
