import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from time import perf_counter
from typing import Any
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.application.dto.agent import AgentContext
from app.application.dto.analysis_input import AnalysisInput, resolve_configuration
from app.application.services.reporting import assemble_report
from app.config.settings import Settings
from app.domain.enums.statuses import AnalysisStatus
from app.domain.models.metrics import ExperimentMetrics
from app.domain.models.report import AnalysisReport
from app.evaluation.metrics import TimingRecorder
from app.observability.logging import log_stage
from app.observability.telemetry import telemetry_scope
from app.orchestration.state import AgentState
from app.ports.agent import Agent

Node = Callable[[AgentState], Awaitable[Mapping[str, Any]]]
RunFactory = Callable[[], tuple[Sequence[Agent], Callable[[], None]]]
CONTEXT_FIELDS = set(AgentContext.model_fields)


def _noop_release() -> None:
    return None


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
        if result.update.insights and state["metrics"].time_to_first_insight is None:
            measured = updates.get("metrics", state["metrics"]).model_copy(deep=True)
            measured.time_to_first_insight = perf_counter() - state["started_monotonic"]
            updates["metrics"] = measured
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
        started_monotonic=perf_counter(),
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
    """Run a static graph or create isolated agents and local data per execution."""

    def __init__(
        self,
        settings: Settings,
        agents: Sequence[Agent] | None = None,
        run_factory: RunFactory | None = None,
    ) -> None:
        if (agents is None) == (run_factory is None):
            raise ValueError("Workflow requires exactly one of agents or run_factory")
        self.settings = settings
        self._run_factory = run_factory
        self.graph = build_graph(agents) if agents is not None else None

    async def run(self, analysis_input: AnalysisInput) -> AnalysisReport:
        state = initial_state(analysis_input, self.settings)
        recorder = TimingRecorder()
        failure: str | None = None
        completed: Mapping[str, Any] = {}
        release = _noop_release
        graph = self.graph

        with telemetry_scope() as telemetry:
            try:
                with recorder.measure("total"):
                    if self._run_factory is not None:
                        agents, release = self._run_factory()
                        graph = build_graph(agents)
                    assert graph is not None
                    async with asyncio.timeout(state["configuration"].performance.timeout_seconds):
                        completed = await graph.ainvoke(state)
            except TimeoutError:
                failure = "Workflow timeout exceeded"
            except asyncio.CancelledError:
                raise
            except Exception as error:
                failure = f"Workflow execution failed: {error}"
            finally:
                release()

        recorded_metrics: ExperimentMetrics = completed.get("metrics", state["metrics"])
        metrics = recorded_metrics.model_copy(
            update={
                "total_response_time": recorder.durations["total"],
                "llm_calls": recorded_metrics.llm_calls
                if recorded_metrics.llm_calls is not None
                else 0,
                "tool_calls": recorded_metrics.tool_calls
                if recorded_metrics.tool_calls is not None
                else 0,
                "iterations": recorded_metrics.iterations
                if recorded_metrics.iterations is not None
                else 1,
            }
        )
        if telemetry.llm_calls:
            metrics.llm_calls = telemetry.llm_calls
            metrics.tokens_used = None if telemetry.missing_token_usage else telemetry.tokens_used
        if telemetry.tool_calls:
            metrics.tool_calls = telemetry.tool_calls
        if failure is not None:
            log_stage(
                state["run_id"], "workflow", AnalysisStatus.FAILED, recorder.durations["total"]
            )
            return AnalysisReport(
                run_id=state["run_id"],
                status=AnalysisStatus.FAILED,
                errors=[failure],
                metrics=metrics,
                execution_trace=telemetry.events,
            )
        report = assemble_report(completed, metrics)
        report.execution_trace = telemetry.events
        return report
