from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from time import perf_counter

from app.application.dto.llm import LLMRequest, LLMResponse
from app.domain.models.analysis import AnalysisResult, ToolRequest
from app.ports.analytics_tool import AnalyticsTool
from app.ports.llm_provider import LLMProvider


@dataclass
class RunTelemetry:
    llm_calls: int = 0
    tool_calls: int = 0
    failed_llm_calls: int = 0
    failed_tool_calls: int = 0
    tokens_used: int = 0
    missing_token_usage: bool = False
    events: list[dict] = field(default_factory=list)


_active: ContextVar[RunTelemetry | None] = ContextVar("analysis_telemetry", default=None)


@contextmanager
def telemetry_scope():
    collector = RunTelemetry()
    token = _active.set(collector)
    try:
        yield collector
    finally:
        _active.reset(token)


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
            collector.events.append(
                {"kind": "llm", "status": status, "duration_seconds": perf_counter() - started}
            )


class InstrumentedAnalyticsTool:
    def __init__(self, tool: AnalyticsTool) -> None:
        self.tool = tool
        self.name = tool.name

    def supports(self, request: ToolRequest) -> bool:
        return self.tool.supports(request)

    async def execute(self, request: ToolRequest) -> AnalysisResult:
        collector = _active.get()
        if collector is None:
            return await self.tool.execute(request)
        collector.tool_calls += 1
        started = perf_counter()
        status = "FAILED"
        try:
            result = await self.tool.execute(request)
            status = result.status
            if status != "SUCCESS":
                collector.failed_tool_calls += 1
            return result
        except BaseException:
            collector.failed_tool_calls += 1
            raise
        finally:
            collector.events.append(
                {
                    "kind": "tool",
                    "method": self.name,
                    "status": str(status),
                    "duration_seconds": perf_counter() - started,
                }
            )
