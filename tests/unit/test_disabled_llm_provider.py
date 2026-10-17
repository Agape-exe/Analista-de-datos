import pytest

from app.shared.adapters.llm.disabled import DisabledLLMProvider
from app.shared.application.errors import LLMDisabledError
from app.shared.contracts.llm import LLMRequest


async def test_disabled_provider_fails_explicitly() -> None:
    with pytest.raises(LLMDisabledError, match="disabled"):
        await DisabledLLMProvider().generate(LLMRequest(run_id="test", instructions="Explain"))
