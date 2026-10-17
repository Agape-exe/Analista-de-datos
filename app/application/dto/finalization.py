from pydantic import Field

from app.domain.models.analysis import AnalysisResult
from app.domain.models.base import DomainModel
from app.domain.models.data_dictionary import DataDictionary
from app.domain.models.dataset import DatasetProfile
from app.domain.models.evidence import Evidence, RelationshipAssessment
from app.domain.models.metrics import ExperimentMetrics


class FinalizationInput(DomainModel):
    """Boundary for integrating completed analytical outputs without rerunning other agents."""

    run_id: str = Field(min_length=1)
    user_question: str | None = None
    analysis_results: list[AnalysisResult] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    relationship_assessments: list[RelationshipAssessment] = Field(default_factory=list)
    dataset_profile: DatasetProfile | None = None
    data_dictionary: DataDictionary | None = None
    metrics: ExperimentMetrics = Field(default_factory=ExperimentMetrics)
    warnings: list[str] = Field(default_factory=list)
