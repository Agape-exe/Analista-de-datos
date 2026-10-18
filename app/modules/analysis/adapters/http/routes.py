from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import Field, model_validator

from app.shared.adapters.http.protection import enforce_request_limit, reserve_operation_capacity
from app.shared.application.errors import (
    DatasetNotFoundError,
    DataSourceError,
    UploadTooLargeError,
    UploadValidationError,
)
from app.shared.contracts.analysis_input import (
    AnalysisConfiguration,
    AnalysisInput,
    StoredSourceSpec,
)
from app.shared.contracts.intake import IntakeOptions
from app.shared.domain.models.base import DomainModel
from app.shared.domain.models.report import AnalysisReport

router = APIRouter()
local_router = APIRouter()


class StoredAnalysisOptions(DomainModel):
    mode: Literal["fast", "standard"] | None = None
    max_hypotheses: int | None = Field(default=None, ge=1, le=20, strict=True)
    max_tool_calls: int | None = Field(default=None, ge=0, le=100, strict=True)
    minimum_sample_size: int | None = Field(default=None, ge=2, le=250000, strict=True)


class StoredPerformanceOptions(DomainModel):
    timeout_seconds: float | None = Field(
        default=None, gt=0, le=120, allow_inf_nan=False, strict=True
    )


class StoredConfiguration(DomainModel):
    analysis: StoredAnalysisOptions = Field(default_factory=StoredAnalysisOptions)
    performance: StoredPerformanceOptions = Field(default_factory=StoredPerformanceOptions)

    @model_validator(mode="after")
    def concrete_overrides(self) -> "StoredConfiguration":
        for section in (self.analysis, self.performance):
            if any(getattr(section, name) is None for name in section.model_fields_set):
                raise ValueError("Configuration overrides cannot be null")
        return self


class StoredAnalysisRequest(DomainModel):
    user_question: str | None = None
    configuration: StoredConfiguration = Field(default_factory=StoredConfiguration)


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
                source=StoredSourceSpec(dataset_id=dataset_id),
                user_question=question or None,
                configuration=AnalysisConfiguration.model_validate(
                    body.configuration.model_dump(exclude_unset=True) if body else {}
                ),
            )
        )
