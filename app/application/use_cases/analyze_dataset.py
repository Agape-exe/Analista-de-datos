from app.application.dto.analysis_input import AnalysisInput
from app.domain.models.report import AnalysisReport
from app.ports.analysis_workflow import AnalysisWorkflow
from app.ports.repository import AnalysisRepository


class AnalyzeDataset:
    def __init__(
        self, workflow: AnalysisWorkflow, repository: AnalysisRepository | None = None
    ) -> None:
        self.workflow = workflow
        self.repository = repository

    async def execute(self, analysis_input: AnalysisInput) -> AnalysisReport:
        report = await self.workflow.run(analysis_input)
        if self.repository is not None:
            await self.repository.save(report)
        return report
