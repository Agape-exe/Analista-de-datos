import csv
import io
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.shared.config.settings import Settings


@pytest.mark.parametrize("delimiter,filename", [(",", "synthetic.csv"), ("\t", "synthetic.tsv")])
def test_real_intake_outliers_match_positional_preview_despite_blank_lines_and_nulls(
    delimiter, filename, monkeypatch
):
    values = [None, 500] + list(range(-20, 21)) + [None, 500, -400, None]
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter=delimiter)
    writer.writerow(["code", "value", "note"])
    stream.write("\n")  # A physical line that does not represent a dataset record.
    for index, value in enumerate(values):
        writer.writerow([f"{index:03d}", value, "synthetic\nmultiline" if index == 0 else "public"])
    with TestClient(create_app(Settings(_env_file=None))) as client:
        loaded = client.post(
            "/intake",
            files={"file": (filename, stream.getvalue().encode(), "text/plain")},
            data={"delimiter": delimiter},
        )
        assert loaded.status_code == 200
        dataset_id = loaded.json()["profile"]["dataset_id"]
        assert loaded.json()["profile"]["row_count"] == len(values)
        registered = client.portal.call(client.app.state.datasets.get, dataset_id)
        before = registered.dataset.table.frame.copy(deep=True)

        def forbidden(*args, **kwargs):
            raise AssertionError("No source re-read")

        with monkeypatch.context() as patch:
            patch.setattr(Path, "open", forbidden)
            response = client.post(
                f"/datasets/{dataset_id}/tools/outliers", json={"variables": ["value"]}
            )
        assert response.status_code == 200 and response.json()["status"] == "SUCCESS"
        result = response.json()["result"]
        assert list(result) == ["value"]
        iqr = result["value"]["iqr"]
        assert iqr["examples"] == [500, 500, -400]
        assert iqr["example_rows"] == [
            {"row_index": 1, "value": 500},
            {"row_index": 44, "value": 500},
            {"row_index": 45, "value": -400},
        ]
        assert iqr["count"] == 3
        for example in iqr["example_rows"]:
            page = client.get(
                f"/datasets/{dataset_id}/preview",
                params={"offset": example["row_index"], "limit": 1},
            )
            assert page.status_code == 200
            assert page.json()["rows"][0][1] == example["value"]
            assert page.json()["rows"][0][0] == f"{example['row_index']:03d}"
        pd.testing.assert_frame_equal(before, registered.dataset.table.frame)
        assert "note" not in result and "synthetic\nmultiline" not in response.text


@pytest.mark.parametrize("limit", [0, 1])
def test_existing_http_endpoint_keeps_configured_example_limit(limit):
    with TestClient(
        create_app(Settings(_env_file=None, eda={"max_outlier_examples": limit}))
    ) as client:
        content = "v\n" + "\n".join(map(str, list(range(-20, 21)) + [500, -400]))
        dataset_id = client.post(
            "/intake", files={"file": ("public.csv", content.encode(), "text/csv")}
        ).json()["profile"]["dataset_id"]
        result = client.post(
            f"/datasets/{dataset_id}/tools/outliers", json={"variables": ["v"]}
        ).json()
        assert result["status"] == "SUCCESS"
        assert result["result"]["v"]["iqr"]["count"] == 2
        assert len(result["result"]["v"]["iqr"]["examples"]) == limit
        assert len(result["result"]["v"]["iqr"]["example_rows"]) == limit
