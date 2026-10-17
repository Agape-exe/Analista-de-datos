from pathlib import Path

import pytest

from app.bootstrap import build_use_case
from app.shared.config.settings import Settings
from app.shared.contracts.analysis_input import AnalysisInput


def input_for(path: Path, categories: list[str], outcomes: list[object]) -> AnalysisInput:
    rows = ["group,outcome"]
    rows.extend(
        f"{category},{outcome if outcome is not None else ''}"
        for category, outcome in zip(categories, outcomes, strict=True)
    )
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return AnalysisInput(
        source={"kind": "csv", "path": path},
        data_dictionary={
            "entries": [
                {"column_name": "group", "semantic_type": "categorical", "source": "manual"},
                {"column_name": "outcome", "semantic_type": "numeric", "source": "manual"},
            ]
        },
    )


@pytest.mark.parametrize(
    "categories,outcomes",
    [
        ([f"g{i}" for i in range(40)], list(range(40))),
        (["a"] * 39 + ["b"], list(range(40))),
        (["a"] * 20 + ["b"] * 20, list(range(21)) + [None] * 19),
        (["a"] * 40, list(range(40))),
        (["a"] * 38 + ["b"] * 2, list(range(38)) + [None] * 2),
    ],
    ids=[
        "all-singletons",
        "one-singleton",
        "singleton-after-missing",
        "one-group",
        "one-complete-group",
    ],
)
async def test_workflow_omits_ineligible_anova_without_executing_it(
    tmp_path: Path, categories: list[str], outcomes: list[object]
) -> None:
    value = input_for(tmp_path / "invalid.csv", categories, outcomes)

    report = await build_use_case(Settings(_env_file=None)).execute(value)

    assert report.status == "SKIPPED"
    assert report.stage_statuses["DataUnderstanding"] == "SUCCESS"
    assert report.stage_statuses["Planner"] == report.stage_statuses["Analysis"] == "SKIPPED"
    assert report.analysis_results == []
    assert report.metrics.tool_calls == 0
    assert not report.errors
    assert any("ANOVA omitted" in warning for warning in report.warnings)


@pytest.mark.parametrize(
    "categories,outcomes",
    [
        (["a"] * 38 + ["b"] * 2, list(range(40))),
        (["a"] * 10 + ["b"] * 10 + ["c"] * 20, list(range(20)) + [None] * 20),
    ],
    ids=["two-is-sufficient", "empty-group-excluded-by-complete-cases"],
)
async def test_workflow_keeps_valid_anova_with_complete_groups(
    tmp_path: Path, categories: list[str], outcomes: list[object]
) -> None:
    value = input_for(tmp_path / "valid.csv", categories, outcomes)

    report = await build_use_case(Settings(_env_file=None)).execute(value)

    assert report.stage_statuses["Planner"] == report.stage_statuses["Analysis"] == "SUCCESS"
    assert len(report.analysis_results) == 1
    result = report.analysis_results[0]
    assert result.method == "anova_one_way" and result.status == "SUCCESS"
    assert result.metadata["group_count"] == 2
    assert result.sample_size == sum(outcome is not None for outcome in outcomes)
    assert result.p_value is not None and result.effect_size is not None
    assert report.metrics.tool_calls == 1
    assert report.status == "SUCCESS"
    assert report.insights and report.relationship_assessments
    assert all(item.potentially_spurious is None for item in report.relationship_assessments)
    assert not report.errors


async def test_fast_mode_uses_next_valid_anova_after_omitting_sparse_pair(tmp_path: Path) -> None:
    rows = ["group,a_sparse,z_valid"]
    for index in range(60):
        group = "a" if index < 30 else "b"
        sparse = index if index <= 30 else ""
        rows.append(f"{group},{sparse},{index * 2 + index % 3}")
    path = tmp_path / "fallback.csv"
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    report = await build_use_case(Settings(_env_file=None)).execute(
        AnalysisInput(source={"kind": "csv", "path": path})
    )

    anova = [item for item in report.analysis_results if item.method == "anova_one_way"]
    assert len(anova) == 1
    assert anova[0].variables == ["group", "z_valid"] and anova[0].status == "SUCCESS"
    assert report.stage_statuses["Analysis"] == "SUCCESS"
    assert report.metrics.tool_calls == 5
    assert any(
        "'a_sparse'" in warning and "ANOVA omitted" in warning for warning in report.warnings
    )
    assert not report.errors
