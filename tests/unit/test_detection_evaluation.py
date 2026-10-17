import pytest

from app.modules.reporting.application.evaluation.classification import (
    RelationshipLabel,
    evaluate_detection,
)
from app.modules.reporting.application.evaluation.consistency import conclusion_agreement
from app.modules.reporting.application.evaluation.rubric import (
    HumanInsightEvaluation,
    default_rubric,
)
from app.shared.domain.models.evidence import RelationshipAssessment
from app.shared.domain.models.report import AnalysisReport


def test_detection_confusion_matrix_and_coverage():
    labels = [
        RelationshipLabel(variables=["a", "b"], potentially_spurious=True),
        RelationshipLabel(variables=["c", "d"], potentially_spurious=False),
        RelationshipLabel(variables=["e", "f"], potentially_spurious=True),
    ]
    predictions = [
        RelationshipAssessment(variables=["b", "a"], potentially_spurious=True),
        RelationshipAssessment(variables=["d", "c"], potentially_spurious=True),
    ]
    score = evaluate_detection(labels, predictions)
    assert (score.true_positives, score.false_positives, score.false_negatives) == (1, 1, 1)
    assert score.coverage == pytest.approx(2 / 3)
    assert score.abstentions_or_missing == 1
    assert score.metrics.precision == score.metrics.recall == score.metrics.f1_score == 0.5


def test_unknown_duplicates_and_missing_ground_truth_rejected():
    label = RelationshipLabel(variables=["a", "b"], potentially_spurious=True)
    for labels, predictions in [
        ([], []),
        ([label, label], []),
        ([label], [RelationshipAssessment(variables=["c", "d"], potentially_spurious=True)]),
    ]:
        with pytest.raises(ValueError):
            evaluate_detection(labels, predictions)
    score = evaluate_detection([label], [])
    assert score.metrics.precision is None
    assert score.metrics.recall == score.metrics.f1_score == 0
    assert score.coverage == 0


def test_consistency_does_not_confuse_abstention_with_agreement():
    def report(decision):
        return AnalysisReport(
            run_id="x",
            status="SUCCESS",
            relationship_assessments=[
                RelationshipAssessment(variables=["a", "b"], potentially_spurious=decision)
            ],
        )

    assert conclusion_agreement([report(True), report(False)])["conclusion_agreement"] == 0
    unknown = conclusion_agreement([report(None), report(None)])
    assert unknown["conclusion_agreement"] is None
    assert unknown["decision_coverage"] == 0
    assert unknown["abstention_agreement"] == 1


def test_rubric_requires_six_justified_scores():
    rubric = default_rubric()
    ratings = [
        {"criterion": c.name, "score": 4, "justification": "Fixture justification"}
        for c in rubric.criteria
    ]
    value = HumanInsightEvaluation(
        evaluator_id="reviewer", run_id="run", insight_id="insight", ratings=ratings
    )
    assert len(value.ratings) == 6
    with pytest.raises(ValueError):
        HumanInsightEvaluation(evaluator_id="x", run_id="y", insight_id="z", ratings=ratings[:1])
