from collections.abc import Mapping
from typing import Any

from app.shared.domain.enums.statuses import AnalysisStatus
from app.shared.domain.models.metrics import ExperimentMetrics
from app.shared.domain.models.report import AnalysisReport


def assemble_report(state: Mapping[str, Any], metrics: ExperimentMetrics) -> AnalysisReport:
    """Preserve evidence and omissions; success requires every recorded stage to succeed."""
    statuses = state.get("stage_statuses", {})
    errors = state.get("errors", [])
    if errors or AnalysisStatus.FAILED in statuses.values():
        status = AnalysisStatus.FAILED
    elif statuses and all(value == AnalysisStatus.SUCCESS for value in statuses.values()):
        status = AnalysisStatus.SUCCESS
    else:
        status = AnalysisStatus.SKIPPED
    configuration = state.get("configuration")
    return AnalysisReport(
        run_id=state["run_id"],
        status=status,
        dataset_profile=state.get("dataset_profile"),
        data_dictionary=state.get("data_dictionary"),
        analysis_results=state.get("analysis_results", []),
        insights=state.get("insights", []),
        evidence=state.get("evidence", []),
        relationship_assessments=state.get("relationship_assessments", []),
        metrics=metrics,
        errors=errors,
        warnings=state.get("warnings", []),
        stage_statuses=statuses,
        stage_durations=state.get("stage_durations", {}),
        configuration=configuration.model_dump(mode="json") if configuration is not None else {},
        audit_version="1",
        user_question=state["input"].user_question if state.get("input") is not None else None,
        requested_configuration=state["input"].configuration.model_dump(mode="json")
        if state.get("input") is not None
        else {},
        dataset_id=state.get("dataset_id"),
        analysis_plan=state.get("analysis_plan"),
        planning_decisions=state.get("planning_decisions", []),
        screening_candidates=state.get("associations", []),
        screening_summary=state.get("screening_summary", {}),
        capabilities={"parallel_tools": False, "critic_feedback": False, "llm": False},
    )
