import numpy as np
import pytest
from eda_support import planted_dataset, store_with

from app.bootstrap import build_tool_registry
from app.modules.exploration.adapters.analytics.columns import label_array
from app.modules.exploration.adapters.analytics.profiling.measures import grouped_summary
from app.shared.application.tool_registry import ToolRegistry
from app.shared.config.settings import Settings
from app.shared.domain.models.analysis import AnalysisResult, ToolRequest


@pytest.fixture
async def registry() -> ToolRegistry:
    settings = Settings(_env_file=None, eda={"max_summary_groups": 5})
    return build_tool_registry(settings, await store_with(planted_dataset()))


async def run(registry: ToolRegistry, *variables: str, **parameters: object) -> AnalysisResult:
    request = ToolRequest(
        dataset_id="ds", method="grouped_summary", variables=list(variables), parameters=parameters
    )
    return await registry.get("grouped_summary").execute(request)


async def test_summarises_each_existing_group(registry: ToolRegistry) -> None:
    result = await run(registry, "monto", "region")
    assert result.status == "SUCCESS" and result.warnings == []
    summary = result.result
    assert isinstance(summary, dict)
    groups = summary["groups"]
    assert {group["label"] for group in groups} == {"norte", "sur", "este"}
    assert [group["rows"] for group in groups] == sorted(
        (group["rows"] for group in groups), reverse=True
    )
    assert sum(group["rows"] for group in groups) == 300
    medians = {group["label"]: group["median"] for group in groups}
    assert medians["norte"] < medians["sur"] < medians["este"]
    for group in groups:
        assert group["missing"] == 0 and group["count"] == group["rows"]
        assert group["std"] > 0 and group["small_sample"] is False
    assert summary["omitted"] == {"groups": 0, "rows": 0, "observed": 0}
    assert summary["overall"]["count"] == 300


async def test_limits_groups_and_reports_the_omission(registry: ToolRegistry) -> None:
    result = await run(registry, "monto", "region", max_groups=2)
    summary = result.result
    assert isinstance(summary, dict)
    assert summary["total_groups"] == 3 and summary["shown_groups"] == 2
    smallest = 300 - sum(group["rows"] for group in summary["groups"])
    assert summary["omitted"] == {"groups": 1, "rows": smallest, "observed": smallest}
    assert result.warnings == [
        f"Showing the 2 largest of 3 groups; 1 group(s) with {smallest} row(s) were omitted."
    ]


@pytest.mark.parametrize("value", [0, 6, "3", True, 2.5])
async def test_rejects_group_limits_outside_the_configured_cap(
    registry: ToolRegistry, value: object
) -> None:
    result = await run(registry, "monto", "region", max_groups=value)
    assert result.status == "FAILED"
    assert "between 1 and 5" in result.warnings[0]


async def test_requires_numeric_value_and_categorical_group(registry: ToolRegistry) -> None:
    assert (await run(registry, "region", "monto")).status == "SKIPPED"
    assert (await run(registry, "monto", "girado")).status == "SKIPPED"
    assert (await run(registry, "monto")).status == "FAILED"


def test_counts_missing_values_unlabelled_rows_and_small_groups() -> None:
    values = np.asarray([1.0, 2.0, np.nan, 4.0, 5.0, 5.0, 5.0, 7.0, np.nan])
    labels = label_array(["a", "a", "a", "b", "c", "c", "c", None, None])
    summary = grouped_summary(values, labels, max_groups=2, minimum_sample_size=3)
    groups = {group["label"]: group for group in summary["groups"]}
    assert list(groups) == ["a", "c"]
    assert groups["a"]["rows"] == 3 and groups["a"]["count"] == 2 and groups["a"]["missing"] == 1
    assert groups["a"]["small_sample"] is True
    assert groups["c"]["std"] == 0 and groups["c"]["small_sample"] is False
    assert summary["omitted"] == {"groups": 1, "rows": 1, "observed": 1}
    assert summary["missing_group"] == {"rows": 2, "observed": 1}
    assert summary["overall"]["count"] == 7
