from app.application.dto.llm import LLMRequest, LLMResponse
from app.application.errors import LLMDisabledError


class DisabledLLMProvider:
    """Explicit failure instead of a fabricated language-model response."""

    async def generate(self, request: LLMRequest) -> LLMResponse:
        raise LLMDisabledError(
            "LLM provider is disabled. "
            "Configure and inject an LLMProvider adapter before reasoning."
        )
