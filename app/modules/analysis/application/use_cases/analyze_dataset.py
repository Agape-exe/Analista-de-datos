from app.modules.analysis.ports.analysis_workflow import AnalysisWorkflow
from app.modules.reporting.ports.repository import AnalysisRepository
from app.shared.contracts.analysis_input import AnalysisInput
from app.shared.domain.models.report import AnalysisReport


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
