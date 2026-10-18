import asyncio
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
from app.modules.data_intake.domain.quality import QualityLimits
from app.shared.config.settings import Settings


@pytest.fixture
def client():
    with TestClient(create_app(Settings(_env_file=None))) as instance:
        yield instance


def upload(
    client,
    content=b"id,name,value\n001,Ana,10\n002,Luis,\n002,Luis,\n",
    filename="synthetic.csv",
    delimiter=",",
):
    response = client.post(
        "/intake", files={"file": (filename, content, "text/plain")}, data={"delimiter": delimiter}
    )
    assert response.status_code == 200
    return response.json()["profile"]["dataset_id"]


@pytest.mark.parametrize("delimiter,filename", [(",", "synthetic.csv"), ("\t", "synthetic.tsv")])
def test_real_intake_then_exact_quality_and_preview(client, delimiter, filename):
    content = "id,name,value\n001,Ana,10\n002,Luis,\n002,Luis,\n".replace(",", delimiter).encode()
    dataset_id = upload(client, content, filename, delimiter)
    response = client.get(f"/datasets/{dataset_id}/quality")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    result = response.json()
    assert result["dataset_id"] == dataset_id and result["status"] == "EVALUATED"
    assert (result["total_rows"], result["total_columns"], result["total_cells"]) == (3, 3, 9)
    assert result["missing"]["missing_cells"] == 2
    assert result["missing"]["missing_percentage"] == pytest.approx(200 / 9)
    assert result["missing"]["incomplete_rows"] == 2 and result["missing"]["complete_rows"] == 1
    assert [c["column_name"] for c in result["missing"]["columns"]] == ["id", "name", "value"]
    assert [c["missing_count"] for c in result["missing"]["columns"]] == [0, 0, 2]
    assert result["duplicates"] == {
        "duplicate_rows": 1,
        "duplicate_groups": 1,
        "duplicate_percentage": 100 / 3,
    }
    assert [(r["rule_id"], r["status"], r["observed_count"]) for r in result["rules"]] == [
        ("NO_MISSING_VALUES", "FAIL", 2),
        ("NO_DUPLICATE_ROWS", "FAIL", 1),
    ]
    preview = client.get(f"/datasets/{dataset_id}/preview").json()
    assert preview["rows"] == [["001", "Ana", 10], ["002", "Luis", None], ["002", "Luis", None]]


def test_clean_dataset_passes_both_rules_and_repeated_column_is_not_full_duplicate(client):
    dataset_id = upload(client, b"id,flag,n\n001,true,1.25\n002,true,2.5\n003,false,3.75\n")
    result = client.get(f"/datasets/{dataset_id}/quality").json()
    assert result["missing"]["missing_cells"] == result["duplicates"]["duplicate_rows"] == 0
    assert result["missing"]["complete_rows"] == 3
    assert all(rule["status"] == "PASS" for rule in result["rules"])


def test_literal_na_null_nan_remain_valid_text_not_missing(client):
    dataset_id = upload(client, b"id,label\n001,NA\n002,NULL\n003,NaN\n004,\n005,NA\n")
    result = client.get(f"/datasets/{dataset_id}/quality").json()
    assert result["missing"]["missing_cells"] == 1
    assert result["duplicates"]["duplicate_rows"] == 0
    assert [r["status"] for r in result["rules"]] == ["FAIL", "PASS"]


def test_multiple_duplicate_groups_exclude_each_first_appearance(client):
    dataset_id = upload(client, b"id,v\n001,A\n001,A\n001,A\n002,B\n002,B\n003,C\n")
    result = client.get(f"/datasets/{dataset_id}/quality").json()
    assert result["duplicates"] == {
        "duplicate_rows": 3,
        "duplicate_groups": 2,
        "duplicate_percentage": 50,
    }
    assert [r["status"] for r in result["rules"]] == ["PASS", "FAIL"]


def test_unknown_dataset_has_stable_private_404_contract(client):
    response = client.get("/datasets/private-missing-id/quality")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "DATASET_NOT_FOUND"
    assert "private-missing-id" not in response.text


def test_quality_touches_lru_and_evicted_dataset_is_404():
    with TestClient(create_app(Settings(_env_file=None, eda={"max_cached_datasets": 2}))) as client:
        first, second = upload(client), upload(client)
        assert client.get(f"/datasets/{first}/quality").status_code == 200
        third = upload(client)
        assert client.get(f"/datasets/{second}/quality").status_code == 404
        assert client.get(f"/datasets/{first}/quality").status_code == 200
        assert client.get(f"/datasets/{third}/quality").status_code == 200


def test_new_app_store_cannot_recover_old_dataset():
    with TestClient(create_app(Settings(_env_file=None))) as first:
        dataset_id = upload(first)
    with TestClient(create_app(Settings(_env_file=None))) as second:
        assert second.get(f"/datasets/{dataset_id}/quality").status_code == 404


@pytest.mark.parametrize(
    "frame",
    [
        pd.DataFrame(),
        pd.DataFrame({"empty": pd.Series(dtype="string")}),
        pd.DataFrame(index=range(2)),
    ],
)
def test_empty_provider_datasets_are_not_evaluated(client, frame):
    registered = registered_frame(frame)
    client.portal.call(client.app.state.datasets.register, registered)
    response = client.get(f"/datasets/{registered.dataset_id}/quality")
    assert response.status_code == 200
    assert response.json()["status"] == "NOT_EVALUATED"
    assert all(rule["status"] == "NOT_EVALUATED" for rule in response.json()["rules"])


