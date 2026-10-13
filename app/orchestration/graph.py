import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.application.dto.agent import AgentContext
from app.application.dto.analysis_input import AnalysisInput, resolve_configuration
from app.config.settings import Settings
from app.domain.enums.statuses import AnalysisStatus
from app.domain.models.metrics import ExperimentMetrics
from app.domain.models.report import AnalysisReport
from app.evaluation.metrics import TimingRecorder
from app.observability.logging import log_stage
from app.orchestration.state import AgentState
from app.ports.agent import Agent

Node = Callable[[AgentState], Awaitable[Mapping[str, Any]]]
CONTEXT_FIELDS = set(AgentContext.model_fields)


def _agent_node(agent: Agent) -> Node:
    async def node(state: AgentState) -> Mapping[str, Any]:
        context = AgentContext.model_validate(
            {key: value for key, value in state.items() if key in CONTEXT_FIELDS}
        )
        recorder = TimingRecorder()
        with recorder.measure(agent.name):
            result = await agent.run(context)
        duration = recorder.durations[agent.name]
        log_stage(state["run_id"], agent.name, result.status, duration)
        # Retain Pydantic objects internally; serialize only at the outer boundary.
        updates: dict[str, Any] = {
            field: getattr(result.update, field) for field in result.update.model_fields_set
        }
        updates.update(
            stage_statuses=state["stage_statuses"] | {agent.name: result.status},
            stage_durations=state["stage_durations"] | {agent.name: duration},
            errors=state["errors"] + result.errors,
            warnings=state["warnings"] + result.warnings,
        )
        return updates

    return node


def _stage_route(agent_name: str) -> Callable[[AgentState], str]:
    def route(state: AgentState) -> str:
        return "failed" if state["stage_statuses"][agent_name] == AnalysisStatus.FAILED else "next"

    return route


def build_graph(agents: Sequence[Agent]) -> CompiledStateGraph:
    """Linear workflow with fail-fast routing; critic feedback is a future extension."""
    if not agents or len({agent.name for agent in agents}) != len(agents):
        raise ValueError("Graph requires agents with unique names")
    graph = StateGraph(AgentState)
    for agent in agents:
        graph.add_node(agent.name, _agent_node(agent))
    graph.add_edge(START, agents[0].name)
    for current, following in zip(agents, agents[1:], strict=False):
        graph.add_conditional_edges(
            current.name, _stage_route(current.name), {"failed": END, "next": following.name}
        )
    graph.add_edge(agents[-1].name, END)
    return graph.compile()


def initial_state(analysis_input: AnalysisInput, settings: Settings) -> AgentState:
    return AgentState(
        run_id=str(uuid4()),
        input=analysis_input,
        configuration=resolve_configuration(settings, analysis_input.configuration),
        dataset_id=None,
        dataset_profile=None,
        data_dictionary=analysis_input.data_dictionary,
        associations=[],
        analysis_plan=None,
        analysis_results=[],
        evidence=[],
        relationship_assessments=[],
        insights=[],
        metrics=ExperimentMetrics(),
        errors=[],
        warnings=[],
        stage_statuses={},
        stage_durations={},
        iterations=0,
    )


class LangGraphWorkflow:
    """Run actual data intake followed by explicit skeleton stages."""

    def __init__(self, settings: Settings, agents: Sequence[Agent]) -> None:
        self.settings = settings
        self.graph = build_graph(agents)

    async def run(self, analysis_input: AnalysisInput) -> AnalysisReport:
        state = initial_state(analysis_input, self.settings)
        recorder = TimingRecorder()
        failure: str | None = None
        completed: Mapping[str, Any] = {}
        with recorder.measure("total"):
            try:
                async with asyncio.timeout(state["configuration"].performance.timeout_seconds):
                    completed = await self.graph.ainvoke(state)
            except TimeoutError:
                failure = "Workflow timeout exceeded"
            except Exception as error:
                # Recover at the workflow boundary; cancellations remain propagating.
                failure = f"Workflow execution failed: {error}"
        recorded_metrics: ExperimentMetrics = completed.get("metrics", state["metrics"])
        metrics = recorded_metrics.model_copy(
            update={
                "total_response_time": recorder.durations["total"],
                "llm_calls": 0,
                "tool_calls": 0,
                "iterations": 1,
            }
        )
        if failure is not None:
            log_stage(
                state["run_id"], "workflow", AnalysisStatus.FAILED, recorder.durations["total"]
            )
            return AnalysisReport(
                run_id=state["run_id"],
                status=AnalysisStatus.FAILED,
                errors=[failure],
                metrics=metrics,
            )
        failed = completed["errors"] or any(
            status == AnalysisStatus.FAILED for status in completed["stage_statuses"].values()
        )
        return AnalysisReport(
            run_id=state["run_id"],
            status=AnalysisStatus.FAILED if failed else AnalysisStatus.SKIPPED,
            dataset_profile=completed["dataset_profile"],
            data_dictionary=completed["data_dictionary"],
            analysis_results=completed["analysis_results"],
            insights=completed["insights"],
            metrics=metrics,
            errors=completed["errors"],
            warnings=completed["warnings"],
            stage_statuses=completed["stage_statuses"],
            stage_durations=completed["stage_durations"],
        )
