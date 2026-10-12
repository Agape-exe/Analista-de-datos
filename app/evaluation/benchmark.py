from datetime import UTC, datetime
from uuid import uuid4

from pydantic import Field

from app.application.dto.analysis_input import AnalysisInput
from app.domain.models.analysis import Hypothesis
from app.domain.models.base import DomainModel
from app.domain.models.metrics import ExperimentMetrics
from app.domain.models.report import AnalysisReport


class GroundTruth(DomainModel):
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    expected_patterns: list[str] = Field(default_factory=list)
    spurious_relationships: list[list[str]] = Field(default_factory=list)
    notes: str | None = None


class BenchmarkDataset(DomainModel):
    benchmark_id: str
    name: str
    input: AnalysisInput
    ground_truth: GroundTruth | None = None


class ExperimentRun(DomainModel):
    experiment_id: str = Field(default_factory=lambda: str(uuid4()))
    benchmark_id: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    configuration: dict[str, str] = Field(default_factory=dict)
    report: AnalysisReport | None = None
    metrics: ExperimentMetrics = Field(default_factory=ExperimentMetrics)
