from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile

from app.adapters.reporting.markdown import MarkdownReportRenderer
from app.api.protection import enforce_request_limit, reserve_operation_capacity
from app.application.dto.analysis_input import AnalysisInput
from app.application.dto.intake import IntakeOptions
from app.application.errors import (
    DatasetNotFoundError,
    DataSourceError,
    UploadTooLargeError,
    UploadValidationError,
)
from app.domain.models.base import DomainModel
from app.domain.models.metrics import ExperimentMetrics
from app.domain.models.report import AnalysisReport

router = APIRouter()
local_router = APIRouter()


@local_router.post("/analysis", response_model=AnalysisReport)
async def analysis(analysis_input: AnalysisInput, request: Request) -> AnalysisReport:
    """Local development contract. Pending stages remain explicitly SKIPPED."""
    return await request.app.state.analysis_use_case.execute(analysis_input)


@router.post("/analysis/upload", response_model=AnalysisReport)
async def analysis_upload(
    request: Request,
    file: Annotated[UploadFile, File()],
    delimiter: Annotated[str, Form(min_length=1, max_length=1)] = ",",
    encoding: Annotated[str, Form(min_length=1)] = "utf-8",
    data_dictionary: Annotated[UploadFile | None, File()] = None,
    user_question: Annotated[str | None, Form()] = None,
) -> AnalysisReport:
    try:
        await enforce_request_limit(request, "upload")
        async with reserve_operation_capacity(request):
            return await request.app.state.upload_analysis.execute(
                file,
                IntakeOptions(delimiter=delimiter, encoding=encoding),
                data_dictionary,
                user_question,
            )
    except UploadTooLargeError as error:
        raise HTTPException(
            413, detail={"code": "UPLOAD_TOO_LARGE", "message": str(error)}
        ) from error
    except (UploadValidationError, DataSourceError) as error:
        raise HTTPException(
            400, detail={"code": "ANALYSIS_INPUT_INVALID", "message": str(error)}
        ) from error
    finally:
        await file.close()
        if data_dictionary is not None:
            await data_dictionary.close()


@router.post(
    "/analysis/datasets/{dataset_id}",
    response_model=AnalysisReport,
    responses={404: {"description": "Dataset no longer in memory"}},
)
async def analysis_stored(
    dataset_id: str, request: Request, body: StoredAnalysisRequest | None = None
) -> AnalysisReport:
    """Analyze a dataset already uploaded through intake, without re-reading or re-profiling."""
    try:
        await request.app.state.datasets.get(dataset_id)
    except DatasetNotFoundError as error:
        raise HTTPException(
            404,
            detail={
                "code": "DATASET_NOT_FOUND",
                "message": "The dataset is no longer in memory. Upload it again to analyze it.",
            },
        ) from error
    question = body.user_question.strip() if body and body.user_question else None
    return await request.app.state.analysis_use_case.execute(
        AnalysisInput(
            source=StoredSourceSpec(dataset_id=dataset_id), user_question=question or None
        )
    )


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
