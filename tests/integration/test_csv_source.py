from pathlib import Path

import pytest

from app.modules.data_intake.adapters.datasource.csv_source import CsvDataSource
from app.shared.application.errors import DataSourceError
from app.shared.contracts.analysis_input import CsvSourceSpec, TsvSourceSpec


async def test_small_csv() -> None:
    path = Path(__file__).parents[1] / "fixtures" / "sample.csv"
    dataset = await CsvDataSource().read(CsvSourceSpec(path=path))
    assert dataset.row_count == 3
    assert [column.name for column in dataset.schema.columns] == ["age", "income", "category"]
    assert dataset.table.column("age") == [25, 30, 35]


async def test_csv_errors(tmp_path: Path) -> None:
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    header_only = tmp_path / "header.csv"
    header_only.write_text("age,income\n", encoding="utf-8")
    for path in (empty, header_only, tmp_path / "missing.csv"):
        with pytest.raises(DataSourceError):
            await CsvDataSource().read(CsvSourceSpec(path=path))
    with pytest.raises(DataSourceError, match="only CSV"):
        await CsvDataSource().read(TsvSourceSpec(path=empty))
