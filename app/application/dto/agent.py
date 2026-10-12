from pydantic import Field

from app.application.dto.analysis_input import AnalysisInput, EffectiveConfiguration
from app.domain.enums.statuses import AnalysisStatus
from app.domain.models.analysis import AnalysisPlan, AnalysisResult, AssociationResult
from app.domain.models.base import DomainModel
from app.domain.models.data_dictionary import DataDictionary
from app.domain.models.dataset import DatasetProfile
from app.domain.models.evidence import Evidence, RelationshipAssessment
from app.domain.models.insight import Insight
from app.domain.models.metrics import ExperimentMetrics


class AgentContext(DomainModel):
    """Explicit summarized input; contains no local table or persistence session."""

    run_id: str
    input: AnalysisInput
    configuration: EffectiveConfiguration
    dataset_id: str | None = None
    dataset_profile: DatasetProfile | None = None
    data_dictionary: DataDictionary | None = None
    associations: list[AssociationResult] = Field(default_factory=list)
    analysis_plan: AnalysisPlan | None = None
    analysis_results: list[AnalysisResult] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    relationship_assessments: list[RelationshipAssessment] = Field(default_factory=list)
    insights: list[Insight] = Field(default_factory=list)
    metrics: ExperimentMetrics = Field(default_factory=ExperimentMetrics)


class AgentUpdate(DomainModel):
    """Only explicitly set fields are applied to the orchestration state."""

    dataset_profile: DatasetProfile | None = None
    data_dictionary: DataDictionary | None = None
    associations: list[AssociationResult] | None = None
    analysis_plan: AnalysisPlan | None = None
    analysis_results: list[AnalysisResult] | None = None
    evidence: list[Evidence] | None = None
    relationship_assessments: list[RelationshipAssessment] | None = None
    insights: list[Insight] | None = None


class AgentResult(DomainModel):
    agent_name: str
    status: AnalysisStatus
    update: AgentUpdate = Field(default_factory=AgentUpdate)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
