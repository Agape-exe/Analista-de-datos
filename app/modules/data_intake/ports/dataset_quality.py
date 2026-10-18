from typing import Protocol

from app.modules.data_intake.domain.quality import QualityCounts, QualityLimits
from app.shared.contracts.datasource import RegisteredDataset


class DatasetQualityReader(Protocol):
    """Read exact aggregate counts from registered local data without changing it."""

    async def measure(self, dataset: RegisteredDataset, limits: QualityLimits) -> QualityCounts: ...
