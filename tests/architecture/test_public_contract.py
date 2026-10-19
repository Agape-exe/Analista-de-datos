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
    # Keep the original and AUD-009 snapshots intact. AUD-013 is isolated in its
    # own additive snapshot; all previous bodies, models and operation IDs match.
    quality_schema_names = (
        "DatasetQuality",
        "QualityColumnMetrics",
        "QualityDuplicateMetrics",
        "QualityMissingMetrics",
        "QualityRuleResult",
        "QualityRuleStatus",
    )
    quality = {
        "path": current["paths"].pop("/datasets/{dataset_id}/quality"),
        "schemas": {
            name: current["components"]["schemas"].pop(name) for name in quality_schema_names
        },
    }
    preview = {
        "path": current["paths"].pop("/datasets/{dataset_id}/preview"),
        "schema": current["components"]["schemas"].pop("DatasetPreview"),
    }
    # AUD-039: nuevos endpoints y esquemas aditivos.
    grounded_paths = {
        path: current["paths"].pop(path)
        for path in (
            "/questions/catalog",
            "/reports/{run_id}/questions",
        )
    }
    grounded_schemas = {
        name: current["components"]["schemas"].pop(name)
        for name in (
            "GroundedAnswer",
            "GroundedQueryRequest",
            "GroundedReference",
        )
    }
    assert "get" in grounded_paths["/questions/catalog"]
    assert "post" in grounded_paths["/reports/{run_id}/questions"]
    assert all(grounded_schemas.values())

    # Additive audit contracts preserve every pre-existing property and route.
    schemas = current["components"]["schemas"]
    additions = {
        "AnalysisResult": {"completeness", "column_results"},
        "AnalysisReport": {
            "audit_version",
            "user_question",
            "dataset_id",
            "analysis_plan",
            "screening_candidates",
            "requested_configuration",
            "capabilities",
            "planning_decisions",
            "screening_configuration",
            "screening_summary",
        },
        "ExperimentMetrics": {"screening_calls"},
        "StoredAnalysisRequest": {"configuration"},
    }
    for name, properties in additions.items():
        for prop in properties:
            assert prop not in schemas[name].get("required", [])
            assert prop not in baseline["components"]["schemas"][name]["properties"]
            schemas[name]["properties"].pop(prop)
    for name in (
        "AnalysisPlan",
        "AnalysisStep",
        "Hypothesis",
        "ToolRequest",
        "AssociationResult",
        "ColumnResult",
        "StoredConfiguration",
        "StoredAnalysisOptions",
        "StoredPerformanceOptions",
    ):
        assert name not in baseline["components"]["schemas"]
        schemas.pop(name)
    for name, schema in schemas.items():
        assert schema == baseline["components"]["schemas"][name], name
    assert current == baseline
    expected_preview = json.loads(
        (ROOT / "tests/fixtures/openapi_preview.json").read_text(encoding="utf-8")
    )
    assert preview == expected_preview
    expected_quality = json.loads(
        (ROOT / "tests/fixtures/openapi_quality.json").read_text(encoding="utf-8")
    )
    assert quality == expected_quality


def test_migration_map_points_to_existing_files() -> None:
    mapping = json.loads((ROOT / "docs/architecture-path-map.json").read_text(encoding="utf-8"))
    assert mapping["base_commit"] == "4aaa945cd10c43ca5f3e015a76443f905af4271d"
    for target in mapping["moved_files"].values():
        assert (ROOT / target).is_file(), target
    for targets in mapping["split_files"].values():
        for target in targets:
            assert (ROOT / target).is_file(), target
