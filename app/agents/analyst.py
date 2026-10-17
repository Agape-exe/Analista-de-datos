import asyncio
from collections import deque
from time import perf_counter

from app.agents.base import SkeletonAgent
from app.analytics.registry import ToolRegistry
from app.application.dto.agent import AgentContext, AgentResult, AgentUpdate
from app.application.errors import ToolRegistryError
from app.domain.enums.statuses import AnalysisStatus
from app.domain.models.analysis import AnalysisPlan, AnalysisResult, AnalysisStep
from app.ports.llm_provider import LLMProvider


class AnalysisAgent(SkeletonAgent):
    name = "Analysis"

    def __init__(self, llm: LLMProvider, tools: ToolRegistry) -> None:
        super().__init__(llm)
        self.tools = tools

    async def run(self, context: AgentContext) -> AgentResult:
        """Execute an externally supplied plan without exposing local dataset rows."""
        started = perf_counter()
        plan = context.analysis_plan
        if plan is None:
            return self._skipped(context, "Analysis requires an executable analysis plan.", started)
        if not plan.steps:
            return self._skipped(context, "Analysis plan contains no executable steps.", started)

        structural_errors = _validate_plan(plan, context)
        if structural_errors:
            return self._failed_structurally(context, structural_errors, started)

        ordered_steps = _topological_steps(plan.steps)
        results: list[AnalysisResult] = []
        statuses: dict[str, AnalysisStatus] = {}
        errors: list[str] = []
        calls = 0
        budget = context.configuration.analysis.max_tool_calls

        for step in ordered_steps:
            blocked = next(
                (
                    dependency
                    for dependency in step.depends_on
                    if statuses[dependency] != AnalysisStatus.SUCCESS
                ),
                None,
            )
            if blocked is not None:
                result = _skipped_step(step, f"Dependency '{blocked}' did not succeed.")
            elif calls >= budget:
                result = _skipped_step(step, "Analysis tool-call budget was exhausted.")
            else:
                try:
                    tool = self.tools.resolve(step.request)
                except ToolRegistryError as error:
                    result = _failed_step(step, str(error))
                else:
                    calls += 1
                    try:
                        result = await tool.execute(step.request)
                    except asyncio.CancelledError:
                        raise
                    except Exception as error:
                        result = _failed_step(step, f"Tool execution failed: {error}")
            traced = _with_trace(result, step)
            results.append(traced)
            statuses[step.step_id] = traced.status
            if traced.status == AnalysisStatus.FAILED:
                errors.append(f"{step.step_id}: {'; '.join(traced.warnings) or 'analysis failed'}")

        metrics = context.metrics.model_copy(
            update={"tool_calls": calls, "analytics_time": perf_counter() - started}
        )
        if errors:
            status = AnalysisStatus.FAILED
        elif any(result.status == AnalysisStatus.SUCCESS for result in results):
            status = AnalysisStatus.SUCCESS
        else:
            status = AnalysisStatus.SKIPPED
        return AgentResult(
            agent_name=self.name,
            status=status,
            update=AgentUpdate(analysis_results=results, metrics=metrics),
            errors=errors,
        )

    def _skipped(self, context: AgentContext, warning: str, started: float) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            status=AnalysisStatus.SKIPPED,
            update=AgentUpdate(
                analysis_results=[],
                metrics=context.metrics.model_copy(
                    update={"tool_calls": 0, "analytics_time": perf_counter() - started}
                ),
            ),
            warnings=[warning],
        )

    def _failed_structurally(
        self, context: AgentContext, errors: list[str], started: float
    ) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            status=AnalysisStatus.FAILED,
            update=AgentUpdate(
                analysis_results=[],
                metrics=context.metrics.model_copy(
                    update={"tool_calls": 0, "analytics_time": perf_counter() - started}
                ),
            ),
            errors=errors,
        )


def _validate_plan(plan: AnalysisPlan, context: AgentContext) -> list[str]:
    errors: list[str] = []
    if context.dataset_id is None:
        errors.append("Analysis requires a context dataset id.")
    if (
        context.dataset_profile is not None
        and context.dataset_id != context.dataset_profile.dataset_id
    ):
        errors.append("Analysis context has inconsistent dataset identifiers.")
    step_ids = [step.step_id for step in plan.steps]
    if len(set(step_ids)) != len(step_ids):
        errors.append("Analysis plan contains duplicate step ids.")
    hypothesis_id_list = [hypothesis.hypothesis_id for hypothesis in plan.hypotheses]
    if len(set(hypothesis_id_list)) != len(hypothesis_id_list):
        errors.append("Analysis plan contains duplicate hypothesis ids.")
    hypothesis_ids = set(hypothesis_id_list)
    if len(plan.hypotheses) > context.configuration.analysis.max_hypotheses:
        errors.append("Analysis plan exceeds the configured hypothesis limit.")
    for step in plan.steps:
        if step.hypothesis_id is not None and step.hypothesis_id not in hypothesis_ids:
            errors.append(f"{step.step_id}: references an unknown hypothesis.")
        if context.dataset_id is not None and step.request.dataset_id != context.dataset_id:
            errors.append(f"{step.step_id}: request dataset id does not match the context.")
        for dependency in step.depends_on:
            if dependency not in set(step_ids):
                errors.append(f"{step.step_id}: dependency '{dependency}' does not exist.")
    if not errors and _has_cycle(plan.steps):
        errors.append("Analysis plan contains circular step dependencies.")
    return errors


def _has_cycle(steps: list[AnalysisStep]) -> bool:
    return len(_topological_steps(steps)) != len(steps)


def _topological_steps(steps: list[AnalysisStep]) -> list[AnalysisStep]:
    by_id = {step.step_id: step for step in steps}
    dependents: dict[str, list[str]] = {step.step_id: [] for step in steps}
    remaining = {step.step_id: len(step.depends_on) for step in steps}
    for step in steps:
        for dependency in step.depends_on:
            if dependency in dependents:
                dependents[dependency].append(step.step_id)
    ready = deque(step.step_id for step in steps if remaining[step.step_id] == 0)
    ordered: list[AnalysisStep] = []
    while ready:
        step_id = ready.popleft()
        ordered.append(by_id[step_id])
        for dependent in dependents[step_id]:
            remaining[dependent] -= 1
            if remaining[dependent] == 0:
                ready.append(dependent)
    return ordered


def _failed_step(step: AnalysisStep, warning: str) -> AnalysisResult:
    return AnalysisResult(
        method=step.request.method,
        variables=step.request.variables,
        status=AnalysisStatus.FAILED,
        warnings=[warning],
    )


def _skipped_step(step: AnalysisStep, warning: str) -> AnalysisResult:
    return AnalysisResult(
        method=step.request.method,
        variables=step.request.variables,
        status=AnalysisStatus.SKIPPED,
        warnings=[warning],
    )


def _with_trace(result: AnalysisResult, step: AnalysisStep) -> AnalysisResult:
    trace = {"step_id": step.step_id}
    if step.hypothesis_id is not None:
        trace["hypothesis_id"] = step.hypothesis_id
    return result.model_copy(update={"metadata": result.metadata | trace})
