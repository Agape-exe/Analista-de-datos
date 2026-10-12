from typing import Protocol

from app.domain.models.analysis import AnalysisResult, ToolRequest


class AnalyticsTool(Protocol):
    """Deterministic analytical operation returning the shared result contract."""

    name: str

    def supports(self, request: ToolRequest) -> bool: ...

    async def execute(self, request: ToolRequest) -> AnalysisResult: ...
