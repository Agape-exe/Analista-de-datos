from pydantic import Field

from app.domain.models.base import DomainModel


class Insight(DomainModel):
    insight_id: str
    statement: str
    evidence_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
