from pydantic import Field, model_validator

from app.shared.domain.enums.semantic_type import SemanticType
from app.shared.domain.enums.statuses import DictionarySource
from app.shared.domain.models.base import DomainModel
from app.shared.domain.models.data_dictionary import DataDictionary


class ColumnSchema(DomainModel):
    name: str = Field(min_length=1)
    data_type: str
    nullable: bool = True


class DatasetSchema(DomainModel):
    columns: list[ColumnSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_columns(self) -> "DatasetSchema":
        names = [column.name for column in self.columns]
        if len(names) != len(set(names)):
            raise ValueError("Schema column names must be unique")
        return self


class ColumnProfile(DomainModel):
    column_name: str
    data_type: str
    semantic_type: SemanticType | None = None
    missing_count: int | None = Field(default=None, ge=0)
    unique_count: int | None = Field(default=None, ge=0)
    classification_source: DictionarySource | None = None
    classification_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)


class ProfilingOptions(DomainModel):
    """Explicit inference policy; runtime values are supplied by configuration."""

    identifier_name_tokens: list[str] = Field(min_length=1)
    identifier_unique_ratio: float = Field(gt=0, le=1)
    identifier_max_length: int = Field(ge=1)
    categorical_max_unique: int = Field(ge=1)
    categorical_unique_ratio: float = Field(gt=0, le=1)
    categorical_max_length: int = Field(ge=1)
    temporal_parse_ratio: float = Field(gt=0, le=1)
    temporal_formats: list[str] = Field(min_length=1)
    text_name_tokens: list[str] = Field(min_length=1)


class DatasetSummary(DomainModel):
    rows: int = Field(ge=0)
    columns: int = Field(ge=0)
    numeric_columns: list[str]
    categorical_columns: list[str]
    temporal_columns: list[str]
    identifiers: list[str]
    text_columns: list[str]
    unknown_columns: list[str]
    data_dictionary: DataDictionary


class DatasetProfile(DomainModel):
    dataset_id: str
    row_count: int = Field(ge=0)
    columns: list[ColumnProfile] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_columns(self) -> "DatasetProfile":
        names = [column.column_name for column in self.columns]
        if len(names) != len(set(names)):
            raise ValueError("Profile column names must be unique")
        for column in self.columns:
            missing = column.missing_count or 0
            if missing > self.row_count:
                raise ValueError("Missing count cannot exceed row count")
            if column.unique_count is not None and column.unique_count > self.row_count - missing:
                raise ValueError("Unique count cannot exceed observed row count")
        return self

    @property
    def column_count(self) -> int:
        return len(self.columns)

    def columns_of_type(self, semantic_type: SemanticType) -> list[str]:
        return [
            column.column_name for column in self.columns if column.semantic_type == semantic_type
        ]

    def summary(self, data_dictionary: DataDictionary) -> DatasetSummary:
        """Derive the public summary without duplicating classification state."""
        return DatasetSummary(
            rows=self.row_count,
            columns=self.column_count,
            numeric_columns=self.columns_of_type(SemanticType.NUMERIC),
            categorical_columns=self.columns_of_type(SemanticType.CATEGORICAL),
            temporal_columns=self.columns_of_type(SemanticType.TEMPORAL),
            identifiers=self.columns_of_type(SemanticType.IDENTIFIER),
            text_columns=self.columns_of_type(SemanticType.TEXT),
            unknown_columns=[
                column.column_name
                for column in self.columns
                if column.semantic_type in (None, SemanticType.UNKNOWN)
            ],
            data_dictionary=data_dictionary,
        )
