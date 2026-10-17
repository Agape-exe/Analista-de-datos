from typing import Protocol

from app.shared.contracts.analysis_input import AnalysisInput
from app.shared.contracts.data_understanding import DataUnderstandingResult


class DataUnderstanding(Protocol):
    """Understand a source locally, independently of CSV, pandas or an LLM."""

    async def understand(self, analysis_input: AnalysisInput) -> DataUnderstandingResult: ...
