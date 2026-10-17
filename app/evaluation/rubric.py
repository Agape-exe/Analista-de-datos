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


class CriterionRating(DomainModel):
    criterion: str
    score: int = Field(ge=1, le=5)
    justification: str = Field(min_length=1)


class HumanInsightEvaluation(DomainModel):
    evaluator_id: str
    run_id: str
    insight_id: str
    rubric_version: str = "1"
    ratings: list[CriterionRating]

    @model_validator(mode="after")
    def complete_rubric(self):
        expected = {
            "correctitud",
            "relevancia",
            "claridad",
            "evidencia",
            "utilidad",
            "prudencia_causal",
        }
        names = [item.criterion for item in self.ratings]
        if set(names) != expected or len(names) != len(expected):
            raise ValueError("Provide each of the six rubric criteria once")
        return self


def default_rubric() -> HumanEvaluationRubric:
    descriptions = {
        "correctitud": "1 contradice datos; 3 impreciso; 5 reproduce resultados y límites.",
        "relevancia": "1 ajeno a la pregunta; 3 parcialmente relevante; 5 responde al objetivo.",
        "claridad": "1 incomprensible; 3 requiere aclaraciones; 5 comprensible y preciso.",
        "evidencia": "1 sin soporte; 3 soporte incompleto; 5 evidencia enlazada y verificable.",
        "utilidad": "1 no orienta; 3 utilidad parcial; 5 orienta una acción o análisis razonable.",
        "prudencia_causal": "1 causalidad sin soporte; 3 ambiguo; 5 distingue asociación de causa.",
    }
    return HumanEvaluationRubric(
        rubric_id="insights",
        version="1",
        criteria=[
            RubricCriterion(name=name, description=description, minimum_score=1, maximum_score=5)
            for name, description in descriptions.items()
        ],
        instructions="Justificar cada puntuación con evidencia; 2 y 4 son niveles intermedios.",
    )
