from typing import Literal
from uuid import uuid4

from pydantic import Field, JsonValue, model_validator

from app.shared.domain.enums.statuses import AnalysisStatus
from app.shared.domain.models.base import DomainModel


class AssociationResult(DomainModel):
    method: str
    variables: list[str]
    strength: float | None = None
    p_value: float | None = Field(default=None, ge=0, le=1)


class RankedRelationship(DomainModel):
    """Candidate relationship from screening; the Critic decides if it is meaningful."""

    x: str
    y: str
    method: str
    score: float = Field(ge=0, le=1)
    strength: float | None = None
    p_value: float | None = Field(default=None, ge=0, le=1)
    adjusted_p_value: float | None = Field(default=None, ge=0, le=1)
    sample_size: int = Field(ge=0)
    supporting: list[AssociationResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class Hypothesis(DomainModel):
    hypothesis_id: str = Field(default_factory=lambda: str(uuid4()))
    statement: str
    variables: list[str] = Field(default_factory=list)


class ToolRequest(DomainModel):
    dataset_id: str
    method: str = Field(min_length=1)
    variables: list[str] = Field(default_factory=list)
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    step_id: str | None = None
    hypothesis_id: str | None = None


class AnalysisStep(DomainModel):
    step_id: str
    hypothesis_id: str | None = None
    request: ToolRequest
    depends_on: list[str] = Field(default_factory=list)


class AnalysisPlan(DomainModel):
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    steps: list[AnalysisStep] = Field(default_factory=list)
    policy_version: str = "deterministic-v2"
    decisions: list[dict[str, JsonValue]] = Field(default_factory=list)


class ColumnResult(DomainModel):
    """Per-column outcome; unsuccessful columns never carry calculated values."""

    status: Literal["SUCCESS", "SKIPPED", "FAILED"]
    result: JsonValue = None
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_outcome(self) -> "ColumnResult":
        if self.status != "SUCCESS" and self.result is not None:
            raise ValueError("Unsuccessful columns cannot contain calculated results")
        return self


class AnalysisResult(DomainModel):
    analysis_id: str = Field(default_factory=lambda: str(uuid4()))
    method: str
    variables: list[str] = Field(default_factory=list)
    status: AnalysisStatus
    result: JsonValue = None
    p_value: float | None = Field(default=None, ge=0, le=1)
    effect_size: float | None = None
    sample_size: int | None = Field(default=None, ge=0)
    warnings: list[str] = Field(default_factory=list)
    execution_time: float = Field(default=0, ge=0)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    completeness: Literal["complete", "partial"] = "complete"
    column_results: dict[str, ColumnResult] = Field(default_factory=dict)

    @model_validator(mode="after")
    def no_unexecuted_statistics(self) -> "AnalysisResult":
        if self.status != AnalysisStatus.SUCCESS and any(
            value is not None for value in (self.result, self.p_value, self.effect_size)
        ):
            raise ValueError("Unsuccessful analyses cannot contain calculated results")
        successes = [item for item in self.column_results.values() if item.status == "SUCCESS"]
        if self.status == AnalysisStatus.SUCCESS and self.column_results and not successes:
            raise ValueError("Successful column-wise results need a successful column")
        if self.status != AnalysisStatus.SUCCESS and successes:
            raise ValueError("Successful columns require a successful partial or complete result")
        if (
            self.status == AnalysisStatus.SUCCESS
            and successes
            and len(successes) < len(self.column_results)
            and self.completeness != "partial"
        ):
            raise ValueError("Mixed column outcomes must be marked partial")
        if self.completeness == "partial" and (
            self.status != AnalysisStatus.SUCCESS
            or not successes
            or len(successes) == len(self.column_results)
        ):
            raise ValueError("Partial results require both successful and unsuccessful columns")
        return self
