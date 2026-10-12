from typing import Annotated

from pydantic import Field

from app.domain.models.base import DomainModel

Rate = Annotated[float, Field(ge=0, le=1)]
Duration = Annotated[float, Field(ge=0)]
Count = Annotated[int, Field(ge=0)]


class ExperimentMetrics(DomainModel):
    precision: Rate | None = None
    recall: Rate | None = None
    f1_score: Rate | None = None
    false_positive_rate: Rate | None = None
    pattern_detection_rate: Rate | None = None
    spurious_detection_rate: Rate | None = None
    hypothesis_consistency: Rate | None = None
    insight_consistency: Rate | None = None
    tool_selection_consistency: Rate | None = None
    conclusion_agreement: Rate | None = None
    semantic_similarity: Rate | None = None
    total_response_time: Duration | None = None
    time_to_first_insight: Duration | None = None
    llm_calls: Count | None = None
    tool_calls: Count | None = None
    tokens_used: Count | None = None
    iterations: Count | None = None
    profiling_time: Duration | None = None
    analytics_time: Duration | None = None
    completion_rate: Rate | None = None
    human_intervention_rate: Rate | None = None
    valid_tool_selection_rate: Rate | None = None
    invalid_analysis_rate: Rate | None = None
