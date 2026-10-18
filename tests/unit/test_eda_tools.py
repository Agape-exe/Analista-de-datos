import json

import pytest
from eda_support import make_dataset, planted_dataset, store_with

from app.bootstrap import EDA_TOOLS, build_tool_registry
from app.shared.application.tool_registry import ToolRegistry
from app.shared.config.settings import Settings
from app.shared.domain.enums.semantic_type import SemanticType
from app.shared.domain.models.analysis import AnalysisResult, RankedRelationship, ToolRequest


@pytest.fixture
async def registry() -> ToolRegistry:
    return build_tool_registry(Settings(_env_file=None), await store_with(planted_dataset()))


async def run(registry: ToolRegistry, tool: str, *variables: str, **parameters) -> AnalysisResult:
    request = ToolRequest(
        dataset_id="ds", method=tool, variables=list(variables), parameters=parameters
    )
    result = await registry.get(tool).execute(request)
    json.dumps(result.model_dump(mode="json"), allow_nan=False)
    return result


async def test_registry_exposes_every_eda_tool(registry: ToolRegistry) -> None:
    assert len(registry.names()) == len(EDA_TOOLS) + 1
    assert "partial_correlation" in registry.names()
    assert {"pearson", "relationship_ranking", "chart_scatter"} <= set(registry.names())


async def test_pearson_tool_returns_shared_contract(registry: ToolRegistry) -> None:
    result = await run(registry, "pearson", "devengado", "girado")
    assert result.status == "SUCCESS"
    assert result.effect_size > 0.9 and result.p_value < 0.001
    assert result.sample_size == 299
    assert result.variables == ["devengado", "girado"]
    assert result.result["score"] == pytest.approx(result.effect_size, abs=1e-6)


async def test_wrong_semantic_type_is_skipped(registry: ToolRegistry) -> None:
    result = await run(registry, "pearson", "devengado", "region")
    assert result.status == "SKIPPED"
    assert result.result is None and "numeric" in result.warnings[0]


async def test_invalid_requests_fail(registry: ToolRegistry) -> None:
    unknown = await run(registry, "spearman", "devengado", "missing")
    assert unknown.status == "FAILED" and "Unknown column" in unknown.warnings[0]
    arity = await registry.get("pearson").execute(
        ToolRequest(dataset_id="ds", method="pearson", variables=["devengado"])
    )
    assert arity.status == "FAILED"
    absent = await registry.get("pearson").execute(
        ToolRequest(dataset_id="nope", method="pearson", variables=["devengado", "girado"])
    )
    assert absent.status == "FAILED" and "not available" in absent.warnings[0]


async def test_minimum_sample_size_is_enforced() -> None:
    small = make_dataset(
        {"a": [1.0, 2.0, 3.0, 4.0], "b": [2.0, 4.0, 6.0, 9.0]},
        {"a": SemanticType.NUMERIC, "b": SemanticType.NUMERIC},
    )
    registry = build_tool_registry(Settings(_env_file=None), await store_with(small))
    result = await run(registry, "pearson", "a", "b")
    assert result.status == "SKIPPED" and "at least 20" in result.warnings[0]


async def test_group_and_categorical_tools(registry: ToolRegistry) -> None:
    for method in ("anova", "kruskal_wallis"):
        result = await run(registry, method, "region", "monto")
        assert result.status == "SUCCESS" and result.p_value < 0.001
    chi = await run(registry, "chi_square", "region", "canal")
    assert chi.status == "SUCCESS" and chi.result["cramers_v"] > 0.5
    v = await run(registry, "cramers_v", "region", "color")
    assert v.status == "SUCCESS" and v.effect_size < 0.2
    mi = await run(registry, "mutual_information", "region", "monto")
    assert mi.status == "SUCCESS" and mi.p_value is None and mi.result["score"] > 0.5


