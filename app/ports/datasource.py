from typing import Protocol

from app.application.dto.analysis_input import SourceSpec
from app.application.dto.datasource import LoadedDataset


class DataSource(Protocol):
    """Read data locally without exposing raw rows to agents."""

    async def read(self, source: SourceSpec) -> LoadedDataset: ...
