import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.api.main import create_app
from app.config.settings import Settings


def test_cors_allows_explicit_origin_and_preflight() -> None:
    origin = "https://analyst.example.test"
    settings = Settings(_env_file=None, deployment={"cors_allowed_origins": [origin]})
    with TestClient(create_app(settings)) as client:
        allowed = client.get("/health", headers={"Origin": origin})
        assert allowed.headers["access-control-allow-origin"] == origin
        blocked = client.get("/health", headers={"Origin": "https://other.example.test"})
        assert "access-control-allow-origin" not in blocked.headers
        preflight = client.options(
            "/analysis/upload",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == origin


def test_local_analysis_route_is_not_registered_when_disabled() -> None:
    settings = Settings(_env_file=None, deployment={"allow_local_analysis": False})
    application = create_app(settings)
    assert "/analysis" not in application.openapi()["paths"]
    with TestClient(application) as client:
        assert client.post("/analysis", json={}).status_code == 404


def test_upload_limit_accepts_exact_payload_and_cleans_up(tmp_path: Path) -> None:
    payload = b"a\n1\n"
    settings = Settings(
        _env_file=None,
        uploads={"temporary_directory": tmp_path, "max_dataset_bytes": len(payload)},
    )
    with TestClient(create_app(settings)) as client:
        response = client.post("/analysis/upload", files={"file": ("small.csv", payload)})
        assert response.status_code == 200
        assert list(tmp_path.iterdir()) == []
        oversized = client.post("/analysis/upload", files={"file": ("large.csv", payload + b"2\n")})
        assert oversized.status_code == 413
        assert list(tmp_path.iterdir()) == []


def test_analysis_upload_rejects_oversized_dictionary_and_cleans_up(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        uploads={
            "temporary_directory": tmp_path,
            "max_dataset_bytes": 10,
            "max_dictionary_bytes": 8,
        },
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/analysis/upload",
            files={
                "file": ("small.csv", b"a\n1\n"),
                "data_dictionary": ("dictionary.json", b"x" * 9),
            },
        )
        assert response.status_code == 413
        assert response.json()["detail"]["code"] == "UPLOAD_TOO_LARGE"
        assert list(tmp_path.iterdir()) == []


def test_upload_rate_limit_returns_retry_after() -> None:
    settings = Settings(
        _env_file=None,
        deployment={"max_upload_requests": 1, "max_exploration_requests": 1},
    )
    with TestClient(create_app(settings)) as client:
        first = client.post("/intake", files={"file": ("small.csv", b"a\n1\n")})
        assert first.status_code == 200
        limited = client.post("/intake", files={"file": ("small.csv", b"a\n1\n")})
        assert limited.status_code == 429
        assert limited.json()["detail"]["code"] == "REQUEST_RATE_LIMITED"
        assert limited.headers["Retry-After"] == "60"


def test_report_rate_limit_runs_before_report_lookup() -> None:
    settings = Settings(_env_file=None, deployment={"max_report_requests": 1})
    with TestClient(create_app(settings)) as client:
        assert client.get("/reports/unknown").status_code == 404
        limited = client.get("/reports/unknown")
        assert limited.status_code == 429
        assert limited.headers["Retry-After"] == "60"


def test_stored_analysis_shares_upload_rate_limit() -> None:
    settings = Settings(_env_file=None, deployment={"max_upload_requests": 2})
    application = create_app(settings)
    with TestClient(application) as client:
        intake = client.post("/intake", files={"file": ("small.csv", b"a\n1\n")})
        dataset_id = intake.json()["profile"]["dataset_id"]
        execute = AsyncMock(wraps=application.state.analysis_use_case.execute)
        application.state.analysis_use_case.execute = execute

        assert client.post(f"/analysis/datasets/{dataset_id}").status_code == 200
        limited = client.post(f"/analysis/datasets/{dataset_id}")
        assert limited.status_code == 429
        assert limited.json()["detail"]["code"] == "REQUEST_RATE_LIMITED"
        assert limited.headers["Retry-After"] == "60"
        execute.assert_awaited_once()


def test_stored_analysis_rate_limit_runs_before_dataset_lookup() -> None:
    settings = Settings(_env_file=None, deployment={"max_upload_requests": 1})
    with TestClient(create_app(settings)) as client:
        assert client.post("/analysis/datasets/missing").status_code == 404
        limited = client.post("/analysis/datasets/another-missing")
        assert limited.status_code == 429
        assert limited.json()["detail"]["code"] == "REQUEST_RATE_LIMITED"
        assert limited.headers["Retry-After"] == "60"


async def test_stored_analysis_reserves_shared_operation_capacity() -> None:
    settings = Settings(_env_file=None, deployment={"max_concurrent_operations": 1})
    application = create_app(settings)
    with TestClient(application) as client:
        intake = client.post("/intake", files={"file": ("small.csv", b"a\n1\n")})
        dataset_id = intake.json()["profile"]["dataset_id"]
        original_execute = application.state.analysis_use_case.execute
        started = asyncio.Event()
        release = asyncio.Event()

        async def blocked_execute(analysis_input):
            started.set()
            await release.wait()
            return await original_execute(analysis_input)

        execute = AsyncMock(side_effect=blocked_execute)
        application.state.analysis_use_case.execute = execute
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://testserver"
        ) as async_client:
            path = f"/analysis/datasets/{dataset_id}"
            first = asyncio.create_task(async_client.post(path))
            try:
                await asyncio.wait_for(started.wait(), timeout=5)
                for limited in (
                    await async_client.post(path),
                    await async_client.post(
                        "/analysis/upload", files={"file": ("small.csv", b"a\n1\n")}
                    ),
                ):
                    assert limited.status_code == 429
                    assert limited.json()["detail"]["code"] == "ANALYSIS_CAPACITY_EXCEEDED"
                    assert limited.headers["Retry-After"] == "1"
                execute.assert_awaited_once()
            finally:
                release.set()
                response = await asyncio.wait_for(first, timeout=10)
            assert response.status_code == 200
            assert (await async_client.post(path)).status_code == 200


def test_stored_analysis_releases_capacity_after_failure() -> None:
    settings = Settings(_env_file=None, deployment={"max_concurrent_operations": 1})
    application = create_app(settings)
    with TestClient(application, raise_server_exceptions=False) as client:
        intake = client.post("/intake", files={"file": ("small.csv", b"a\n1\n")})
        dataset_id = intake.json()["profile"]["dataset_id"]
        original_execute = application.state.analysis_use_case.execute
        application.state.analysis_use_case.execute = AsyncMock(side_effect=RuntimeError("failed"))

        assert client.post(f"/analysis/datasets/{dataset_id}").status_code == 500
        application.state.analysis_use_case.execute = original_execute
        assert client.post(f"/analysis/datasets/{dataset_id}").status_code == 200
