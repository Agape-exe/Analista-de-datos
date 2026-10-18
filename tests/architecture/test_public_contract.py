import json
from pathlib import Path

from app.api.main import create_app
from app.shared.config.settings import Settings

ROOT = Path(__file__).resolve().parents[2]


def test_public_http_contract_is_unchanged_by_architecture_migration() -> None:
    baseline = json.loads(
        (ROOT / "tests/fixtures/openapi_develop.json").read_text(encoding="utf-8")
    )
    current = create_app(Settings(_env_file=None)).openapi()
    # AUD-009 adds exactly one route and one response DTO. All old definitions,
    # bodies, operation IDs and paths must still match the untouched develop snapshot.
    preview = {
        "path": current["paths"].pop("/datasets/{dataset_id}/preview"),
        "schema": current["components"]["schemas"].pop("DatasetPreview"),
    }
    assert current == baseline
    expected_preview = json.loads(
        (ROOT / "tests/fixtures/openapi_preview.json").read_text(encoding="utf-8")
    )
    assert preview == expected_preview


def test_migration_map_points_to_existing_files() -> None:
    mapping = json.loads((ROOT / "docs/architecture-path-map.json").read_text(encoding="utf-8"))
    assert mapping["base_commit"] == "4aaa945cd10c43ca5f3e015a76443f905af4271d"
    for target in mapping["moved_files"].values():
        assert (ROOT / target).is_file(), target
    for targets in mapping["split_files"].values():
        for target in targets:
            assert (ROOT / target).is_file(), target
