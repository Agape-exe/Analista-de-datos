from pathlib import Path

from app.agents.planner import PlannerAgent
from app.application.dto.agent import AgentContext
from app.application.dto.analysis_input import AnalysisInput, resolve_configuration
from app.application.dto.llm import LLMRequest, LLMResponse
from app.config.settings import Settings
from app.domain.enums.semantic_type import SemanticType
from app.domain.enums.statuses import DictionarySource
from app.domain.models.analysis import AssociationResult
from app.domain.models.data_dictionary import DataDictionary, DataDictionaryEntry
from app.domain.models.dataset import ColumnProfile, DatasetProfile


class MustNotCallLLM:
    async def generate(self, request: LLMRequest) -> LLMResponse:
        raise AssertionError("Planner must not call the LLM")


def context(
    columns: list[tuple[str, SemanticType]],
    *,
    question: str | None = None,
    row_count: int = 40,
    configuration: dict[str, object] | None = None,
    dictionary: DataDictionary | None = None,
) -> AgentContext:
    analysis_input = AnalysisInput(
        source={"kind": "csv", "path": Path("metadata-only.csv")},
        user_question=question,
        configuration=configuration or {},
    )
    settings = Settings(_env_file=None)
    profile = DatasetProfile(
        dataset_id="dataset-plan",
        row_count=row_count,
        columns=[
            ColumnProfile(
                column_name=name,
                data_type="number" if semantic == SemanticType.NUMERIC else "string",
                semantic_type=semantic,
                missing_count=0,
                unique_count=min(row_count, 5),
            )
            for name, semantic in columns
        ],
    )
    return AgentContext(
        run_id="plan-run",
        input=analysis_input,
        configuration=resolve_configuration(settings, analysis_input.configuration),
        dataset_id=profile.dataset_id,
        dataset_profile=profile,
        data_dictionary=dictionary,
    )


async def test_planner_generates_numeric_analysis_plan() -> None:
    result = await PlannerAgent(MustNotCallLLM()).run(
        context([("height", SemanticType.NUMERIC), ("weight", SemanticType.NUMERIC)])
    )

    assert result.status == "SUCCESS"
    assert result.update.analysis_plan is not None
    assert [step.request.method for step in result.update.analysis_plan.steps] == [
        "pearson",
        "spearman",
        "correlation_without_outliers",
    ]
    assert result.update.analysis_plan.steps[-1].depends_on == [
        result.update.analysis_plan.steps[0].step_id
    ]
    assert all(
        step.request.dataset_id == "dataset-plan" for step in result.update.analysis_plan.steps
    )


async def test_planner_selects_categorical_tools() -> None:
    result = await PlannerAgent(MustNotCallLLM()).run(
        context([("segment", SemanticType.CATEGORICAL), ("region", SemanticType.CATEGORICAL)])
    )

    assert result.status == "SUCCESS"
    assert result.update.analysis_plan is not None
    assert [step.request.method for step in result.update.analysis_plan.steps] == [
        "chi_square",
        "cramers_v",
    ]


async def test_planner_selects_anova() -> None:
    result = await PlannerAgent(MustNotCallLLM()).run(
        context([("segment", SemanticType.CATEGORICAL), ("spend", SemanticType.NUMERIC)])
    )

    assert result.status == "SUCCESS"
    assert result.update.analysis_plan is not None
    step = result.update.analysis_plan.steps[0]
    assert step.request.method == "anova_one_way"
    assert step.request.variables == ["segment", "spend"]


async def test_planner_selects_partial_correlation() -> None:
    result = await PlannerAgent(MustNotCallLLM()).run(
        context(
            [
                ("income", SemanticType.NUMERIC),
                ("spend", SemanticType.NUMERIC),
                ("age", SemanticType.NUMERIC),
            ],
            question="Evaluar income y spend controlando por age.",
        )
    )

    assert result.status == "SUCCESS"
    assert result.update.analysis_plan is not None
    partial = next(
        step
        for step in result.update.analysis_plan.steps
        if step.request.method == "partial_correlation"
    )
    assert partial.request.variables == ["income", "spend"]
    assert partial.request.parameters == {"control_variable": "age"}


async def test_planner_detects_exact_numeric_control_variable() -> None:
    result = await PlannerAgent(MustNotCallLLM()).run(
        context(
            [
                ("income", SemanticType.NUMERIC),
                ("spend", SemanticType.NUMERIC),
                ("age", SemanticType.NUMERIC),
            ],
            question="Evaluar income y spend, ajustando por age.",
        )
    )

    assert result.update.analysis_plan is not None
    partial = next(
        step
        for step in result.update.analysis_plan.steps
        if step.request.method == "partial_correlation"
    )
    assert partial.request.parameters == {"control_variable": "age"}


