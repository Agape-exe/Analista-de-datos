from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app.shared.adapters.http.protection import enforce_request_limit, reserve_operation_capacity
from app.shared.application.errors import (
    DatasetNotFoundError,
    DataSourceError,
    UploadTooLargeError,
    UploadValidationError,
)
from app.shared.contracts.analysis_input import AnalysisInput, StoredSourceSpec
from app.shared.contracts.intake import IntakeOptions
from app.shared.domain.models.base import DomainModel
from app.shared.domain.models.report import AnalysisReport

router = APIRouter()
local_router = APIRouter()


class StoredAnalysisRequest(DomainModel):
    user_question: str | None = None


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
    await enforce_request_limit(request, "upload")
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
    async with reserve_operation_capacity(request):
        return await request.app.state.analysis_use_case.execute(
            AnalysisInput(
                source=StoredSourceSpec(dataset_id=dataset_id), user_question=question or None
            )
        )
