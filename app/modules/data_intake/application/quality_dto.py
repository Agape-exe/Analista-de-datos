from typing import Literal

from pydantic import Field

from app.modules.data_intake.domain.quality import QualityRuleResult
from app.shared.domain.models.base import DomainModel


class QualityColumnMetrics(DomainModel):
    column_name: str
    data_type: str
    missing_count: int = Field(ge=0)
    missing_percentage: float = Field(ge=0, le=100)


class QualityMissingMetrics(DomainModel):
    missing_cells: int = Field(ge=0)
    missing_percentage: float = Field(ge=0, le=100)
    incomplete_rows: int = Field(ge=0)
    complete_rows: int = Field(ge=0)
    columns: list[QualityColumnMetrics]


class QualityDuplicateMetrics(DomainModel):
    """Full-row equality; duplicate_rows excludes each group's first occurrence."""

    duplicate_rows: int = Field(ge=0)
    duplicate_percentage: float = Field(ge=0, le=100)
    duplicate_groups: int = Field(ge=0)


class DatasetQuality(DomainModel):
    """Exact aggregates only, never raw rows. Percentages use a 0–100 scale.

    Zero denominators yield 0%; rules on empty tables are NOT_EVALUATED.
    Unsupported/over-budget evaluations fail as a whole, without partial metrics.
    """

    dataset_id: str
    status: Literal["EVALUATED", "NOT_EVALUATED"]
    total_rows: int = Field(ge=0)
    total_columns: int = Field(ge=0)
    total_cells: int = Field(ge=0)
    missing: QualityMissingMetrics
    duplicates: QualityDuplicateMetrics
    rules: list[QualityRuleResult]
