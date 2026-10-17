from datetime import UTC, datetime
from uuid import uuid4

from pydantic import Field, JsonValue

from app.modules.reporting.application.evaluation.classification import RelationshipLabel
from app.shared.contracts.analysis_input import AnalysisInput
from app.shared.domain.models.analysis import Hypothesis
from app.shared.domain.models.base import DomainModel
from app.shared.domain.models.metrics import ExperimentMetrics
from app.shared.domain.models.report import AnalysisReport


class GroundTruth(DomainModel):
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    expected_patterns: list[str] = Field(default_factory=list)
    spurious_relationships: list[list[str]] = Field(default_factory=list)
    notes: str | None = None
    relationship_labels: list[RelationshipLabel] = Field(default_factory=list)


class BenchmarkDataset(DomainModel):
    benchmark_id: str
    name: str
    input: AnalysisInput
    ground_truth: GroundTruth | None = None


class ExperimentRun(DomainModel):
    experiment_id: str = Field(default_factory=lambda: str(uuid4()))
    benchmark_id: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    configuration: dict[str, JsonValue] = Field(default_factory=dict)
    report: AnalysisReport | None = None
    metrics: ExperimentMetrics = Field(default_factory=ExperimentMetrics)
