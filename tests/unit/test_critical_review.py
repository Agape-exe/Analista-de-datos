import pytest

from app.agents.critic import CriticAgent
from app.application.dto.agent import AgentContext
from app.application.dto.analysis_input import AnalysisInput, resolve_configuration
from app.application.services.insights import generate_insights
from app.config.settings import Settings
from app.domain.models.analysis import AnalysisResult


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
