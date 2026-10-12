import pytest
from pydantic import ValidationError

from app.domain.models.data_dictionary import DataDictionary, DataDictionaryEntry


def test_dictionary_round_trip_and_duplicate_rejection() -> None:
    entry = DataDictionaryEntry(column_name="age", source="manual", confidence=0.9)
    dictionary = DataDictionary(entries=[entry])
    assert DataDictionary.model_validate_json(dictionary.model_dump_json()) == dictionary
    with pytest.raises(ValidationError, match="unique"):
        DataDictionary(entries=[entry, entry])


def test_invalid_source() -> None:
    with pytest.raises(ValidationError):
        DataDictionaryEntry(column_name="age", source="unknown")
