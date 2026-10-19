import pytest

from app.modules.critical_review.application.services.screening_provenance import (
    extract_screening_provenance,
)
from app.shared.domain.enums.statuses import AnalysisStatus
from app.shared.domain.models.analysis import AnalysisResult


def test_preserves_statistical_provenance():
    """AUD-036: Conservar la procedencia del screening."""

    analysis = AnalysisResult(
        analysis_id="screening-001",
        method="relationship_ranking",
        status=AnalysisStatus.SUCCESS,
        result={
            "top_relationships": [
                {
                    "x": "publicidad",
                    "y": "ventas",
                    "method": "pearson",
                    "score": 0.85,
                    "strength": 0.85,
                    "p_value": 0.001,
                    "adjusted_p_value": 0.008,
                    "sample_size": 100,
                    "warnings": ["Posible influencia de outliers."],
                    "supporting": [
                        {
                            "method": "spearman",
                            "variables": ["publicidad", "ventas"],
                            "strength": 0.78,
                            "p_value": 0.002,
                        }
                    ],
                }
            ],
            "correction": "benjamini-hochberg",
            "significance_level": 0.05,
            "skipped_pairs": [
                {
                    "x": "edad",
                    "y": "ventas",
                    "reason": "Muestra insuficiente.",
                }
            ],
            "excluded_columns": {
                "codigo": "constant or empty column",
            },
        },
        warnings=["Screening exploratorio, no causal."],
    )

    provenance = extract_screening_provenance(analysis)

    assert provenance is not None
    assert provenance.analysis_id == "screening-001"
    assert provenance.correction == "benjamini-hochberg"
    assert provenance.significance_level == 0.05

    relationship = provenance.relationships[0]

    assert relationship.method == "pearson"
    assert relationship.sample_size == 100
    assert relationship.p_value == pytest.approx(0.001)
    assert relationship.adjusted_p_value == pytest.approx(0.008)
    assert relationship.warnings == ["Posible influencia de outliers."]

    assert len(relationship.supporting) == 1
    assert relationship.supporting[0].method == "spearman"
    assert relationship.supporting[0].strength == pytest.approx(0.78)

    assert provenance.skipped_pairs[0]["reason"] == "Muestra insuficiente."
    assert provenance.excluded_columns["codigo"] == "constant or empty column"
    assert provenance.warnings == ["Screening exploratorio, no causal."]


@pytest.mark.parametrize(
    ("method", "status", "payload"),
    [
        ("pearson", AnalysisStatus.SUCCESS, {}),
        ("relationship_ranking", AnalysisStatus.SKIPPED, None),
        ("relationship_ranking", AnalysisStatus.FAILED, None),
        ("relationship_ranking", AnalysisStatus.SUCCESS, {}),
    ],
)
def test_rejects_non_evaluable_screening(method, status, payload):
    """AUD-036: No fabricar procedencia de análisis no evaluables."""

    analysis = AnalysisResult(
        analysis_id="screening-invalid-001",
        method=method,
        status=status,
        result=payload,
    )

    provenance = extract_screening_provenance(analysis)

    assert provenance is None
