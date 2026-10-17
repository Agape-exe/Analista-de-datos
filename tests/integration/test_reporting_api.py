from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.shared.config.settings import Settings


def test_upload_report_lifecycle_cleanup_and_download(tmp_path: Path):
    settings = Settings(_env_file=None, uploads={"temporary_directory": tmp_path})
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/analysis/upload", files={"file": ("example.csv", b"x,y\n1,2\n3,4\n")}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "SKIPPED"
        assert body["dataset_profile"]["row_count"] == 2
        assert body["insights"] == []
        assert not list(tmp_path.iterdir())
        run_id = body["run_id"]
        assert client.get(f"/reports/{run_id}").json() == body
        assert client.get(f"/reports/{run_id}/metrics").json() == body["metrics"]
        markdown = client.get(f"/reports/{run_id}/markdown")
        assert markdown.status_code == 200
        assert "SKIPPED" in markdown.text
        assert "No se generaron insights" in markdown.text
        assert client.get("/reports/not-found").status_code == 404


def test_durable_report_survives_app_restart(tmp_path: Path):
    settings = Settings(
        _env_file=None, persistence={"database_url": f"sqlite:///{tmp_path / 'reports.db'}"}
    )
    with TestClient(create_app(settings)) as client:
        response = client.post("/analysis/upload", files={"file": ("example.csv", b"x,y\n1,2\n")})
        assert response.status_code == 200
        original = response.json()
    with TestClient(create_app(settings)) as client:
        assert client.get(f"/reports/{original['run_id']}").json() == original


def test_upload_limits_and_invalid_dictionary_cleanup(tmp_path: Path):
    settings = Settings(
        _env_file=None, uploads={"temporary_directory": tmp_path, "max_dataset_bytes": 10}
    )
    with TestClient(create_app(settings)) as client:
        assert (
            client.post(
                "/analysis/upload", files={"file": ("large.csv", b"a,b\n123,456\n")}
            ).status_code
            == 413
        )
        assert (
            client.post("/analysis/upload", files={"file": ("file.exe", b"a,b\n1,2\n")}).status_code
            == 400
        )
        assert (
            client.post(
                "/analysis/upload",
                files={
                    "file": ("small.csv", b"a,b\n1,2\n"),
                    "data_dictionary": ("dict.json", b"not json"),
                },
            ).status_code
            == 400
        )
        assert not list(tmp_path.iterdir())
