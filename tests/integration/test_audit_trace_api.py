from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.shared.config.settings import Settings
from app.shared.domain.models.report import AnalysisReport


def upload(client):
    rows = ["x,y,control"]
    for i in range(60):
        control, noise = i // 5, i % 5 - 2
        rows.append(f"{control * 10 + noise},{control * 20 - noise},{control}")
    response = client.post("/intake", files={"file": ("audit.csv", "\n".join(rows), "text/csv")})
    assert response.status_code == 200
    return response.json()["profile"]["dataset_id"]


def test_real_trace_snapshot_and_overrides_survive_restart(tmp_path: Path):
    settings = Settings(
        _env_file=None, persistence={"database_url": f"sqlite:///{tmp_path / 'audit.db'}"}
    )
    question = "Evaluar x y y controlando por control."
    requested = {
        "analysis": {"max_tool_calls": 2, "max_hypotheses": 1},
        "performance": {"timeout_seconds": 30},
    }
    with TestClient(create_app(settings)) as client:
        dataset_id = upload(client)
        response = client.post(
            f"/analysis/datasets/{dataset_id}",
            json={"user_question": question, "configuration": requested},
        )
        assert response.status_code == 200
        report = response.json()
        assert report["audit_version"] == "1" and report["user_question"] == question
        assert report["requested_configuration"] == requested
        assert report["dataset_id"] == dataset_id
        assert len(report["analysis_plan"]["steps"]) == 2
        assert report["planning_decisions"]
        assert report["configuration"]["analysis"]["max_tool_calls"] == 2
        assert report["configuration"]["performance"]["parallel_tools"] is False
        assert report["configuration"]["analysis"]["max_critic_cycles"] == 0
        events = report["execution_trace"]
        assert len({event["event_id"] for event in events}) == len(events)
        assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
        assert all(event["run_id"] == report["run_id"] for event in events)
        assert all(event["duration_seconds"] >= 0 for event in events)
        tools = [event for event in events if event["kind"] == "tool"]
        analysis = [event for event in tools if event["scope"] == "analysis"]
        screening = [event for event in tools if event["scope"] == "screening"]
        assert len(analysis) == report["metrics"]["tool_calls"] == 2
        assert len(screening) == report["metrics"]["screening_calls"] == 1
        results = {item["analysis_id"]: item for item in report["analysis_results"]}
        for event in analysis:
            assert event["analysis_id"] in results and event["step_id"]
            assert event["status"] == results[event["analysis_id"]]["status"]
        assert all("rows" not in event and "path" not in event for event in events)
        assert "source" not in report and "database_url" not in report["configuration"]
        run_id = report["run_id"]
    with TestClient(create_app(settings)) as client:
        assert client.get(f"/reports/{run_id}").json() == report
        markdown = client.get(f"/reports/{run_id}/markdown").text
        assert "## Contexto y plan" in markdown and "## Traza" in markdown


@pytest.mark.parametrize(
    "configuration",
    [
        {"analysis": {"max_tool_calls": -1}},
        {"analysis": {"max_tool_calls": True}},
        {"analysis": {"max_tool_calls": None}},
        {"analysis": {"mode": "deep"}},
        {"performance": {"parallel_tools": True}},
        {"analysis": {"max_critic_cycles": 1}},
        {"performance": {"timeout_seconds": 0}},
        {"persistence": {"database_url": "secret"}},
    ],
)
def test_stored_configuration_rejects_non_operational_or_invalid_options(client, configuration):
    assert (
        client.post("/analysis/datasets/unused", json={"configuration": configuration}).status_code
        == 422
    )


def test_historical_report_requires_no_new_fields():
    report = AnalysisReport.model_validate({"run_id": "historical", "status": "SKIPPED"})
    assert report.audit_version is None and report.analysis_plan is None
    assert report.execution_trace == [] and report.dataset_id is None