@pytest.mark.parametrize(
    "frame",
    [
        pd.DataFrame({"secret": [["PRIVATE-CELL"]]}),
        pd.DataFrame({"secret": [float("inf")]}),
        pd.DataFrame({"secret": [complex(1, 2)]}),
    ],
)
def test_unsupported_values_return_controlled_422_release_capacity_and_hide_values(client, frame):
    registered = registered_frame(frame)
    client.portal.call(client.app.state.datasets.register, registered)
    response = client.get(f"/datasets/{registered.dataset_id}/quality")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "QUALITY_UNSUPPORTED"
    assert "PRIVATE-CELL" not in response.text
    assert client.app.state.operation_capacity._active == 0


@pytest.mark.parametrize(
    "limits",
    [
        QualityLimits(max_rows=2),
        QualityLimits(max_columns=2),
        QualityLimits(max_cells=8),
        QualityLimits(max_data_bytes=1),
        QualityLimits(max_value_chars=2),
        QualityLimits(max_response_bytes=20),
    ],
)
def test_resource_limits_return_controlled_413_without_partial_results(client, limits):
    dataset_id = upload(client)
    client.app.state.quality_use_case.limits = limits
    response = client.get(f"/datasets/{dataset_id}/quality")
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "QUALITY_TOO_LARGE"
    assert "missing" not in response.json()
    assert client.app.state.operation_capacity._active == 0


def test_rate_limit_is_shared_with_preview_and_exploration_before_lookup():
    app = create_app(Settings(_env_file=None, deployment={"max_exploration_requests": 1}))
    with TestClient(app) as client:
        assert client.get("/datasets/missing/quality").status_code == 404
        for path in [
            "/datasets/missing/quality",
            "/datasets/missing/preview",
            "/datasets/missing/tools/missing_values",
        ]:
            response = client.post(path) if path.endswith("missing_values") else client.get(path)
            assert response.status_code == 429
            assert response.json()["detail"]["code"] == "REQUEST_RATE_LIMITED"
            assert response.headers["Retry-After"] == "60"


async def test_shared_capacity_rejects_concurrent_evaluations():
    app = create_app(Settings(_env_file=None, deployment={"max_concurrent_operations": 1}))
    with TestClient(app) as client:
        dataset_id = upload(client)
        started, release = asyncio.Event(), asyncio.Event()
        original = app.state.quality_use_case.execute

        async def blocked(*args):
            started.set()
            await release.wait()
            return await original(*args)

        app.state.quality_use_case.execute = AsyncMock(side_effect=blocked)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as http:
            first = asyncio.create_task(http.get(f"/datasets/{dataset_id}/quality"))
            try:
                await asyncio.wait_for(started.wait(), 5)
                response = await http.get(f"/datasets/{dataset_id}/quality")
                assert response.status_code == 429
                assert response.json()["detail"]["code"] == "ANALYSIS_CAPACITY_EXCEEDED"
                assert response.headers["Retry-After"] == "1"
                app.state.quality_use_case.execute.assert_awaited_once()
            finally:
                release.set()
                assert (await asyncio.wait_for(first, 10)).status_code == 200
        assert app.state.operation_capacity._active == 0


def test_no_reread_reprofile_mutation_or_sensitive_response_logs(tmp_path, monkeypatch, caplog):
    app = create_app(Settings(_env_file=None, uploads={"temporary_directory": tmp_path}))
    with TestClient(app) as client:
        dataset_id = upload(
            client, b"id,label\n001,SYNTHETIC-PRIVATE-MARKER\n001,SYNTHETIC-PRIVATE-MARKER\n"
        )
        registered = client.portal.call(app.state.datasets.get, dataset_id)
        before = registered.dataset.table.frame.copy(deep=True)
        assert not list(tmp_path.iterdir())

        def forbidden(*args, **kwargs):
            raise AssertionError("No source I/O or re-profiling")

        with monkeypatch.context() as patch, caplog.at_level(logging.INFO, logger="app.api"):
            patch.setattr(Path, "open", forbidden)
            patch.setattr(PandasLocalTable, "column", forbidden)
            response = client.get(f"/datasets/{dataset_id}/quality")
        assert response.status_code == 200
        pd.testing.assert_frame_equal(before, registered.dataset.table.frame)
        assert "SYNTHETIC-PRIVATE-MARKER" not in response.text + caplog.text
        assert str(tmp_path) not in response.text
        assert "rows" not in response.json()


def test_existing_exploration_missing_values_matches_quality(client):
    dataset_id = upload(client)
    quality = client.get(f"/datasets/{dataset_id}/quality").json()
    exploration = client.post(f"/datasets/{dataset_id}/tools/missing_values", json={})
    assert exploration.status_code == 200
    result = exploration.json()["result"]
    assert result["missing_cells"] == quality["missing"]["missing_cells"]
    assert result["complete_rows"] == quality["missing"]["complete_rows"]


def test_dataset_quality_does_not_mix_datasets(client):
    first = upload(client)
    second = upload(client, b"a\n1\n2\n")
    assert first != second
    result = client.get(f"/datasets/{second}/quality").json()
    assert result["total_rows"] == 2 and result["total_columns"] == 1
    assert result["missing"]["missing_cells"] == result["duplicates"]["duplicate_rows"] == 0
