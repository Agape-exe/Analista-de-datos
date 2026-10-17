from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.config.settings import Settings


def test_full_analysis_preserves_eda_and_durable_report(tmp_path: Path) -> None:
    rows = ["x,partial_y,control"]
    for index in range(50):
        control = index // 5
        residual = (index % 5) - 2
        rows.append(f"{control * 10 + residual},{control * 20 - residual},{control}")
    content = ("\n".join(rows) + "\n").encode()
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    settings = Settings(
        _env_file=None,
        uploads={"temporary_directory": uploads},
        persistence={"database_url": f"sqlite:///{tmp_path / 'reports.db'}"},
    )
    with TestClient(create_app(settings)) as client:
        intake = client.post("/intake", files={"file": ("eda.csv", content, "text/csv")})
        assert intake.status_code == 200
        dataset_id = intake.json()["profile"]["dataset_id"]
        tool_url = f"/datasets/{dataset_id}/tools/pearson"
        request = {"variables": ["x", "partial_y"]}
        before = client.post(tool_url, json=request)
        assert before.status_code == 200
        assert before.json()["status"] == "SUCCESS"

        response = client.post(
            "/analysis/upload",
            files={"file": ("analysis.csv", content, "text/csv")},
            data={"user_question": "Evaluar x y partial_y controlando por control."},
        )
        assert response.status_code == 200
        report = response.json()
        assert report["status"] == "SUCCESS"
        assert report["stage_statuses"] == {
            stage: "SUCCESS"
            for stage in (
                "DataUnderstanding",
                "Association",
                "Planner",
                "Analysis",
                "Critic",
                "Insight",
            )
        }
        assert report["evidence"] and report["relationship_assessments"] and report["insights"]
        assert report["metrics"]["tool_calls"] == 4
        assert any(
            item["method"] == "correlation_without_outliers" for item in report["analysis_results"]
        )
        assert report["metrics"]["tokens_used"] is None
        assert report["dataset_profile"]["dataset_id"] != dataset_id
        assert not list(uploads.iterdir())
        after = client.post(tool_url, json=request)
        assert after.status_code == 200
        assert after.json()["status"] == "SUCCESS"
        assert after.json()["result"] == before.json()["result"]
        run_id = report["run_id"]

    with TestClient(create_app(settings)) as client:
        recovered = client.get(f"/reports/{run_id}")
        assert recovered.status_code == 200
        assert recovered.json() == report
        markdown = client.get(f"/reports/{run_id}/markdown")
        assert markdown.status_code == 200
        assert "SUCCESS" in markdown.text
        assert "attachment" in markdown.headers["content-disposition"]
