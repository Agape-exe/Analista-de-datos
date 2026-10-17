from pydantic import Field

from app.shared.domain.models.analysis import AnalysisResult
from app.shared.domain.models.base import DomainModel
from app.shared.domain.models.data_dictionary import DataDictionary
from app.shared.domain.models.dataset import DatasetProfile
from app.shared.domain.models.evidence import Evidence, RelationshipAssessment
from app.shared.domain.models.metrics import ExperimentMetrics


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
