from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)

from app.modules.data_intake.adapters.http.dependencies import (
    get_intake_use_case,
    get_preview_use_case,
    get_quality_use_case,
)
from app.modules.data_intake.application.dto import DatasetPreview, DatasetPreviewQuery
from app.modules.data_intake.application.quality_dto import DatasetQuality
from app.modules.data_intake.application.use_cases.evaluate_dataset_quality import (
    EvaluateDatasetQuality,
)
from app.modules.data_intake.application.use_cases.intake_uploaded_dataset import (
    IntakeUploadedDataset,
)
from app.modules.data_intake.application.use_cases.preview_dataset import PreviewDataset
from app.modules.data_intake.domain.preview import PreviewTooLargeError, PreviewUnsupportedError
from app.modules.data_intake.domain.quality import QualityTooLargeError, QualityUnsupportedError
from app.shared.adapters.http.protection import enforce_request_limit, reserve_operation_capacity
from app.shared.application.errors import (
    DatasetNotFoundError,
    DataSourceError,
    UploadTooLargeError,
    UploadValidationError,
)
from app.shared.contracts.intake import IntakeOptions, IntakeResponse

router = APIRouter()


@router.get(
    "/datasets/{dataset_id}/quality",
    response_model=DatasetQuality,
    responses={
        404: {"description": "Dataset no longer registered in memory"},
        413: {"description": "Exact quality evaluation exceeds resource budgets"},
        422: {"description": "Unsupported local table, structure or value"},
        429: {"description": "Shared exploration rate or operation capacity exceeded"},
    },
)
async def dataset_quality(
    request: Request,
    response: Response,
    dataset_id: str,
    use_case: Annotated[EvaluateDatasetQuality, Depends(get_quality_use_case)],
) -> DatasetQuality:
    """Evaluate exact quality aggregates on the registered, unmodified dataset."""
    try:
        await enforce_request_limit(request, "exploration")
        async with reserve_operation_capacity(request):
            result = await use_case.execute(dataset_id)
    except DatasetNotFoundError as error:
        raise HTTPException(
            404,
            detail={
                "code": "DATASET_NOT_FOUND",
                "message": "Dataset no longer in memory. Upload it again to evaluate quality.",
            },
        ) from error
    except QualityTooLargeError as error:
        raise HTTPException(
            413,
            detail={
                "code": "QUALITY_TOO_LARGE",
                "message": "Exact quality evaluation exceeds resource limits; no partial results.",
            },
        ) from error
    except QualityUnsupportedError as error:
        raise HTTPException(
            422,
            detail={
                "code": "QUALITY_UNSUPPORTED",
                "message": "Dataset cannot be evaluated safely with the supported quality rules.",
            },
        ) from error
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get(
    "/datasets/{dataset_id}/preview",
    response_model=DatasetPreview,
    responses={
        404: {"description": "Dataset no longer registered in memory"},
        413: {"description": "Preview exceeds row, cell or UTF-8 JSON budgets"},
        422: {"description": "Invalid pagination or unsupported preview value/table"},
        429: {"description": "Shared exploration rate or operation capacity exceeded"},
    },
)
async def preview_dataset(
    request: Request,
    response: Response,
    dataset_id: str,
    query: Annotated[DatasetPreviewQuery, Query()],
    use_case: Annotated[PreviewDataset, Depends(get_preview_use_case)],
) -> DatasetPreview:
    """Read a bounded page in original order; positions are not persistent row IDs."""
    try:
        await enforce_request_limit(request, "exploration")
        async with reserve_operation_capacity(request):
            page = await use_case.execute(dataset_id, query)
    except DatasetNotFoundError as error:
        raise HTTPException(
            404,
            detail={
                "code": "DATASET_NOT_FOUND",
                "message": "The dataset is no longer in memory. Upload it again to preview it.",
            },
        ) from error
    except PreviewTooLargeError as error:
        raise HTTPException(
            413,
            detail={
                "code": "PREVIEW_TOO_LARGE",
                "message": (
                    "Preview exceeds its size limits. Request fewer rows; values are not truncated."
                ),
            },
        ) from error
    except PreviewUnsupportedError as error:
        raise HTTPException(
            422,
            detail={
                "code": "PREVIEW_UNSUPPORTED",
                "message": (
                    "This page contains a value or local table that cannot be previewed safely."
                ),
            },
        ) from error
    response.headers["Cache-Control"] = "no-store"
    return page


@router.post("/intake", response_model=IntakeResponse)
async def intake(
    request: Request,
    file: Annotated[UploadFile, File()],
    use_case: Annotated[IntakeUploadedDataset, Depends(get_intake_use_case)],
    delimiter: Annotated[str, Form(min_length=1, max_length=1)] = ",",
    encoding: Annotated[str, Form(min_length=1)] = "utf-8",
    data_dictionary: Annotated[UploadFile | None, File()] = None,
) -> IntakeResponse:
    """Translate multipart HTTP input to the framework-independent intake use case."""
    try:
        await enforce_request_limit(request, "upload")
        async with reserve_operation_capacity(request):
            return await use_case.execute(
                file, IntakeOptions(delimiter=delimiter, encoding=encoding), data_dictionary
            )
    except UploadTooLargeError as error:
        raise HTTPException(
            413, detail={"code": "UPLOAD_TOO_LARGE", "message": str(error)}
        ) from error
    except (UploadValidationError, DataSourceError) as error:
        raise HTTPException(
            400, detail={"code": "INTAKE_VALIDATION_FAILED", "message": str(error)}
        ) from error
    finally:
        await file.close()
        if data_dictionary is not None:
            await data_dictionary.close()
