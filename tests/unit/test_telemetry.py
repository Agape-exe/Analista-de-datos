import asyncio

from app.application.dto.llm import LLMRequest, LLMResponse
from app.observability.telemetry import InstrumentedLLMProvider, telemetry_scope


class Provider:
    async def generate(self, request):
        await asyncio.sleep(0)
        if request.instructions == "fail":
            raise RuntimeError("fixture failure")
        return LLMResponse(
            content="ok", tokens_used=None if request.instructions == "unknown" else 4
        )


async def test_parallel_runs_do_not_share_metrics_and_failed_calls_count():
    provider = InstrumentedLLMProvider(Provider())

    async def run(instructions):
        with telemetry_scope() as recorder:
            for text in instructions:
                try:
                    await provider.generate(LLMRequest(run_id="test", instructions=text))
                except RuntimeError:
                    pass
            return recorder

    first, second = await asyncio.gather(run(["ok", "fail"]), run(["unknown"]))
    assert first.llm_calls == 2
    assert first.failed_llm_calls == 1
    assert first.tokens_used == 4
    assert first.missing_token_usage
    assert second.llm_calls == 1
    assert second.missing_token_usage
    assert len(first.events) == 2
