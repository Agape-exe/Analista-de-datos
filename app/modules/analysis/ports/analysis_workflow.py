from typing import Protocol

from app.shared.contracts.analysis_input import AnalysisInput
from app.shared.domain.models.report import AnalysisReport


class AnalysisWorkflow(Protocol):
    """Application-facing execution boundary, independent of LangGraph."""

    async def run(self, analysis_input: AnalysisInput) -> AnalysisReport: ...