async def test_planner_rejects_partial_control_name_match() -> None:
    result = await PlannerAgent(MustNotCallLLM()).run(
        context(
            [
                ("income", SemanticType.NUMERIC),
                ("spend", SemanticType.NUMERIC),
                ("age", SemanticType.NUMERIC),
            ],
            question="Evaluar income y spend controlando por ageless.",
        )
    )

    assert result.update.analysis_plan is not None
    assert all(
        step.request.method != "partial_correlation" for step in result.update.analysis_plan.steps
    )


async def test_planner_prioritizes_user_question() -> None:
    result = await PlannerAgent(MustNotCallLLM()).run(
        context(
            [
                ("age", SemanticType.NUMERIC),
                ("income", SemanticType.NUMERIC),
                ("spend", SemanticType.NUMERIC),
            ],
            question="¿Qué asociación existe entre income y spend?",
        )
    )

    assert result.status == "SUCCESS"
    assert result.update.analysis_plan is not None
    assert result.update.analysis_plan.hypotheses[0].variables == ["income", "spend"]


async def test_planner_bounds_large_numeric_candidate_selection() -> None:
    columns = [(f"metric_{number:03}", SemanticType.NUMERIC) for number in range(100)] + [
        ("zeta_income", SemanticType.NUMERIC),
        ("zeta_spend", SemanticType.NUMERIC),
    ]
    value = context(
        columns,
        question="Evaluar la asociación entre zeta_income y zeta_spend.",
        configuration={"analysis": {"max_hypotheses": 1, "max_tool_calls": 2}},
    )
    planner = PlannerAgent(MustNotCallLLM())

    first = await planner.run(value)
    second = await planner.run(value)

    assert first.update.analysis_plan is not None
    assert first.update.analysis_plan == second.update.analysis_plan
    assert len(first.update.analysis_plan.hypotheses) == 1
    assert len(first.update.analysis_plan.steps) == 2


async def test_planner_prioritizes_late_explicit_columns_in_bounded_pool() -> None:
    columns = [(f"metric_{number:03}", SemanticType.NUMERIC) for number in range(100)] + [
        ("zeta_income", SemanticType.NUMERIC),
        ("zeta_spend", SemanticType.NUMERIC),
    ]
    result = await PlannerAgent(MustNotCallLLM()).run(
        context(
            columns,
            question="Evaluar la asociación entre zeta_income y zeta_spend.",
        )
    )

    assert result.update.analysis_plan is not None
    assert result.update.analysis_plan.hypotheses[0].variables == [
        "zeta_income",
        "zeta_spend",
    ]


async def test_planner_respects_fast_mode_limits() -> None:
    result = await PlannerAgent(MustNotCallLLM()).run(
        context(
            [
                ("age", SemanticType.NUMERIC),
                ("income", SemanticType.NUMERIC),
                ("segment", SemanticType.CATEGORICAL),
                ("region", SemanticType.CATEGORICAL),
            ],
            configuration={"analysis": {"max_hypotheses": 2, "max_tool_calls": 2}},
        )
    )

    assert result.status == "SUCCESS"
    assert result.update.analysis_plan is not None
    assert len(result.update.analysis_plan.hypotheses) <= 2
    assert len(result.update.analysis_plan.steps) == 2


async def test_planner_skips_insufficient_data() -> None:
    result = await PlannerAgent(MustNotCallLLM()).run(
        context([("age", SemanticType.NUMERIC), ("income", SemanticType.NUMERIC)], row_count=3)
    )

    assert result.status == "SKIPPED"
    assert result.update.analysis_plan is None
    assert "minimum sample size" in result.warnings[0]


async def test_planner_produces_valid_analysis_plan() -> None:
    result = await PlannerAgent(MustNotCallLLM()).run(
        context([("segment", SemanticType.CATEGORICAL), ("spend", SemanticType.NUMERIC)])
    )

    assert result.status == "SUCCESS"
    assert result.update.analysis_plan is not None
    plan = result.update.analysis_plan
    hypothesis_ids = {hypothesis.hypothesis_id for hypothesis in plan.hypotheses}
    assert len(hypothesis_ids) == len(plan.hypotheses)
    assert len({step.step_id for step in plan.steps}) == len(plan.steps)
    assert all(step.hypothesis_id in hypothesis_ids for step in plan.steps)
    assert type(plan).model_validate_json(plan.model_dump_json()) == plan


async def test_planner_skips_when_tool_budget_is_zero() -> None:
    result = await PlannerAgent(MustNotCallLLM()).run(
        context(
            [("age", SemanticType.NUMERIC), ("income", SemanticType.NUMERIC)],
            configuration={"analysis": {"max_tool_calls": 0}},
        )
    )

    assert result.status == "SKIPPED"
    assert "budget is zero" in result.warnings[0]


