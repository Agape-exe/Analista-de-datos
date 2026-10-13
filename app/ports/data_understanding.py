from typing import Protocol

from app.application.dto.analysis_input import AnalysisInput
from app.application.dto.data_understanding import DataUnderstandingResult


class DataUnderstanding(Protocol):
    """Understand a source locally, independently of CSV, pandas or an LLM."""

    async def understand(self, analysis_input: AnalysisInput) -> DataUnderstandingResult: ...
