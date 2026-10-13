from typing import Literal

from pydantic import Field, model_validator

from app.domain.enums.statuses import DictionarySource
from app.domain.models.base import DomainModel


class DataDictionaryEntry(DomainModel):
    column_name: str = Field(min_length=1)
    description: str | None = None
    data_type: str | None = None
    semantic_type: str | None = None
    unit: str | None = None
    source: DictionarySource
    confidence: float | None = Field(default=None, ge=0, le=1)
    inferred_fields: list[Literal["description", "data_type", "semantic_type"]] = Field(
        default_factory=list
    )
    inference_reason: str | None = None


class DataDictionary(DomainModel):
    entries: list[DataDictionaryEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_columns(self) -> "DataDictionary":
        names = [entry.column_name for entry in self.entries]
        if len(names) != len(set(names)):
            raise ValueError("Data dictionary column names must be unique")
        return self
