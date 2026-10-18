from pydantic import ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr

from app.modules.data_intake.domain.preview import (
    DEFAULT_PREVIEW_LIMIT,
    MAX_PREVIEW_LIMIT,
    MAX_PREVIEW_OFFSET,
)
from app.shared.domain.models.base import DomainModel
from app.shared.domain.models.dataset import ColumnSchema


class DatasetPreviewQuery(DomainModel):
    """Zero-based positional paging; offsets are not business identifiers."""

    offset: int = Field(default=0, ge=0, le=MAX_PREVIEW_OFFSET)
    limit: int = Field(default=DEFAULT_PREVIEW_LIMIT, ge=1, le=MAX_PREVIEW_LIMIT)


class DatasetPreview(DomainModel):
    """Bounded rows in source order. rows[i][j] belongs to columns[j].

    Temporal scalars use ISO 8601 strings, Decimal uses lossless decimal strings,
    missing values use null. Non-finite infinities and unsupported objects are rejected.
    """

    model_config = ConfigDict(allow_inf_nan=False)

    dataset_id: str
    columns: list[ColumnSchema]
    rows: list[list[StrictStr | StrictInt | StrictFloat | StrictBool | None]]
    total_rows: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=MAX_PREVIEW_LIMIT)
    returned_rows: int = Field(ge=0, le=MAX_PREVIEW_LIMIT)
    has_more: bool
    next_offset: int | None
