import pytest

from app.adapters.llm.disabled import DisabledLLMProvider
from app.application.dto.llm import LLMRequest
from app.application.errors import LLMDisabledError


async def test_disabled_provider_fails_explicitly() -> None:
    with pytest.raises(LLMDisabledError, match="disabled"):
        await DisabledLLMProvider().generate(LLMRequest(run_id="test", instructions="Explain"))
