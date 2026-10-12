from fastapi import APIRouter, HTTPException, status

from app.application.dto.analysis_input import AnalysisInput
from app.domain.models.report import AnalysisReport

router = APIRouter()


@router.post(
    "/analysis",
    response_model=AnalysisReport,
    responses={501: {"description": "Complete analysis workflow not enabled"}},
)
async def analysis(analysis_input: AnalysisInput) -> AnalysisReport:
    """Validate the public contract; execution will be wired in a later increment."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "code": "ANALYSIS_WORKFLOW_NOT_ENABLED",
            "message": "Initial skeleton: the complete analysis workflow is not enabled.",
        },
    )
