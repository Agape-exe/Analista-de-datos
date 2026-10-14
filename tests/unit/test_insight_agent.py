import pytest

from app.agents.insight import InsightAgent
from app.application.dto.agent import AgentContext
from app.application.dto.analysis_input import AnalysisConfiguration, resolve_configuration
from app.application.dto.llm import LLMResponse
from app.config.settings import Settings
from app.domain.models.analysis import AnalysisResult
from app.domain.models.evidence import Evidence, RelationshipAssessment


class Provider:
    def __init__(self, content='{"insight_ids": ["insight_1"]}'):
        self.content = content

    async def generate(self, request):
        return LLMResponse(content=self.content, tokens_used=12)


def context():
    return AgentContext(
        run_id="fixture",
        input={"source": {"kind": "csv", "path": "fixture.csv"}},
        configuration=resolve_configuration(Settings(_env_file=None), AnalysisConfiguration()),
        analysis_results=[
            AnalysisResult(
                analysis_id="r1",
                method="pearson",
                variables=["x", "y"],
                status="SUCCESS",
                result={"coefficient": 0.72},
                sample_size=20,
            )
        ],
        evidence=[Evidence(evidence_id="e1", analysis_id="r1", description="test fixture")],
        relationship_assessments=[
            RelationshipAssessment(
                variables=["x", "y"],
                evidence_ids=["e1"],
                potentially_spurious=True,
                rationale="Fixture assessment",
            )
        ],
    )


async def test_evidence_linked_template_does_not_call_llm():
    result = await InsightAgent(Provider()).run(context())
    assert result.status == "SUCCESS"
    assert "0.72" in result.update.insights[0].statement
    assert result.update.insights[0].evidence_ids == ["e1"]
    assert result.update.metrics.llm_calls is None
    assert "no demuestra causalidad" in result.update.insights[0].statement


@pytest.mark.parametrize("kind", ["missing", "failed", "wrong_variables"])
async def test_invalid_evidence_is_not_explained(kind):
    value = context()
    if kind == "missing":
        value.evidence = []
    elif kind == "failed":
        value.analysis_results = [
            AnalysisResult(analysis_id="r1", method="pearson", status="FAILED")
        ]
    else:
        value.analysis_results[0].variables = ["a", "b"]
    result = await InsightAgent(Provider()).run(value)
    assert result.status == "SKIPPED"
    assert result.update.insights == []
    assert result.warnings


async def test_llm_can_only_prioritize_existing_insights():
    result = await InsightAgent(Provider(), use_llm=True).run(context())
    assert result.update.metrics.llm_calls == 1
    assert result.update.metrics.tokens_used == 12
    malicious = await InsightAgent(Provider('{"insight_ids": ["invented"]}'), use_llm=True).run(
        context()
    )
    assert malicious.warnings
    assert malicious.update.insights[0].insight_id == "insight_1"


async def test_indeterminate_assessment_stays_indeterminate():
    value = context()
    value.relationship_assessments[0].potentially_spurious = None
    result = await InsightAgent(Provider()).run(value)
    assert "indeterminada" in result.update.insights[0].statement
