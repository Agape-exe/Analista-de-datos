import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.bootstrap import (
    build_dataset_store,
    build_exploration_use_case,
    build_intake_use_case,
    build_preview_use_case,
    build_quality_use_case,
    build_repository,
    build_use_case,
)
from app.modules.analysis.adapters.http.routes import local_router as local_analysis_router
from app.modules.analysis.adapters.http.routes import router as analysis_router
from app.modules.analysis.application.use_cases.analyze_dataset import AnalyzeDataset
from app.modules.analysis.application.use_cases.analyze_uploaded_dataset import (
    AnalyzeUploadedDataset,
)
from app.modules.data_intake.adapters.datasource.upload_storage import TemporaryUploadStorage
from app.modules.data_intake.adapters.http.routes import router as intake_router
from app.modules.exploration.adapters.http.routes import router as exploration_router
from app.modules.reporting.adapters.http.routes import router as reporting_router
from app.shared.adapters.http.protection import build_operation_capacity, build_request_limiter
from app.shared.config.settings import Settings, load_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Composition root for HTTP; no analytics or persistence operations here."""

    @asynccontextmanager
    async def lifespan(instance):
        repository = build_repository(instance.state.settings)
        instance.state.report_repository = repository
        workflow = build_use_case(instance.state.settings, instance.state.datasets).workflow
        instance.state.analysis_use_case = AnalyzeDataset(workflow, repository)
        uploads = instance.state.settings.uploads
        instance.state.upload_analysis = AnalyzeUploadedDataset(
            instance.state.analysis_use_case,
            TemporaryUploadStorage(uploads.chunk_size_bytes, uploads.temporary_directory),
            uploads.max_dataset_bytes,
            uploads.max_dictionary_bytes,
        )
        try:
            yield
        finally:
            repository.engine.dispose()

    application = FastAPI(title="Multiagent Data Analyst", version="0.1.0", lifespan=lifespan)
    application.state.settings = settings if settings is not None else load_settings()
    deployment = application.state.settings.deployment
    application.state.request_limiter = build_request_limiter(deployment)
    application.state.operation_capacity = build_operation_capacity(deployment)
    if deployment.cors_allowed_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=deployment.cors_allowed_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type"],
            # Retry-After must be readable cross-origin or clients cannot honour 429 waits.
            expose_headers=["X-Request-ID", "Retry-After"],
        )
    datasets = build_dataset_store(application.state.settings)
    application.state.datasets = datasets
    application.state.intake_use_case = build_intake_use_case(application.state.settings, datasets)
    application.state.preview_use_case = build_preview_use_case(datasets)
    application.state.quality_use_case = build_quality_use_case(datasets)
    application.state.exploration_use_case = build_exploration_use_case(
        application.state.settings, datasets
    )

    @application.middleware("http")
    async def request_trace(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logging.getLogger("app.api").info(
            "request_id=%s method=%s status=%s", request_id, request.method, response.status_code
        )
        return response

    application.include_router(health_router)
    application.include_router(analysis_router)
    application.include_router(reporting_router)
    if deployment.allow_local_analysis:
        application.include_router(local_analysis_router)
    application.include_router(intake_router)
    application.include_router(exploration_router)
    return application


app = create_app()