async def test_planner_omits_identifier_text_and_temporal_columns() -> None:
    result = await PlannerAgent(MustNotCallLLM()).run(
        context(
            [
                ("record_id", SemanticType.IDENTIFIER),
                ("comment", SemanticType.TEXT),
                ("created_at", SemanticType.TEMPORAL),
                ("income", SemanticType.NUMERIC),
                ("spend", SemanticType.NUMERIC),
            ]
        )
    )

    assert result.status == "SUCCESS"
    assert result.update.analysis_plan is not None
    assert {
        variable
        for step in result.update.analysis_plan.steps
        for variable in step.request.variables
    } == {
        "income",
        "spend",
    }


async def test_planner_ignores_incompatible_control_and_conflicting_dictionary_type() -> None:
    dictionary = DataDictionary(
        entries=[
            DataDictionaryEntry(
                column_name="segment",
                semantic_type="numeric",
                source=DictionarySource.MANUAL,
            )
        ]
    )
    result = await PlannerAgent(MustNotCallLLM()).run(
        context(
            [
                ("income", SemanticType.NUMERIC),
                ("spend", SemanticType.NUMERIC),
                ("segment", SemanticType.CATEGORICAL),
            ],
            question="Evaluar income y spend controlando por segment.",
            dictionary=dictionary,
        )
    )

    assert result.status == "SUCCESS"
    assert result.update.analysis_plan is not None
    assert all(
        step.request.method != "partial_correlation" for step in result.update.analysis_plan.steps
    )
    assert any("conflicts" in warning for warning in result.warnings)


async def test_planner_is_deterministic_and_contains_no_raw_rows() -> None:
    value = context(
        [
            ("age", SemanticType.NUMERIC),
            ("income", SemanticType.NUMERIC),
            ("segment", SemanticType.CATEGORICAL),
        ]
    )
    planner = PlannerAgent(MustNotCallLLM())

    first = await planner.run(value)
    second = await planner.run(value)

    assert first.update.analysis_plan == second.update.analysis_plan
    assert "table" not in first.update.analysis_plan.model_dump_json()
    assert "table" not in value.model_dump()


async def test_planner_omits_anova_when_metadata_proves_singleton_groups() -> None:
    value = context([("group", SemanticType.CATEGORICAL), ("outcome", SemanticType.NUMERIC)])
    value.dataset_profile.columns[0].unique_count = value.dataset_profile.row_count

    result = await PlannerAgent(MustNotCallLLM()).run(value)

    assert result.status == "SKIPPED"
    assert result.update.analysis_plan is None
    assert any("each group requires at least two" in warning for warning in result.warnings)


async def test_anova_summary_requests_stay_bounded_and_prioritize_question() -> None:
    columns = [(f"group_{i:03}", SemanticType.CATEGORICAL) for i in range(100)] + [
        (f"value_{i:03}", SemanticType.NUMERIC) for i in range(100)
    ]
    value = context(columns, question="Compare group_099 and value_099.")
    calls: list[list[tuple[str, str]]] = []

    def summarize(dataset_id, pairs):
        assert dataset_id == value.dataset_id
        calls.append(pairs)
        return {}

    await PlannerAgent(MustNotCallLLM(), summarize_anova=summarize).run(value)

    assert len(calls) == 1 and len(calls[0]) == 16
    assert ("group_099", "value_099") in calls[0]


async def test_constant_numeric_columns_are_excluded_before_planning():
    value = context(
        [
            ("year", SemanticType.NUMERIC),
            ("amount", SemanticType.NUMERIC),
            ("interest", SemanticType.NUMERIC),
        ]
    )
    next(
        item for item in value.dataset_profile.columns if item.column_name == "year"
    ).unique_count = 1
    result = await PlannerAgent(MustNotCallLLM()).run(value)
    assert result.status == "SUCCESS"
    assert all("year" not in step.request.variables for step in result.update.analysis_plan.steps)
    assert any("constant numeric column" in warning for warning in result.warnings)


async def test_continuous_numeric_pool_keeps_priority_over_calendar_codes():
    value = context(
        [
            ("a_year", SemanticType.NUMERIC),
            ("tax", SemanticType.NUMERIC),
            ("interest", SemanticType.NUMERIC),
            ("total", SemanticType.NUMERIC),
        ]
    )
    for item in value.dataset_profile.columns:
        item.data_type = "Int64" if item.column_name == "a_year" else "Float64"
    result = await PlannerAgent(MustNotCallLLM()).run(value)
    steps = result.update.analysis_plan.steps
    correlation = next(item for item in steps if item.request.method == "pearson")
    assert correlation.request.variables == ["interest", "tax"]
    identity = next(item for item in steps if item.request.method == "additive_identity")
    assert identity.request.variables == ["interest", "tax", "total"]
