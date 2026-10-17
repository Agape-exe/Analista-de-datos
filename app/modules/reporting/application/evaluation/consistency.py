from pydantic import Field

from app.shared.domain.models.base import DomainModel
from app.shared.domain.models.metrics import ExperimentMetrics


class ConsistencyRun(DomainModel):
    consistency_id: str
    benchmark_id: str
    experiment_ids: list[str] = Field(default_factory=list)
    repetitions: int = Field(ge=1)
    metrics: ExperimentMetrics = Field(default_factory=ExperimentMetrics)
    decision_coverage: float | None = Field(default=None, ge=0, le=1)
    abstention_agreement: float | None = Field(default=None, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


def conclusion_agreement(reports):
    """Pairwise exact decisions on a fixed universe; abstention agreement is separate."""
    from itertools import combinations

    from app.modules.reporting.application.evaluation.classification import pair_key

    if len(reports) < 2:
        raise ValueError("At least two reports are required")
    mappings = []
    for report in reports:
        mapping = {}
        for item in report.relationship_assessments:
            key = pair_key(item.variables)
            if key in mapping:
                raise ValueError("Duplicate relationship assessment")
            mapping[key] = item.potentially_spurious
        mappings.append(mapping)
    universe = set(mappings[0])
    if any(set(mapping) != universe for mapping in mappings):
        raise ValueError("Consistency runs must assess the same pairs")
    if not universe:
        return {
            "conclusion_agreement": None,
            "decision_coverage": 0.0,
            "abstention_agreement": None,
        }
    slots = list(combinations(mappings, 2))
    decided = matches = abstention_matches = 0
    for left, right in slots:
        for key in universe:
            a, b = left[key], right[key]
            abstention_matches += a is None and b is None
            if a is not None and b is not None:
                decided += 1
                matches += a == b
    total = len(slots) * len(universe)
    return {
        "conclusion_agreement": matches / decided if decided else None,
        "decision_coverage": decided / total,
        "abstention_agreement": abstention_matches / total,
    }
