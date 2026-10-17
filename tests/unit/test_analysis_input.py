import pytest
from pydantic import ValidationError

from app.shared.config.settings import Settings
from app.shared.contracts.analysis_input import AnalysisInput, resolve_configuration


def test_source_discrimination_schema_alias_and_overrides() -> None:
    value = AnalysisInput.model_validate(
        {
            "source": {"kind": "sql", "connection_ref": "warehouse", "table": "sales"},
            "schema": {"columns": []},
            "configuration": {"analysis": {"max_tool_calls": 2}},
        }
    )
    assert "schema" in value.model_dump(by_alias=True)
    config = resolve_configuration(Settings(_env_file=None), value.configuration)
    assert config.analysis.max_tool_calls == 2
    assert config.analysis.minimum_sample_size == 20
    assert AnalysisInput.model_validate_json(value.model_dump_json()) == value


def test_no_provider_overrides_or_nulls() -> None:
    for configuration in ({"llm": {}}, {"analysis": {"max_tool_calls": None}}):
        with pytest.raises(ValidationError):
            AnalysisInput(source={"kind": "csv", "path": "small.csv"}, configuration=configuration)
