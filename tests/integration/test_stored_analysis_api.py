import json
from pathlib import Path

from fastapi.testclient import TestClient

FIXTURE = Path(__file__).parents[1] / "fixtures" / "associations.csv"


def upload(client: TestClient, dictionary: dict | None = None) -> dict:
    files = {"file": ("associations.csv", FIXTURE.read_bytes(), "text/csv")}
    if dictionary is not None:
        files["data_dictionary"] = ("dictionary.json", json.dumps(dictionary), "application/json")
    response = client.post("/intake", files=files)
    assert response.status_code == 200
    return response.json()


def test_analysis_reuses_intake_dataset(client: TestClient) -> None:
    dictionary = {"entries": [{"column_name": "REGION", "source": "official", "unit": "zona"}]}
    intake = upload(client, dictionary)
    dataset_id = intake["profile"]["dataset_id"]

    response = client.post(
        f"/analysis/datasets/{dataset_id}", json={"user_question": " ¿Qué se relaciona? "}
    )

    assert response.status_code == 200
    report = response.json()
    assert report["status"] != "FAILED", report["errors"]
    assert report["dataset_profile"] == intake["profile"]
    assert report["stage_statuses"]["DataUnderstanding"] == "SUCCESS"
    assert report["metrics"]["profiling_time"] == 0
    region = next(e for e in report["data_dictionary"]["entries"] if e["column_name"] == "REGION")
    assert region["unit"] == "zona"
    assert client.get(f"/reports/{report['run_id']}").status_code == 200
    # The intake dataset stays available for further analyses and exploration.
    assert client.post(f"/analysis/datasets/{dataset_id}").status_code == 200
    ranking = client.post(f"/datasets/{dataset_id}/tools/relationship_ranking")
    assert ranking.status_code == 200


def test_analysis_of_unknown_dataset_is_not_found(client: TestClient) -> None:
    response = client.post("/analysis/datasets/missing")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "DATASET_NOT_FOUND"
