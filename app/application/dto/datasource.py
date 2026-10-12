from dataclasses import dataclass
from typing import Protocol

from app.domain.models.dataset import DatasetSchema


class LocalTable(Protocol):
    """Local-only column access for future deterministic tools."""

    def column(self, name: str) -> list[object]: ...


@dataclass(frozen=True)
class LoadedDataset:
    """Non-serializable local data, excluded from agents and LLM requests."""

    dataset_id: str
    schema: DatasetSchema
    row_count: int
    table: LocalTable
