from pydantic import Field

from app.shared.domain.models.base import DomainModel


class Evidence(DomainModel):
    evidence_id: str
    analysis_id: str
    description: str
    limitations: list[str] = Field(default_factory=list)


class RelationshipAssessment(DomainModel):
    variables: list[str]
    evidence_ids: list[str] = Field(default_factory=list)
    potentially_spurious: bool | None = None
    rationale: str | None = None
    limitations: list[str] = Field(default_factory=list)
