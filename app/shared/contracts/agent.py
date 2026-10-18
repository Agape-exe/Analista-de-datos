from pydantic import Field, JsonValue

from app.shared.contracts.analysis_input import AnalysisInput, EffectiveConfiguration
from app.shared.domain.enums.statuses import AnalysisStatus
from app.shared.domain.models.analysis import AnalysisPlan, AnalysisResult, AssociationResult
from app.shared.domain.models.base import DomainModel
from app.shared.domain.models.data_dictionary import DataDictionary
from app.shared.domain.models.dataset import DatasetProfile
from app.shared.domain.models.evidence import Evidence, RelationshipAssessment
from app.shared.domain.models.insight import Insight
from app.shared.domain.models.metrics import ExperimentMetrics


class AgentContext(DomainModel):
    """Explicit summarized input; contains no local table or persistence session."""

    run_id: str
    input: AnalysisInput
    configuration: EffectiveConfiguration
    dataset_id: str | None = None
    dataset_profile: DatasetProfile | None = None
    data_dictionary: DataDictionary | None = None
    associations: list[AssociationResult] = Field(default_factory=list)
    screening_summary: dict[str, JsonValue] = Field(default_factory=dict)
    analysis_plan: AnalysisPlan | None = None
    planning_decisions: list[dict[str, JsonValue]] = Field(default_factory=list)
    analysis_results: list[AnalysisResult] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    relationship_assessments: list[RelationshipAssessment] = Field(default_factory=list)
    insights: list[Insight] = Field(default_factory=list)
    metrics: ExperimentMetrics = Field(default_factory=ExperimentMetrics)


class AgentUpdate(DomainModel):
    """Only explicitly set fields are applied to the orchestration state."""

    dataset_id: str | None = None
    dataset_profile: DatasetProfile | None = None
    data_dictionary: DataDictionary | None = None
    associations: list[AssociationResult] | None = None
    screening_summary: dict[str, JsonValue] | None = None
    analysis_plan: AnalysisPlan | None = None
    planning_decisions: list[dict[str, JsonValue]] | None = None
    analysis_results: list[AnalysisResult] | None = None
    evidence: list[Evidence] | None = None
    relationship_assessments: list[RelationshipAssessment] | None = None
    insights: list[Insight] | None = None
    metrics: ExperimentMetrics | None = None


class AgentResult(DomainModel):
    agent_name: str
    status: AnalysisStatus
    update: AgentUpdate = Field(default_factory=AgentUpdate)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
