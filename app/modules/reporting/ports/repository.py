from typing import Protocol

from app.shared.domain.models.report import AnalysisReport


class AnalysisRepository(Protocol):
    """Persist reports independently of a database implementation."""

    async def save(self, report: AnalysisReport) -> None: ...

    async def get(self, run_id: str) -> AnalysisReport | None: ...
