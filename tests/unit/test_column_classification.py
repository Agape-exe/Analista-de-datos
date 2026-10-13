from datetime import datetime

import pytest

from app.config.settings import Settings
from app.domain.models.data_dictionary import DataDictionaryEntry
from app.domain.models.dataset import ColumnSchema
from app.domain.services.column_classification import classify_column


@pytest.mark.parametrize(
    "name, values, expected",
    [
        ("amount", [1.2, 2.7, 4.9], "numeric"),
        ("customer_id", [1, 1, 2], "identifier"),
        ("customerId", ["A1", "A2", "A3"], "identifier"),
        ("id", [1.2, 2.3, 3.4], "numeric"),
        ("code", ["001", "002", "003"], "identifier"),
        ("uuid", ["d8b619d7-9a2d-40f4-9f26-7a2431ddde2f"], "identifier"),
        ("created_at", ["2026-01-01", "2026-01-02"], "temporal"),
        ("event", [datetime(2026, 1, 1)], "temporal"),
        ("ambiguous_date", ["01/02/2026", "02/03/2026"], "categorical"),
        ("broken_date", ["2026-01-01", "2026-13-50"], "categorical"),
        ("segment", ["A", "B", "A"], "categorical"),
        ("active", [True, False, None], "categorical"),
        ("description", ["first note", "second note"], "text"),
        ("empty", [None, None], "unknown"),
        ("mixed", [1, "a"], "unknown"),
    ],
)
def test_roles(name: str, values: list[object], expected: str) -> None:
    profile = classify_column(
        ColumnSchema(name=name, data_type="example"), values, Settings(_env_file=None).data_intake
    )
    assert profile.semantic_type == expected
    assert profile.missing_count == sum(value is None for value in values)
    assert profile.classification_source == "inferred"
    assert profile.classification_reason


def test_dictionary_override_and_conflict() -> None:
    options = Settings(_env_file=None).data_intake
    schema = ColumnSchema(name="group", data_type="Int64")
    entry = DataDictionaryEntry(column_name="group", source="official", semantic_type="categorical")
    profile = classify_column(schema, [1, 2, 3], options, entry)
    assert profile.semantic_type == "categorical"
    assert profile.classification_source == "official"
    entry.semantic_type = "temporal"
    profile = classify_column(schema, [1, 2, 3], options, entry)
    assert profile.semantic_type == "numeric"
    assert profile.warnings
    assert profile.classification_source == "inferred"


def test_configurable_policies() -> None:
    options = Settings(_env_file=None).data_intake
    schema = ColumnSchema(name="value", data_type="string")
    options.categorical_max_unique = 1
    assert classify_column(schema, ["a", "b"], options).semantic_type == "text"
    options.temporal_formats = ["%d/%m/%Y"]
    assert classify_column(schema, ["01/02/2026"], options).semantic_type == "temporal"
    options.temporal_parse_ratio = 0.5
    assert classify_column(schema, ["01/02/2026", "invalid"], options).semantic_type == "temporal"


def test_inferred_dictionary_field_is_not_promoted_to_official() -> None:
    entry = DataDictionaryEntry(
        column_name="group",
        source="official",
        semantic_type="categorical",
        inferred_fields=["semantic_type"],
    )
    profile = classify_column(
        ColumnSchema(name="group", data_type="Int64"),
        [1, 2, 3],
        Settings(_env_file=None).data_intake,
        entry,
    )
    assert profile.classification_source == "inferred"
