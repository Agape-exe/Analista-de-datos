from pathlib import Path

import pytest

from app.modules.data_intake.adapters.datasource.csv_source import CsvDataSource
from app.modules.data_intake.adapters.datasource.router import DataSourceRouter
from app.modules.data_intake.adapters.datasource.tsv_source import TsvDataSource
from app.modules.data_intake.application.services.data_understanding import DataUnderstandingService
from app.shared.application.errors import DataSourceError
from app.shared.config.settings import Settings
from app.shared.contracts.analysis_input import AnalysisInput
from app.shared.domain.models.data_dictionary import DataDictionary


def service() -> DataUnderstandingService:
    return DataUnderstandingService(
        DataSourceRouter({"csv": CsvDataSource(), "tsv": TsvDataSource()}),
        Settings(_env_file=None).data_intake,
    )


async def test_tsv_summary_and_inferred_dictionary() -> None:
    path = Path(__file__).parents[1] / "fixtures" / "sample.tsv"
    result = await service().understand(AnalysisInput(source={"kind": "tsv", "path": path}))
    summary = result.summary()
    assert summary.rows == 3
    assert summary.columns == 5
    assert summary.numeric_columns == ["amount"]
    assert summary.identifiers == ["customer_id"]
    assert summary.temporal_columns == ["created_at"]
    assert summary.categorical_columns == ["segment", "active"]
    assert result.profile.columns[1].missing_count == 1
    assert result.profiling_time >= 0
    assert all(entry.source == "inferred" for entry in result.data_dictionary.entries)
    assert all(entry.confidence is None for entry in result.data_dictionary.entries)
    assert result.profile.model_validate_json(result.profile.model_dump_json()) == result.profile
    assert type(summary).model_validate_json(summary.model_dump_json()) == summary


async def test_partial_dictionary_preserves_provenance_and_does_not_mutate() -> None:
    path = Path(__file__).parents[1] / "fixtures" / "sample.csv"
    dictionary = DataDictionary.model_validate(
        {
            "entries": [
                {
                    "column_name": "age",
                    "description": "Official age",
                    "source": "official",
                    "unit": "years",
                    "semantic_type": "numeric",
                    "data_type": "int",
                },
                {"column_name": "category", "source": "manual", "description": "Manual label"},
                {"column_name": "missing", "source": "official"},
            ]
        }
    )
    original = dictionary.model_dump_json()
    result = await service().understand(
        AnalysisInput(source={"kind": "csv", "path": path}, data_dictionary=dictionary)
    )
    entries = {entry.column_name: entry for entry in result.data_dictionary.entries}
    assert dictionary.model_dump_json() == original
    assert entries["age"].source == "official"
    assert entries["age"].description == "Official age"
    assert entries["age"].unit == "years"
    assert entries["age"].inferred_fields == []
    assert entries["category"].source == "manual"
    assert "semantic_type" in entries["category"].inferred_fields
    assert entries["income"].source == "inferred"
    assert "missing" not in entries
    assert any("absent" in warning for warning in result.warnings)


async def test_schema_mismatch_and_conflicting_dictionary(tmp_path: Path) -> None:
    path = tmp_path / "small.csv"
    path.write_text("value\ntext\nother\n", encoding="utf-8")
    with pytest.raises(DataSourceError, match="schema columns"):
        await service().understand(
            AnalysisInput(
                source={"kind": "csv", "path": path},
                schema={"columns": [{"name": "different", "data_type": "str"}]},
            )
        )
    result = await service().understand(
        AnalysisInput(
            source={"kind": "csv", "path": path},
            data_dictionary={
                "entries": [
                    {
                        "column_name": "value",
                        "source": "official",
                        "data_type": "int",
                        "semantic_type": "numeric",
                    }
                ]
            },
        )
    )
    assert result.profile.columns[0].semantic_type == "categorical"
    assert result.data_dictionary.entries[0].semantic_type == "numeric"
    assert len(result.warnings) == 2


async def test_empty_column_is_unknown(tmp_path: Path) -> None:
    path = tmp_path / "missing.csv"
    path.write_text("value,empty\n1,\n2,\n", encoding="utf-8")
    summary = (
        await service().understand(AnalysisInput(source={"kind": "csv", "path": path}))
    ).summary()
    assert summary.unknown_columns == ["empty"]
    assert summary.numeric_columns == ["value"]


async def test_schema_nullability_is_enforced(tmp_path: Path) -> None:
    path = tmp_path / "nullable.csv"
    path.write_text("a,b\n1,2\n,3\n", encoding="utf-8")
    value = AnalysisInput(
        source={"kind": "csv", "path": path},
        schema={
            "columns": [
                {"name": "a", "data_type": "int", "nullable": False},
                {"name": "b", "data_type": "int"},
            ]
        },
    )
    with pytest.raises(DataSourceError, match="non-nullable"):
        await service().understand(value)
