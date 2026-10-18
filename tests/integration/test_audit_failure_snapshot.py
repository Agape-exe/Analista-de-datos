import asyncio

from app.modules.analysis.adapters.orchestration.graph import LangGraphWorkflow
from app.modules.analysis.application.agents.analyst import AnalysisAgent
from app.shared.adapters.llm.disabled import DisabledLLMProvider
from app.shared.adapters.observability.telemetry import InstrumentedAnalyticsTool
from app.shared.application.tool_registry import ToolRegistry
from app.shared.config.settings import Settings
from app.shared.contracts.agent import AgentResult, AgentUpdate
from app.shared.contracts.analysis_input import AnalysisInput
from app.shared.domain.models.analysis import AnalysisPlan, AnalysisStep, ToolRequest


class SnapshotAgent:
    name = "Planner"

    async def run(self, context):
        return AgentResult(
            agent_name=self.name,
            status="SUCCESS",
            update=AgentUpdate(dataset_id="snapshot-dataset", analysis_plan=AnalysisPlan()),
        )


class SlowAgent:
    name = "Analysis"

    async def run(self, context):
        await asyncio.sleep(1)


async def test_timeout_preserves_completed_snapshot_and_failed_stage():
    workflow = LangGraphWorkflow(
        Settings(_env_file=None, performance={"timeout_seconds": 0.02}),
        [SnapshotAgent(), SlowAgent()],
    )
    report = await workflow.run(
        AnalysisInput(
            source={"kind": "csv", "path": "not-read.csv"}, user_question="Keep this question"
        )
    )
    assert report.status == "FAILED" and report.user_question == "Keep this question"
    assert report.dataset_id == "snapshot-dataset" and report.analysis_plan is not None
    assert report.stage_statuses == {"Planner": "SUCCESS", "Analysis": "FAILED"}
    assert report.execution_trace[-1]["agent"] == "Analysis"
    assert report.execution_trace[-1]["status"] == "FAILED"


async def test_failed_tool_links_result_and_blocked_step_is_not_counted_as_call():
    class BrokenTool:
        name = "broken"

        def supports(self, request):
            return request.method == self.name

        async def execute(self, request):
            raise ValueError("calculation failed")

    class PlanAgent:
        name = "Planner"

        async def run(self, context):
            request = ToolRequest(dataset_id="ds", method="broken")
            return AgentResult(
                agent_name=self.name,
                status="SUCCESS",
                update=AgentUpdate(
                    dataset_id="ds",
                    analysis_plan=AnalysisPlan(
                        steps=[
                            AnalysisStep(step_id="first", request=request),
                            AnalysisStep(
                                step_id="dependent", request=request, depends_on=["first"]
                            ),
                        ]
                    ),
                ),
            )

    tools = ToolRegistry()
    tools.register(InstrumentedAnalyticsTool(BrokenTool()))
    report = await LangGraphWorkflow(
        Settings(_env_file=None),
        [
            PlanAgent(),
            AnalysisAgent(DisabledLLMProvider(), tools),
        ],
    ).run(AnalysisInput(source={"kind": "stored", "dataset_id": "ds"}))
    assert report.status == "FAILED" and report.metrics.tool_calls == 1
    assert [item.status for item in report.analysis_results] == ["FAILED", "SKIPPED"]
    [tool] = [event for event in report.execution_trace if event["kind"] == "tool"]
    [omission] = [event for event in report.execution_trace if event["kind"] == "step"]
    assert tool["analysis_id"] == report.analysis_results[0].analysis_id
    assert tool["warnings"] == report.analysis_results[0].warnings
    assert omission["step_id"] == "dependent" and omission["status"] == "SKIPPED"
