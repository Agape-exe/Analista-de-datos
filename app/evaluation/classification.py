from pydantic import Field, model_validator

from app.domain.models.base import DomainModel
from app.domain.models.evidence import RelationshipAssessment
from app.domain.models.metrics import ExperimentMetrics


def pair_key(variables: list[str]) -> tuple[str, str]:
    if len(variables) != 2 or variables[0] == variables[1] or any(not v for v in variables):
        raise ValueError("Evaluation requires two distinct named variables")
    return tuple(sorted(variables))


class RelationshipLabel(DomainModel):
    variables: list[str]
    potentially_spurious: bool

    @model_validator(mode="after")
    def valid_pair(self):
        pair_key(self.variables)
        return self


class DetectionScore(DomainModel):
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    expected_pairs: int
    classified_pairs: int
    abstentions_or_missing: int
    coverage: float = Field(ge=0, le=1)
    metrics: ExperimentMetrics


def evaluate_detection(
    labels: list[RelationshipLabel], predictions: list[RelationshipAssessment]
) -> DetectionScore:
    """Binary detection: unclassified pairs are not detected, with coverage reported."""
    truth = {}
    for label in labels:
        key = pair_key(label.variables)
        if key in truth:
            raise ValueError("Duplicate ground truth pair")
        truth[key] = label.potentially_spurious
    if not truth:
        raise ValueError("Ground truth must define an explicit nonempty evaluation universe")
    predicted = {}
    for value in predictions:
        key = pair_key(value.variables)
        if key not in truth or key in predicted:
            raise ValueError("Unknown or duplicate prediction pair")
        predicted[key] = value.potentially_spurious
    tp = fp = fn = tn = classified = 0
    for key, actual in truth.items():
        decision = predicted.get(key)
        classified += decision is not None
        detected = decision is True
        tp += actual and detected
        fp += not actual and detected
        fn += actual and not detected
        tn += not actual and not detected
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None
    return DetectionScore(
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        true_negatives=tn,
        expected_pairs=len(truth),
        classified_pairs=classified,
        abstentions_or_missing=len(truth) - classified,
        coverage=classified / len(truth),
        metrics=ExperimentMetrics(
            precision=precision,
            recall=recall,
            f1_score=f1,
            false_positive_rate=fp / (fp + tn) if fp + tn else None,
        ),
    )
