from app.application.dto.analysis_input import AnalysisInput
from app.domain.models.report import AnalysisReport
from app.ports.analysis_workflow import AnalysisWorkflow


class AnalyzeDataset:
    """Delegate execution through a workflow port, without framework coupling."""

    def __init__(self, workflow: AnalysisWorkflow) -> None:
        self.workflow = workflow

    async def execute(self, analysis_input: AnalysisInput) -> AnalysisReport:
        return await self.workflow.run(analysis_input)
