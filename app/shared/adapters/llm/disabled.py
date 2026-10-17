from app.shared.application.errors import LLMDisabledError
from app.shared.contracts.llm import LLMRequest, LLMResponse


class DisabledLLMProvider:
    """Explicit failure instead of a fabricated language-model response."""

    async def generate(self, request: LLMRequest) -> LLMResponse:
        raise LLMDisabledError(
            "LLM provider is disabled. "
            "Configure and inject an LLMProvider adapter before reasoning."
        )
