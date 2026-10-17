from fastapi.testclient import TestClient


def test_health_and_trace(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"]


def test_analysis_execution_and_invalid_input(client: TestClient) -> None:
    response = client.post("/analysis", json={"source": {"kind": "csv", "path": "small.csv"}})
    assert response.status_code == 200
    assert response.json()["status"] == "FAILED"
    run_id = response.json()["run_id"]
    assert client.get(f"/reports/{run_id}").json() == response.json()
    assert client.post("/analysis", json={}).status_code == 422
    invalid = {"source": {"kind": "csv", "path": "small.csv"}, "configuration": {"llm": {}}}
    assert client.post("/analysis", json=invalid).status_code == 422
