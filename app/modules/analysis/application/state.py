from typing import TypedDict

from app.shared.contracts.analysis_input import AnalysisInput, EffectiveConfiguration
from app.shared.domain.enums.statuses import AnalysisStatus
from app.shared.domain.models.analysis import AnalysisPlan, AnalysisResult, AssociationResult
from app.shared.domain.models.data_dictionary import DataDictionary
from app.shared.domain.models.dataset import DatasetProfile
from app.shared.domain.models.evidence import Evidence, RelationshipAssessment
from app.shared.domain.models.insight import Insight
from app.shared.domain.models.metrics import ExperimentMetrics


class AgentState(TypedDict):
    """Workflow-owned message state, never a shared data store for agents."""

    started_monotonic: float
    run_id: str
    input: AnalysisInput
    configuration: EffectiveConfiguration
    dataset_id: str | None
    dataset_profile: DatasetProfile | None
    data_dictionary: DataDictionary | None
    associations: list[AssociationResult]
    analysis_plan: AnalysisPlan | None
    analysis_results: list[AnalysisResult]
    evidence: list[Evidence]
    relationship_assessments: list[RelationshipAssessment]
    insights: list[Insight]
    metrics: ExperimentMetrics
    errors: list[str]
    warnings: list[str]
    stage_statuses: dict[str, AnalysisStatus]
    stage_durations: dict[str, float]
    iterations: int
