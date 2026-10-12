from pydantic import Field

from app.domain.models.base import DomainModel
from app.domain.models.metrics import ExperimentMetrics


class ConsistencyRun(DomainModel):
    consistency_id: str
    benchmark_id: str
    experiment_ids: list[str] = Field(default_factory=list)
    repetitions: int = Field(ge=1)
    metrics: ExperimentMetrics = Field(default_factory=ExperimentMetrics)
