from typing import Protocol

from app.shared.domain.models.analysis import AnalysisResult
from app.shared.domain.models.dataset import DatasetProfile


class RelationshipScreening(Protocol):
    """Supply measured candidates without coupling agents to a statistical engine."""

    async def screen(
        self, dataset_id: str, profile: DatasetProfile, minimum_sample_size: int
    ) -> AnalysisResult: ...
