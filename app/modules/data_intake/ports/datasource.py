from typing import Protocol

from app.shared.contracts.analysis_input import SourceSpec
from app.shared.contracts.datasource import LoadedDataset


class DataSource(Protocol):
    """Read data locally without exposing raw rows to agents."""

    async def read(self, source: SourceSpec) -> LoadedDataset: ...
