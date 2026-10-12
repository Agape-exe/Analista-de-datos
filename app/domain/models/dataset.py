from pydantic import Field

from app.domain.models.base import DomainModel


class ColumnSchema(DomainModel):
    name: str = Field(min_length=1)
    data_type: str
    nullable: bool = True


class DatasetSchema(DomainModel):
    columns: list[ColumnSchema] = Field(default_factory=list)


class ColumnProfile(DomainModel):
    column_name: str
    data_type: str
    semantic_type: str | None = None
    missing_count: int | None = Field(default=None, ge=0)
    unique_count: int | None = Field(default=None, ge=0)


class DatasetProfile(DomainModel):
    dataset_id: str
    row_count: int = Field(ge=0)
    columns: list[ColumnProfile] = Field(default_factory=list)
