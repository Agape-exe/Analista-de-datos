from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.shared.config.settings import Settings


def upload_control_data(client):
    rows = ["x,y,control,label"]
    for i in range(60):
        rows.append(f"{i + (i % 3) / 10},{2 * i + (i % 5) / 10},{i // 5},group-{i % 2}")
    response = client.post("/intake", files={"file": ("control.csv", "\n".join(rows), "text/csv")})
    assert response.status_code == 200
    return response.json()["profile"]["dataset_id"]


def test_real_screening_provenance_reaches_critic_and_survives_report_recovery(tmp_path):
    settings = Settings(
        _env_file=None, persistence={"database_url": f"sqlite:///{tmp_path / 'provenance.db'}"}
    )
    with TestClient(create_app(settings)) as client:
        fixture = Path("tests/fixtures/associations.csv").read_bytes()
        dataset_id = client.post(
            "/intake", files={"file": ("associations.csv", fixture, "text/csv")}
        ).json()["profile"]["dataset_id"]
        response = client.post(f"/analysis/datasets/{dataset_id}", json={})
        assert response.status_code == 200
        report = response.json()
        summary = report["screening_summary"]
        assert summary["top_relationships"] and summary["tests_performed"] > 0
        [screening_event] = [
            event
            for event in report["execution_trace"]
            if event.get("kind") == "tool" and event.get("scope") == "screening"
        ]
        assert summary["analysis_id"] == screening_event["analysis_id"]
        matches = 0
        for assessment in report["relationship_assessments"]:
            ranked = next(
                (
                    item
                    for item in summary["top_relationships"]
                    if {item["x"], item["y"]} == set(assessment["variables"])
                ),
                None,
            )
            if ranked is None:
                continue
            matches += 1
            notes = " ".join(assessment["limitations"])
            assert f"Screening {summary['analysis_id']}" in notes
            assert f"n={ranked['sample_size']}" in notes
            assert f"p ajustado={ranked['adjusted_p_value']}" in notes
            assert summary["correction"] in notes
            assert "retesteo independiente" in notes
        assert matches > 0
        # Ranking is not injected into Analysis just to make the provenance test pass.
        assert all(item["method"] != "relationship_ranking" for item in report["analysis_results"])
        assert report["metrics"]["screening_calls"] == 1
        assert report["metrics"]["tool_calls"] == sum(
            event.get("kind") == "tool" and event.get("scope") == "analysis"
            for event in report["execution_trace"]
        )
    with TestClient(create_app(settings)) as client:
        assert client.get(f"/reports/{report['run_id']}").json() == report


def test_selected_control_is_in_plan_result_trace_and_saved_report(tmp_path):
    settings = Settings(
        _env_file=None, persistence={"database_url": f"sqlite:///{tmp_path / 'control.db'}"}
    )
    with TestClient(create_app(settings)) as client:
        dataset_id = upload_control_data(client)
        previous = client.post(f"/analysis/datasets/{dataset_id}", json={}).json()
        selection = {"variables": ["x", "y"], "control_variable": "control"}
        response = client.post(
            f"/analysis/datasets/{dataset_id}",
            json={
                "control_selection": selection,
                "configuration": {"analysis": {"max_tool_calls": 2}},
            },
        )
        assert response.status_code == 200
        report = response.json()
        assert report["run_id"] != previous["run_id"]
        steps = report["analysis_plan"]["steps"]
        assert [step["request"]["method"] for step in steps] == ["pearson", "partial_correlation"]
        assert steps[1]["request"]["variables"] == selection["variables"]
        assert steps[1]["request"]["parameters"] == {"control_variable": "control"}
        assert steps[1]["depends_on"] == [steps[0]["step_id"]]
        assert report["analysis_plan"]["decisions"][0]["reason"].startswith(
            "explicit user selection"
        )
        [partial] = [
            item for item in report["analysis_results"] if item["method"] == "partial_correlation"
        ]
        assert partial["status"] == "SUCCESS"
        assert partial["metadata"]["step_id"] == steps[1]["step_id"]
        assert partial["metadata"]["control_variable"] == "control"
        assert any(
            event.get("analysis_id") == partial["analysis_id"]
            and event.get("step_id") == steps[1]["step_id"]
            for event in report["execution_trace"]
        )
        assert any(item["analysis_id"] == partial["analysis_id"] for item in report["evidence"])
        assert report["metrics"]["tool_calls"] == 2
        assert client.get(f"/reports/{previous['run_id']}").json() == previous
    with TestClient(create_app(settings)) as client:
        assert client.get(f"/reports/{report['run_id']}").json() == report


@pytest.mark.parametrize(
    "selection",
    [
        {"variables": ["x", "x"], "control_variable": "control"},
        {"variables": ["x", "y"], "control_variable": "x"},
        {"variables": ["x"], "control_variable": "control"},
        {"variables": ["x", "y"], "control_variable": "unknown"},
        {"variables": ["x", "y"], "control_variable": "label"},
        {"variables": ["x", "label"], "control_variable": "control"},
        {"variables": ["x", "y"], "control_variable": " "},
        {"variables": ["x", "y"], "control_variable": "control", "extra": True},
    ],
)
def test_invalid_control_selection_is_rejected_by_api(client, selection):
    dataset_id = upload_control_data(client)
    response = client.post(
        f"/analysis/datasets/{dataset_id}", json={"control_selection": selection}
    )
    assert response.status_code == 422


def test_control_selection_respects_budget_without_silently_running_only_baseline(client):
    dataset_id = upload_control_data(client)
    response = client.post(
        f"/analysis/datasets/{dataset_id}",
        json={
            "control_selection": {"variables": ["x", "y"], "control_variable": "control"},
            "configuration": {"analysis": {"max_tool_calls": 1}},
        },
    )
    assert response.status_code == 200
    report = response.json()
    assert report["stage_statuses"]["Planner"] == "SKIPPED"
    assert report["analysis_plan"] is None and report["analysis_results"] == []
    assert report["metrics"]["tool_calls"] == 0
    assert report["planning_decisions"][0]["control_variable"] == "control"
    assert report["planning_decisions"][0]["variables"] == ["x", "y"]
    assert any("at least two tool calls" in warning for warning in report["warnings"])
