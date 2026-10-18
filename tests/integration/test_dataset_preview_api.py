import asyncio
import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from preview_support import registered_frame

from app.api.main import create_app
from app.modules.data_intake.adapters.datasource.delimited_source import PandasLocalTable
from app.modules.data_intake.domain.preview import MAX_PREVIEW_BYTES, MAX_PREVIEW_OFFSET
from app.shared.config.settings import Settings


def upload(
    client: TestClient,
    name: str = "sample.csv",
    content: bytes = b"id,value\n001,10\n002,20\n003,30\n",
) -> str:
    result = client.post("/intake", files={"file": (name, content)})
    assert result.status_code == 200
    return result.json()["profile"]["dataset_id"]


@pytest.mark.parametrize("filename,delimiter", [("sample.csv", ","), ("sample.tsv", "\t")])
def test_intake_preview_preserves_column_and_row_order(client, filename, delimiter) -> None:
    text = (
        f"codigo{delimiter}importe{delimiter}activo{delimiter}etiqueta\n"
        f"001{delimiter}1.5{delimiter}true{delimiter}café\n"
        f"002{delimiter}{delimiter}false{delimiter}NA\n"
    )
    dataset_id = upload(client, filename, text.encode())
    response = client.get(f"/datasets/{dataset_id}/preview")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Request-ID"]
    result = response.json()
    assert result == {
        "dataset_id": dataset_id,
        "columns": [
            {"name": "codigo", "data_type": "string", "nullable": False},
            {"name": "importe", "data_type": "Float64", "nullable": True},
            {"name": "activo", "data_type": "boolean", "nullable": False},
            {"name": "etiqueta", "data_type": "string", "nullable": False},
        ],
        "rows": [["001", 1.5, True, "café"], ["002", None, False, "NA"]],
        "total_rows": 2,
        "offset": 0,
        "limit": 20,
        "returned_rows": 2,
        "has_more": False,
        "next_offset": None,
    }
    assert len(response.content) <= MAX_PREVIEW_BYTES
    assert "table" not in result and "profile" not in result
    json.loads(response.content, parse_constant=lambda value: pytest.fail(f"Invalid JSON: {value}"))


@pytest.mark.parametrize(
    "offset,limit,rows,more,next_offset",
    [
        (0, 2, [["001", 10], ["002", 20]], True, 2),
        (1, 1, [["002", 20]], True, 2),
        (2, 2, [["003", 30]], False, None),
        (3, 1, [], False, None),
        (999, 100, [], False, None),
    ],
)
def test_paging_metadata(client, offset, limit, rows, more, next_offset) -> None:
    dataset_id = upload(client)
    response = client.get(
        f"/datasets/{dataset_id}/preview", params={"offset": offset, "limit": limit}
    )
    assert response.status_code == 200
    page = response.json()
    assert page["rows"] == rows
    assert page["total_rows"] == 3 and page["returned_rows"] == len(rows)
    assert page["offset"] == offset and page["limit"] == limit
    assert page["has_more"] is more and page["next_offset"] == next_offset


@pytest.mark.parametrize(
    "query",
    [
        "offset=-1",
        "limit=0",
        "limit=-1",
        "limit=101",
        "limit=1.5",
        "limit=abc",
        "offset=1.5",
        f"offset={MAX_PREVIEW_OFFSET + 1}",
        "offset=",
        "limit=",
        "unexpected=1",
    ],
)
def test_invalid_queries_return_422_before_dataset_lookup(client, query) -> None:
    response = client.get(f"/datasets/missing/preview?{query}")
    assert response.status_code == 422


