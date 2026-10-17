from pathlib import Path

import pytest

from app.modules.data_intake.adapters.datasource.csv_source import CsvDataSource
from app.modules.data_intake.adapters.datasource.router import DataSourceRouter
from app.modules.data_intake.adapters.datasource.tsv_source import TsvDataSource
from app.shared.application.errors import DataSourceError
from app.shared.contracts.analysis_input import CsvSourceSpec, SqlSourceSpec, TsvSourceSpec


async def test_tsv_preserves_codes_and_missing_values() -> None:
    path = Path(__file__).parents[1] / "fixtures" / "sample.tsv"
    dataset = await TsvDataSource().read(TsvSourceSpec(path=path))
    assert dataset.row_count == 3
    assert dataset.table.column("customer_id") == ["001", "002", "003"]
    assert dataset.table.column("amount") == [10.5, 20.5, None]
    assert dataset.table.column("active") == [True, False, True]


@pytest.mark.parametrize(
    "content, message",
    [
        ("a,a\n1,2\n", "unique"),
        ("a, a \n1,2\n", "unique"),
        ("a,\n1,2\n", "empty"),
        ("a,b\n1\n", "Invalid row"),
        ("a,b\n1,2,3\n", "Invalid row"),
        ('a,b\n1,"unterminated\n', "Unable to read"),
        ("a,b\n,\n", "only missing"),
    ],
)
async def test_invalid_sources(tmp_path: Path, content: str, message: str) -> None:
    path = tmp_path / "invalid.csv"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(DataSourceError, match=message):
        await CsvDataSource().read(CsvSourceSpec(path=path))


async def test_custom_delimiter_encoding_bom_and_literal_na(tmp_path: Path) -> None:
    path = tmp_path / "custom.csv"
    path.write_text('\ufeffcode;label\n0001;"NA"\n0002;"café; quoted"\n', encoding="utf-8")
    dataset = await CsvDataSource().read(CsvSourceSpec(path=path, delimiter=";"))
    assert dataset.table.column("code") == ["0001", "0002"]
    assert dataset.table.column("label") == ["NA", "café; quoted"]
    with pytest.raises(DataSourceError):
        await CsvDataSource().read(CsvSourceSpec(path=path, encoding="ascii"))


async def test_routing_and_unsupported_sql() -> None:
    router = DataSourceRouter({"csv": CsvDataSource(), "tsv": TsvDataSource()})
    path = Path(__file__).parents[1] / "fixtures" / "sample.tsv"
    assert (await router.read(TsvSourceSpec(path=path))).row_count == 3
    with pytest.raises(DataSourceError, match="sql"):
        await router.read(SqlSourceSpec(connection_ref="warehouse", table="sales"))


async def test_numeric_conversion_does_not_round_large_codes(tmp_path: Path) -> None:
    path = tmp_path / "precision.csv"
    path.write_text("customer_id\n9007199254740993\n1.5\n", encoding="utf-8")
    dataset = await CsvDataSource().read(CsvSourceSpec(path=path))
    assert dataset.table.column("customer_id") == ["9007199254740993", "1.5"]


async def test_full_precision_decimals_stay_numeric(tmp_path: Path) -> None:
    path = tmp_path / "decimals.csv"
    path.write_text("income\n14173.124078682275\n-0.5\n1e-5\n\n", encoding="utf-8")
    dataset = await CsvDataSource().read(CsvSourceSpec(path=path))
    assert dataset.table.column("income") == [14173.124078682275, -0.5, 1e-5]


async def test_report_style_numbers_become_numbers_only_in_numeric_columns(
    tmp_path: Path,
) -> None:
    path = tmp_path / "accounting.csv"
    path.write_text(
        "sales,units,note,code,ambiguous\n"
        '"(0.17)",(2),(draft),(01),"1,035"\n'
        '"1,035.50",5,ok,02,2\n'
        ',"(1,200.00)",(x),03,3\n',
        encoding="utf-8",
    )
    dataset = await CsvDataSource().read(CsvSourceSpec(path=path))
    assert dataset.table.column("sales") == [-0.17, 1035.5, None]
    assert dataset.table.column("units") == [-2.0, 5.0, -1200.0]
    assert dataset.table.column("note") == ["(draft)", "ok", "(x)"]
    assert dataset.table.column("code") == ["(01)", "02", "03"]
    assert dataset.table.column("ambiguous") == ["1,035", "2", "3"]
