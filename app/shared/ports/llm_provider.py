from typing import Protocol

from app.shared.contracts.llm import LLMRequest, LLMResponse


class LLMProvider(Protocol):
    """Provider-neutral reasoning over summarized analytical context."""

    async def generate(self, request: LLMRequest) -> LLMResponse: ...
