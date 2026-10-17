from dataclasses import dataclass
from typing import Protocol

from app.shared.domain.enums.semantic_type import SemanticType
from app.shared.domain.models.data_dictionary import DataDictionary
from app.shared.domain.models.dataset import DatasetProfile, DatasetSchema


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


@dataclass(frozen=True)
class RegisteredDataset:
    """Local data plus its understood profile, resolved by tools through dataset_id.

    The dictionary and warnings let a later analysis reuse intake without re-profiling.
    """

    dataset: LoadedDataset
    profile: DatasetProfile
    data_dictionary: DataDictionary | None = None
    warnings: tuple[str, ...] = ()

    @property
    def dataset_id(self) -> str:
        return self.dataset.dataset_id

    def has_column(self, name: str) -> bool:
        return any(column.column_name == name for column in self.profile.columns)

    def semantic_type(self, name: str) -> SemanticType:
        for column in self.profile.columns:
            if column.column_name == name:
                return column.semantic_type or SemanticType.UNKNOWN
        raise KeyError(name)

    def columns_of_type(self, *semantic_types: SemanticType) -> list[str]:
        return [
            column.column_name
            for column in self.profile.columns
            if column.semantic_type in semantic_types
        ]

    def values(self, name: str) -> list[object]:
        return self.dataset.table.column(name)
