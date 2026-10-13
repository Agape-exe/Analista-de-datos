from typing import Literal

from pydantic import Field

from app.domain.models.base import DomainModel
from app.domain.models.dataset import DatasetProfile, DatasetSummary


class IntakeOptions(DomainModel):
    delimiter: str = Field(default=",", min_length=1, max_length=1)
    encoding: str = Field(default="utf-8", min_length=1)


class DatasetCompleteness(DomainModel):
    missing_cells: int = Field(ge=0)
    total_cells: int = Field(ge=0)
    missing_percentage: float = Field(ge=0, le=100)
    column_missing_percentages: dict[str, float]


class IntakeResponse(DomainModel):
    """Metadata-only HTTP response; no raw rows or server filesystem paths."""

    status: Literal["SUCCESS"] = "SUCCESS"
    filename: str
    profile: DatasetProfile
    summary: DatasetSummary
    completeness: DatasetCompleteness
    warnings: list[str] = Field(default_factory=list)
    profiling_time: float = Field(ge=0)
