from pathlib import Path

from fastapi.testclient import TestClient

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
