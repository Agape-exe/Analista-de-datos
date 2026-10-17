import pytest

from app.modules.critical_review.application.agents.critic import CriticAgent
from app.modules.reporting.application.services.insights import generate_insights
from app.shared.config.settings import Settings
from app.shared.contracts.agent import AgentContext
from app.shared.contracts.analysis_input import AnalysisInput, resolve_configuration
from app.shared.domain.models.analysis import AnalysisResult


class NoLLM:
    async def generate(self, request):
        raise AssertionError("No LLM calls")


def context(results):
    value = AnalysisInput(source={"kind": "csv", "path": "unused.csv"})
    return AgentContext(
        run_id="review",
        input=value,
        configuration=resolve_configuration(Settings(_env_file=None), value.configuration),
        analysis_results=results,
    )


async def test_measured_pearson_spearman_comparison_is_traceable_but_indeterminate():
    results = [
        AnalysisResult(
            method=method,
            status="SUCCESS",
            variables=["x", "y"],
            effect_size=coefficient,
            result={"correlation": coefficient},
            sample_size=40,
        )
        for method, coefficient in [("pearson", 0.8), ("spearman", 0.2)]
    ]
    output = await CriticAgent(NoLLM()).run(context(results))
    assert output.status == "SUCCESS"
    assert {item.analysis_id for item in output.update.evidence} == {
        item.analysis_id for item in results
    }
    assert "Pearson-Spearman" in output.update.evidence[1].description
    assessment = output.update.relationship_assessments[0]
    assert assessment.potentially_spurious is None
    insights, warnings = generate_insights(
        results, output.update.evidence, output.update.relationship_assessments
    )
    assert insights and not warnings
    assert "indeterminada" in insights[0].statement


@pytest.mark.parametrize(
    ("method", "variables", "payload", "effect_size", "expected_text"),
    [
        (
            "chi_square",
            ["segment", "outcome"],
            {"chi_square": 12.0},
            None,
            "chi-cuadrado",
        ),
        (
            "cramers_v",
            ["segment", "outcome"],
            {"cramers_v": 0.55},
            0.55,
            "V de Cramér",
        ),
        (
            "anova_one_way",
            ["group", "score"],
            {"f_statistic": 9.5},
            0.32,
            "ANOVA",
        ),
    ],
)
async def test_measured_mixed_statistics_are_traceable_and_indeterminate(
    method, variables, payload, effect_size, expected_text
):
    result = AnalysisResult(
        analysis_id=method,
        method=method,
        status="SUCCESS",
        variables=variables,
        result=payload,
        effect_size=effect_size,
        p_value=0.01,
        sample_size=40,
    )

    output = await CriticAgent(NoLLM()).run(context([result]))

    assert output.status == "SUCCESS"
    evidence = output.update.evidence[0]
    assessment = output.update.relationship_assessments[0]
    assert evidence.analysis_id == result.analysis_id
    assert expected_text in evidence.description
    assert assessment.evidence_ids == [evidence.evidence_id]
    assert assessment.potentially_spurious is None

    insights, warnings = generate_insights(
        [result], output.update.evidence, output.update.relationship_assessments
    )
    assert not warnings
    assert insights[0].evidence_ids == [evidence.evidence_id]
    assert expected_text in insights[0].statement
    assert any("causalidad" in item for item in insights[0].limitations)


async def test_critical_review_preserves_statistical_warnings_in_traceable_insight():
    result = AnalysisResult(
        analysis_id="chi-low-expected",
        method="chi_square",
        status="SUCCESS",
        variables=["segment", "outcome"],
        result={"chi_square": 0.2},
        p_value=0.8,
        sample_size=40,
        warnings=["1 expected cell is below 5; chi-square approximation may be unreliable."],
    )

    output = await CriticAgent(NoLLM()).run(context([result]))
    evidence = output.update.evidence[0]
    insights, warnings = generate_insights(
        [result], output.update.evidence, output.update.relationship_assessments
    )

    assert not warnings
    assert result.warnings[0] in evidence.limitations
    assert result.warnings[0] in insights[0].limitations


@pytest.mark.parametrize(
    "results",
    [
        [],
        [AnalysisResult(method="pearson", status="SKIPPED", variables=["x", "y"])],
        [AnalysisResult(method="pearson", status="SUCCESS", variables=["x", "y"])],
        [AnalysisResult(method="anova_one_way", status="SUCCESS", variables=["x", "y"], result={})],
    ],
)
async def test_absent_or_unmeasured_results_never_create_evidence_or_insights(results):
    output = await CriticAgent(NoLLM()).run(context(results))
    assert output.status == "SKIPPED"
    assert output.update.evidence is None and output.update.relationship_assessments is None
    assert generate_insights(results, [], [])[0] == []
