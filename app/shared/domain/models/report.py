from pydantic import Field, JsonValue

from app.shared.domain.enums.statuses import AnalysisStatus
from app.shared.domain.models.analysis import AnalysisPlan, AnalysisResult, AssociationResult
from app.shared.domain.models.base import DomainModel
from app.shared.domain.models.data_dictionary import DataDictionary
from app.shared.domain.models.dataset import DatasetProfile
from app.shared.domain.models.evidence import Evidence, RelationshipAssessment
from app.shared.domain.models.insight import Insight
from app.shared.domain.models.metrics import Duration, ExperimentMetrics


class AnalysisReport(DomainModel):
    run_id: str
    status: AnalysisStatus
    dataset_profile: DatasetProfile | None = None
    data_dictionary: DataDictionary | None = None
    analysis_results: list[AnalysisResult] = Field(default_factory=list)
    insights: list[Insight] = Field(default_factory=list)
    metrics: ExperimentMetrics = Field(default_factory=ExperimentMetrics)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    stage_statuses: dict[str, AnalysisStatus] = Field(default_factory=dict)
    stage_durations: dict[str, Duration] = Field(default_factory=dict)

    evidence: list[Evidence] = Field(default_factory=list)
    relationship_assessments: list[RelationshipAssessment] = Field(default_factory=list)
    configuration: dict[str, JsonValue] = Field(default_factory=dict)
    execution_trace: list[dict[str, JsonValue]] = Field(default_factory=list)
    audit_version: str | None = None
    user_question: str | None = None
    dataset_id: str | None = None
    analysis_plan: AnalysisPlan | None = None
    screening_candidates: list[AssociationResult] = Field(default_factory=list)
    requested_configuration: dict[str, JsonValue] = Field(default_factory=dict)
    capabilities: dict[str, bool] = Field(default_factory=dict)
    planning_decisions: list[dict[str, JsonValue]] = Field(default_factory=list)
    screening_configuration: dict[str, JsonValue] = Field(default_factory=dict)
    screening_summary: dict[str, JsonValue] = Field(default_factory=dict)
