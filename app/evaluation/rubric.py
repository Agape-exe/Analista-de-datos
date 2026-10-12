from pydantic import Field, model_validator

from app.domain.models.base import DomainModel


class RubricCriterion(DomainModel):
    name: str
    description: str
    minimum_score: int
    maximum_score: int

    @model_validator(mode="after")
    def valid_scale(self) -> "RubricCriterion":
        if self.maximum_score <= self.minimum_score:
            raise ValueError("Maximum rubric score must exceed minimum")
        return self


class HumanEvaluationRubric(DomainModel):
    rubric_id: str
    version: str
    criteria: list[RubricCriterion] = Field(default_factory=list)
    instructions: str | None = None
