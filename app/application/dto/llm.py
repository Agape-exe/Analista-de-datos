from pydantic import Field, JsonValue

from app.domain.models.base import DomainModel


class LLMRequest(DomainModel):
    """Instructions and aggregate context only; never raw table rows."""

    run_id: str
    instructions: str
    summary: dict[str, JsonValue] = Field(default_factory=dict)


class LLMResponse(DomainModel):
    content: str
    tokens_used: int | None = Field(default=None, ge=0)
