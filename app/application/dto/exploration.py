from pydantic import Field, JsonValue

from app.domain.models.base import DomainModel


class ToolRunRequest(DomainModel):
    """HTTP body for running one deterministic tool on an intake dataset."""

    variables: list[str] = Field(default_factory=list)
    parameters: dict[str, JsonValue] = Field(default_factory=dict)


class ToolCatalog(DomainModel):
    tools: list[str]
