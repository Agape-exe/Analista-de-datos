import numpy as np
from fastapi.testclient import TestClient


def upload(client: TestClient, rows: int = 60) -> str:
    rng = np.random.default_rng(1)
    lines = ["id,devengado,girado,region"]
    for index in range(rows):
        devengado = rng.normal(1000, 100)
        girado = 0.9 * devengado + rng.normal(0, 10)
        lines.append(f"{index:03d},{devengado:.2f},{girado:.2f},{'NS'[index % 2]}")
    content = ("\n".join(lines) + "\n").encode()
    response = client.post("/intake", files={"file": ("montos.csv", content, "text/csv")})
    assert response.status_code == 200
    return response.json()["profile"]["dataset_id"]


def test_tools_catalog(client: TestClient) -> None:
    response = client.get("/tools")
    assert response.status_code == 200
    assert "relationship_ranking" in response.json()["tools"]


def test_run_tools_on_intake_dataset(client: TestClient) -> None:
    dataset_id = upload(client)
    ranking = client.post(f"/datasets/{dataset_id}/tools/relationship_ranking")
    assert ranking.status_code == 200
    top = ranking.json()["result"]["top_relationships"][0]
    assert {top["x"], top["y"]} == {"devengado", "girado"}
    assert top["method"] in {"pearson", "spearman"} and top["score"] > 0.9
    scatter = client.post(
        f"/datasets/{dataset_id}/tools/chart_scatter",
        json={"variables": ["devengado", "girado"]},
    )
    assert scatter.status_code == 200
    assert scatter.json()["result"]["kind"] == "scatter"
    assert scatter.json()["result"]["total_points"] == 60


def test_tool_outcomes_and_http_errors(client: TestClient) -> None:
    dataset_id = upload(client)
    skipped = client.post(
        f"/datasets/{dataset_id}/tools/pearson", json={"variables": ["devengado", "region"]}
    )
    assert skipped.status_code == 200 and skipped.json()["status"] == "SKIPPED"
    unknown_tool = client.post(f"/datasets/{dataset_id}/tools/kendall")
    assert unknown_tool.status_code == 404
    assert unknown_tool.json()["detail"]["code"] == "TOOL_NOT_FOUND"
    missing = client.post("/datasets/expired/tools/pearson")
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "DATASET_NOT_FOUND"
    invalid = client.post(f"/datasets/{dataset_id}/tools/pearson", json={"extra": 1})
    assert invalid.status_code == 422