def test_default_and_max_limits_are_bounded_on_large_dataset(client, monkeypatch) -> None:
    dataset_id = upload(
        client, content=("value\n" + "\n".join(str(i) for i in range(1_000)) + "\n").encode()
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("Preview must not read full columns")

    monkeypatch.setattr(PandasLocalTable, "column", forbidden)
    first = client.get(f"/datasets/{dataset_id}/preview").json()
    assert first["limit"] == first["returned_rows"] == 20
    assert first["total_rows"] == 1_000 and first["next_offset"] == 20
    maximum = client.get(f"/datasets/{dataset_id}/preview?offset=800&limit=100").json()
    assert len(maximum["rows"]) == maximum["returned_rows"] == 100
    assert maximum["rows"][0] == [800] and maximum["rows"][-1] == [899]


def test_unknown_dataset_returns_existing_error_contract(client) -> None:
    response = client.get("/datasets/missing/preview")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "DATASET_NOT_FOUND"
    assert "missing" not in response.json()["detail"]["message"]


def test_lru_eviction_and_preview_access_order() -> None:
    app = create_app(Settings(_env_file=None, eda={"max_cached_datasets": 2}))
    with TestClient(app) as client:
        first, second = upload(client), upload(client)
        assert client.get(f"/datasets/{first}/preview").status_code == 200
        third = upload(client)
        assert client.get(f"/datasets/{second}/preview").status_code == 404
        assert client.get(f"/datasets/{first}/preview").status_code == 200
        assert client.get(f"/datasets/{third}/preview").status_code == 200


def test_new_process_store_does_not_recover_old_dataset() -> None:
    with TestClient(create_app(Settings(_env_file=None))) as first:
        dataset_id = upload(first)
    with TestClient(create_app(Settings(_env_file=None))) as second:
        response = second.get(f"/datasets/{dataset_id}/preview")
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "DATASET_NOT_FOUND"


def test_no_reread_reprofile_or_mutation_after_upload(tmp_path: Path, monkeypatch) -> None:
    app = create_app(Settings(_env_file=None, uploads={"temporary_directory": tmp_path}))
    with TestClient(app) as client:
        dataset_id = upload(client)
        registered = client.portal.call(app.state.datasets.get, dataset_id)
        before = registered.dataset.table.frame.copy(deep=True)
        assert list(tmp_path.iterdir()) == []

        def forbidden(*args, **kwargs):
            raise AssertionError("Original source must not be read or re-profiled")

        with monkeypatch.context() as patch:
            patch.setattr(Path, "open", forbidden)
            patch.setattr(PandasLocalTable, "column", forbidden)
            assert client.get(f"/datasets/{dataset_id}/preview?offset=1&limit=1").status_code == 200
        pd.testing.assert_frame_equal(before, registered.dataset.table.frame)


def test_preview_does_not_mix_datasets(client) -> None:
    first = upload(client, content=b"a\nprivate-marker-A\n")
    second = upload(client, content=b"b\nmarker-B\n")
    response = client.get(f"/datasets/{second}/preview")
    assert first != second
    assert response.json()["rows"] == [["marker-B"]]
    assert "private-marker-A" not in response.text


@pytest.mark.parametrize(
    "frame,expected",
    [
        (pd.DataFrame({"empty": pd.Series(dtype="string")}), []),
        (pd.DataFrame(), []),
        (pd.DataFrame({"empty": pd.Series([pd.NA, pd.NA], dtype="Int64")}), [[None], [None]]),
        (
            pd.DataFrame({"date": pd.to_datetime(["2026-10-17", None], utc=True)}),
            [["2026-10-17T00:00:00+00:00"], [None]],
        ),
    ],
)
def test_provider_edge_cases_are_json_serializable(client, frame, expected) -> None:
    registered = registered_frame(frame)
    client.portal.call(client.app.state.datasets.register, registered)
    response = client.get(f"/datasets/{registered.dataset_id}/preview")
    assert response.status_code == 200
    assert response.json()["rows"] == expected
    assert response.json()["total_rows"] == len(frame)
    assert response.json()["returned_rows"] == len(expected)


@pytest.mark.parametrize(
    "frame,code,status",
    [
        (pd.DataFrame({"secret": ["PRIVATE-CELL" * 10_000]}), "PREVIEW_TOO_LARGE", 413),
        (pd.DataFrame({"c": ["x" * 60_000] * 20}), "PREVIEW_TOO_LARGE", 413),
        (pd.DataFrame({f"c{i}": [1] for i in range(1_001)}), "PREVIEW_TOO_LARGE", 413),
        (pd.DataFrame({"c": [float("inf")]}), "PREVIEW_UNSUPPORTED", 422),
    ],
)
def test_size_and_serialization_errors_are_controlled_and_release_capacity(
    client, frame, code, status
) -> None:
    registered = registered_frame(frame)
    client.portal.call(client.app.state.datasets.register, registered)
    response = client.get(f"/datasets/{registered.dataset_id}/preview")
    assert response.status_code == status
    assert response.json()["detail"]["code"] == code
    assert "PRIVATE-CELL" not in response.text
    assert client.app.state.operation_capacity._active == 0
    dataset_id = upload(client)
    assert client.get(f"/datasets/{dataset_id}/preview").status_code == 200


def test_preview_rate_limit_is_shared_with_exploration_and_precedes_lookup() -> None:
    app = create_app(Settings(_env_file=None, deployment={"max_exploration_requests": 1}))
    with TestClient(app) as client:
        assert client.get("/datasets/missing/preview").status_code == 404
        for path in ["/datasets/missing/preview", "/datasets/missing/tools/descriptive_statistics"]:
            response = client.get(path) if path.endswith("preview") else client.post(path)
            assert response.status_code == 429
            assert response.json()["detail"]["code"] == "REQUEST_RATE_LIMITED"
            assert response.headers["Retry-After"] == "60"


async def test_preview_reserves_shared_capacity_without_queuing() -> None:
    app = create_app(Settings(_env_file=None, deployment={"max_concurrent_operations": 1}))
    with TestClient(app) as client:
        dataset_id = upload(client)
        started, release = asyncio.Event(), asyncio.Event()
        original = app.state.preview_use_case.execute

        async def blocked(*args, **kwargs):
            started.set()
            await release.wait()
            return await original(*args, **kwargs)

        execute = AsyncMock(side_effect=blocked)
        app.state.preview_use_case.execute = execute
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as http:
            first = asyncio.create_task(http.get(f"/datasets/{dataset_id}/preview"))
            try:
                await asyncio.wait_for(started.wait(), timeout=5)
                response = await http.get(f"/datasets/{dataset_id}/preview")
                assert response.status_code == 429
                assert response.json()["detail"]["code"] == "ANALYSIS_CAPACITY_EXCEEDED"
                assert response.headers["Retry-After"] == "1"
                execute.assert_awaited_once()
            finally:
                release.set()
                assert (await asyncio.wait_for(first, timeout=10)).status_code == 200
        assert app.state.operation_capacity._active == 0


def test_cell_values_are_not_logged(client, caplog) -> None:
    secret = "SYNTHETIC-NOT-FOR-LOGS"
    dataset_id = upload(client, content=f"a\n{secret}\n".encode())
    with caplog.at_level(logging.INFO, logger="app.api"):
        assert client.get(f"/datasets/{dataset_id}/preview").status_code == 200
    assert secret not in caplog.text
