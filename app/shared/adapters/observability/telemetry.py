from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from time import perf_counter
from uuid import uuid4

from app.shared.contracts.llm import LLMRequest, LLMResponse
from app.shared.domain.models.analysis import AnalysisResult, ToolRequest
from app.shared.ports.analytics_tool import AnalyticsTool
from app.shared.ports.llm_provider import LLMProvider


@dataclass
class RunTelemetry:
    run_id: str | None = None
    llm_calls: int = 0
    tool_calls: int = 0
    screening_calls: int = 0
    failed_llm_calls: int = 0
    failed_tool_calls: int = 0
    tokens_used: int = 0
    missing_token_usage: bool = False
    events: list[dict] = field(default_factory=list)
    last_state: dict = field(default_factory=dict)
    results: list[AnalysisResult] = field(default_factory=list)

    def record(self, **event) -> None:
        self.events.append(
            {
                "event_id": str(uuid4()),
                "sequence": len(self.events) + 1,
                "run_id": self.run_id,
                **event,
            }
        )


_active: ContextVar[RunTelemetry | None] = ContextVar("analysis_telemetry", default=None)


@contextmanager
def telemetry_scope(run_id: str | None = None):
    collector = RunTelemetry(run_id=run_id)
    token = _active.set(collector)
    try:
        yield collector
    finally:
        _active.reset(token)


def active_telemetry() -> RunTelemetry | None:
    return _active.get()


class InstrumentedLLMProvider:
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    async def generate(self, request: LLMRequest) -> LLMResponse:
        collector = _active.get()
        if collector is None:
            return await self.provider.generate(request)
        collector.llm_calls += 1
        started = perf_counter()
        status = "FAILED"
        try:
            response = await self.provider.generate(request)
            if response.tokens_used is None:
                collector.missing_token_usage = True
            else:
                collector.tokens_used += response.tokens_used
            status = "SUCCESS"
            return response
        except BaseException:
            collector.failed_llm_calls += 1
            collector.missing_token_usage = True
            raise
        finally:
            collector.record(kind="llm", status=status, duration_seconds=perf_counter() - started)


class InstrumentedAnalyticsTool:
    def __init__(self, tool: AnalyticsTool, *, scope: str = "analysis") -> None:
        self.tool = tool
        self.name = tool.name
        self.scope = scope

    def supports(self, request: ToolRequest) -> bool:
        return self.tool.supports(request)

    async def execute(self, request: ToolRequest) -> AnalysisResult:
        collector = _active.get()
        if collector is None:
            return await self.tool.execute(request)
        if self.scope == "screening":
            collector.screening_calls += 1
        else:
            collector.tool_calls += 1
        started = perf_counter()
        status = "FAILED"
        result = None
        try:
            result = await self.tool.execute(request)
            status = result.status
            if self.scope == "analysis":
                collector.results.append(
                    result.model_copy(
                        update={
                            "metadata": result.metadata
                            | {
                                "step_id": request.step_id,
                                "hypothesis_id": request.hypothesis_id,
                            }
                        }
                    )
                )
            if status == "FAILED":
                collector.failed_tool_calls += 1
            return result
        except BaseException:
            collector.failed_tool_calls += 1
            raise
        finally:
            collector.record(
                kind="tool",
                scope=self.scope,
                agent="Association" if self.scope == "screening" else "Analysis",
                method=self.name,
                status=str(status),
                dataset_id=request.dataset_id,
                step_id=request.step_id,
                hypothesis_id=request.hypothesis_id,
                analysis_id=result.analysis_id if result is not None else None,
                warnings=result.warnings if result is not None else [],
                duration_seconds=perf_counter() - started,
            )
