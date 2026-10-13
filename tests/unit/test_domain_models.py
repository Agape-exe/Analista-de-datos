import pytest
from pydantic import ValidationError

from app.domain.models.dataset import ColumnProfile, DatasetProfile, DatasetSchema
from app.domain.models.metrics import ExperimentMetrics


def test_profile_round_trip() -> None:
    profile = DatasetProfile(dataset_id="small", row_count=3)
    assert DatasetProfile.model_validate_json(profile.model_dump_json()) == profile


def test_invalid_counts_and_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        DatasetProfile(dataset_id="small", row_count=-1)
    with pytest.raises(ValidationError):
        ExperimentMetrics(precision=1.5)
    assert ExperimentMetrics().precision is None


def test_profile_and_schema_invariants() -> None:
    with pytest.raises(ValidationError, match="unique"):
        DatasetSchema(columns=[{"name": "a", "data_type": "str"}] * 2)
    with pytest.raises(ValidationError, match="observed"):
        DatasetProfile(
            dataset_id="small",
            row_count=2,
            columns=[
                ColumnProfile(column_name="a", data_type="str", missing_count=1, unique_count=2)
            ],
        )
