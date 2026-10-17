from typing import Protocol

from app.shared.domain.models.report import AnalysisReport


class ReportRenderer(Protocol):
    """Render a structured report into a presentation format."""

    def render(self, report: AnalysisReport) -> str: ...
