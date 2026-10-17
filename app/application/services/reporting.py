from collections.abc import Mapping
from typing import Any

from app.domain.enums.statuses import AnalysisStatus
from app.domain.models.metrics import ExperimentMetrics
from app.domain.models.report import AnalysisReport


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
    )