async def test_correlation_matrix(registry: ToolRegistry) -> None:
    result = await run(registry, "correlation_matrix", method="spearman")
    matrix = result.result
    assert matrix["columns"] == ["devengado", "girado", "monto", "ruido", "constante"]
    assert matrix["values"][0][0] == 1.0
    assert matrix["values"][0][1] == matrix["values"][1][0] > 0.9
    assert matrix["values"][4][0] is None
    assert matrix["sample_sizes"][0][1] == 299
    assert result.warnings
    bad = await run(registry, "correlation_matrix", method="kendall")
    assert bad.status == "FAILED"


async def test_relationship_ranking_finds_planted_relationships(registry: ToolRegistry) -> None:
    result = await run(registry, "relationship_ranking")
    assert result.status == "SUCCESS"
    ranked = [
        RankedRelationship.model_validate(item) for item in result.result["top_relationships"]
    ]
    pairs = {frozenset((item.x, item.y)): item for item in ranked}
    assert frozenset(("devengado", "girado")) in pairs
    assert frozenset(("monto", "region")) in pairs
    assert frozenset(("region", "canal")) in pairs
    assert all("ruido" not in pair and "color" not in pair for pair in pairs)
    linear = pairs[frozenset(("devengado", "girado"))]
    assert linear.method in {"pearson", "spearman"} and linear.score > 0.9
    assert {item.method for item in linear.supporting} >= {"mutual_information"}
    assert pairs[frozenset(("monto", "region"))].method in {"anova", "kruskal_wallis"}
    assert pairs[frozenset(("region", "canal"))].method == "cramers_v"
    assert [item.score for item in ranked] == sorted((item.score for item in ranked), reverse=True)
    assert all(item.adjusted_p_value >= item.p_value for item in ranked)
    assert result.result["excluded_columns"] == {"constante": "constant or empty column"}
    assert "codigo_id" not in result.variables
    assert result.result["evaluated_pairs"] == 21


async def test_relationship_ranking_parameters(registry: ToolRegistry) -> None:
    result = await run(registry, "relationship_ranking", top_k=1)
    assert len(result.result["top_relationships"]) == 1
    subset = await run(registry, "relationship_ranking", "ruido", "color")
    assert subset.result["top_relationships"] == []
    identifier = await run(registry, "relationship_ranking", "codigo_id", "girado")
    assert identifier.status == "SKIPPED"


async def test_profiling_tools(registry: ToolRegistry) -> None:
    stats = (await run(registry, "descriptive_statistics")).result
    assert stats["devengado"]["count"] == 299 and stats["devengado"]["missing"] == 1
    assert 900 < stats["devengado"]["mean"] < 1100
    assert stats["region"]["unique"] == 3 and stats["region"]["missing"] == 0
    assert "codigo_id" not in stats
    missing = (await run(registry, "missing_values")).result
    assert missing["columns"]["devengado"]["missing"] == 1
    assert missing["complete_rows"] == 299
    distribution = (await run(registry, "distribution", "girado", "color")).result
    assert sum(distribution["girado"]["histogram"]["counts"]) == 300
    assert len(distribution["girado"]["histogram"]["counts"]) <= 30
    assert distribution["girado"]["normality"]["normal"] is True
    assert distribution["color"]["frequencies"]["unique"] == 2
    cardinality = (await run(registry, "cardinality")).result
    assert "constant" in cardinality["constante"]["flags"]
    assert "near_unique" in cardinality["girado"]["flags"]
    assert "near_unique" not in cardinality["codigo_id"]["flags"]


async def test_outliers_tool_flags_planted_extremes() -> None:
    values: list[object] = [float(v) for v in range(50)] + [500.0, -400.0]
    dataset = make_dataset({"v": values}, {"v": SemanticType.NUMERIC})
    registry = build_tool_registry(Settings(_env_file=None), await store_with(dataset))
    result = (await run(registry, "outliers", "v")).result["v"]
    assert result["iqr"]["count"] == 2
    assert result["iqr"]["examples"] == [500.0, -400.0]
    assert result["mad"]["count"] == 2
    skipped = await run(registry, "outliers", "v", "missing")
    assert skipped.status == "FAILED"
