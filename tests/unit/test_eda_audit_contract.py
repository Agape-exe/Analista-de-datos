import json
from pathlib import Path

import pytest
from eda_support import make_dataset, store_with
from pydantic import ValidationError

from app.bootstrap import build_tool_registry
from app.shared.config.settings import Settings
from app.shared.domain.enums.semantic_type import SemanticType
from app.shared.domain.models.analysis import AnalysisResult, ToolRequest


def test_shared_json_examples_and_historical_result():
    examples = json.loads(
        (Path(__file__).parents[1] / "fixtures/eda-result-variants.json").read_text()
    )
    assert [AnalysisResult.model_validate(item).status for item in examples] == [
        "SUCCESS",
        "SUCCESS",
        "SKIPPED",
        "FAILED",
    ]
    legacy = AnalysisResult.model_validate({"method": "pearson", "status": "SUCCESS"})
    assert legacy.completeness == "complete" and not legacy.column_results
    with pytest.raises(ValidationError):
        AnalysisResult(method="x", status="SUCCESS", completeness="partial")
    with pytest.raises(ValidationError):
        AnalysisResult(method="x", status="FAILED", result={"mean": 3})


async def test_partial_columns_preserve_measured_results_and_explicit_omissions():
    data = make_dataset(
        {"good": list(range(40)), "sparse": [None] * 39 + [2]},
        {name: SemanticType.NUMERIC for name in ("good", "sparse")},
    )
    tools = build_tool_registry(Settings(_env_file=None), await store_with(data))
    result = await tools.get("outliers").execute(
        ToolRequest(dataset_id="ds", method="outliers", variables=["good", "sparse"])
    )
    assert result.status == "SUCCESS" and result.completeness == "partial"
    assert "good" in result.result and "sparse" not in result.result
    assert result.column_results["sparse"].status == "SKIPPED"


async def test_one_column_failure_does_not_discard_other_columns(monkeypatch):
    data = make_dataset(
        {name: list(range(40)) for name in ("good", "broken")},
        {name: SemanticType.NUMERIC for name in ("good", "broken")},
    )
    tools = build_tool_registry(Settings(_env_file=None), await store_with(data))
    tool = tools.get("descriptive_statistics")
    profile = tool.profile

    def compute_column(dataset, name, role):
        if name == "broken":
            raise ArithmeticError("column calculation failed")
        return profile(dataset, name, role)

    monkeypatch.setattr(tool, "profile", compute_column)
    result = await tool.execute(ToolRequest(dataset_id="ds", method=tool.name))
    assert result.status == "SUCCESS" and result.completeness == "partial"
    assert result.result["good"]["mean"] == 19.5
    assert result.column_results["broken"].status == "FAILED"
    assert result.column_results["broken"].result is None


@pytest.mark.parametrize(
    "parameters",
    [
        {"top_k": -1},
        {"top_k": True},
        {"top_k": 2.5},
        {"top_k": "3"},
        {"significance_level": 2},
        {"significance_level": True},
        {"unknown": 1},
    ],
)
async def test_ranking_rejects_invalid_parameters_before_computing(parameters):
    data = make_dataset({"a": list(range(40))}, {"a": SemanticType.NUMERIC})
    tools = build_tool_registry(Settings(_env_file=None), await store_with(data))
    result = await tools.get("relationship_ranking").execute(
        ToolRequest(dataset_id="ds", method="relationship_ranking", parameters=parameters)
    )
    assert result.status == "FAILED" and result.result is None
