from fastapi import APIRouter, HTTPException, Request, Response

from app.modules.reporting.adapters.rendering.markdown import MarkdownReportRenderer
from app.shared.adapters.http.protection import enforce_request_limit
from app.shared.domain.models.metrics import ExperimentMetrics
from app.shared.domain.models.report import AnalysisReport

router = APIRouter()


async def get_report(run_id: str, request: Request) -> AnalysisReport:
    await enforce_request_limit(request, "report")
    report = await request.app.state.report_repository.get(run_id)
    if report is None:
        raise HTTPException(404, detail={"code": "REPORT_NOT_FOUND", "message": "Unknown run ID"})
    return report


@router.get("/reports/{run_id}", response_model=AnalysisReport)
async def report(run_id: str, request: Request) -> AnalysisReport:
    return await get_report(run_id, request)


@router.get("/reports/{run_id}/metrics", response_model=ExperimentMetrics)
async def report_metrics(run_id: str, request: Request) -> ExperimentMetrics:
    return (await get_report(run_id, request)).metrics


@router.get("/reports/{run_id}/markdown", response_class=Response)
async def report_markdown(run_id: str, request: Request) -> Response:
    content = MarkdownReportRenderer().render(await get_report(run_id, request))
    return Response(
        content,
        media_type="text/markdown",
        headers={"Content-Disposition": 'attachment; filename="analysis-report.md"'},
    )
