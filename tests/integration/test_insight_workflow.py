from app.modules.analysis.adapters.orchestration.graph import LangGraphWorkflow
from app.modules.reporting.application.agents.insight import InsightAgent
from app.shared.adapters.observability.telemetry import InstrumentedLLMProvider
from app.shared.config.settings import Settings
from app.shared.contracts.agent import AgentResult, AgentUpdate
from app.shared.contracts.analysis_input import AnalysisInput
from app.shared.contracts.llm import LLMResponse
from app.shared.domain.models.analysis import AnalysisResult
from app.shared.domain.models.evidence import Evidence, RelationshipAssessment


class FixtureEvidenceAgent:
    name = "FixtureEvidence"

    async def run(self, context):
        return AgentResult(
            agent_name=self.name,
            status="SUCCESS",
            update=AgentUpdate(
                analysis_results=[
                    AnalysisResult(
                        analysis_id="r1",
                        method="fixture",
                        variables=["x", "y"],
                        status="SUCCESS",
                        result={"coefficient": 0.2},
                    )
                ],
                evidence=[Evidence(evidence_id="e1", analysis_id="r1", description="fixture")],
                relationship_assessments=[
                    RelationshipAssessment(
                        variables=["x", "y"], evidence_ids=["e1"], potentially_spurious=None
                    )
                ],
            ),
        )


class FixtureProvider:
    async def generate(self, request):
        return LLMResponse(content='{"insight_ids": ["insight_1"]}', tokens_used=10)


async def test_workflow_report_preserves_evidence_and_actual_metrics():
    workflow = LangGraphWorkflow(
        Settings(_env_file=None),
        [
            FixtureEvidenceAgent(),
            InsightAgent(InstrumentedLLMProvider(FixtureProvider()), use_llm=True),
        ],
    )
    report = await workflow.run(AnalysisInput(source={"kind": "csv", "path": "not-read.csv"}))
    assert report.status == "SUCCESS"
    assert report.metrics.llm_calls == 1
    assert report.metrics.tokens_used == 10
    assert 0 <= report.metrics.time_to_first_insight <= report.metrics.total_response_time
    assert report.evidence[0].analysis_id == "r1"
    assert report.relationship_assessments[0].potentially_spurious is None
    assert any(event["kind"] == "llm" for event in report.execution_trace)
