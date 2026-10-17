from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class AnovaGroupSummary:
    """Aggregate complete-case counts; contains no category labels or local rows."""

    group_count: int
    minimum_group_size: int


AnovaGroupSummaries = dict[tuple[str, str], AnovaGroupSummary]
AnovaGroupSummarizer = Callable[[str, list[tuple[str, str]]], AnovaGroupSummaries]
