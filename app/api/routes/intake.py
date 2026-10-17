from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.api.dependencies import get_intake_use_case
from app.api.protection import enforce_request_limit, reserve_operation_capacity
from app.application.dto.intake import IntakeOptions, IntakeResponse
from app.application.errors import DataSourceError, UploadTooLargeError, UploadValidationError
from app.application.use_cases.intake_uploaded_dataset import IntakeUploadedDataset

router = APIRouter()


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
