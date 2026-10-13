from pydantic import Field

from app.domain.enums.statuses import AnalysisStatus
from app.domain.models.analysis import AnalysisResult
from app.domain.models.base import DomainModel
from app.domain.models.data_dictionary import DataDictionary
from app.domain.models.dataset import DatasetProfile
from app.domain.models.insight import Insight
from app.domain.models.metrics import Duration, ExperimentMetrics


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
