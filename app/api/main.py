import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, Response

from app.adapters.datasource.upload_storage import TemporaryUploadStorage
from app.api.routes.analysis import router as analysis_router
from app.api.routes.health import router as health_router
from app.api.routes.intake import router as intake_router
from app.application.use_cases.analyze_dataset import AnalyzeDataset
from app.application.use_cases.analyze_uploaded_dataset import AnalyzeUploadedDataset
from app.bootstrap import build_intake_use_case, build_repository, build_use_case
from app.config.settings import Settings, load_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Composition root for HTTP; no analytics or persistence operations here."""

    @asynccontextmanager
    async def lifespan(instance):
        repository = build_repository(instance.state.settings)
        instance.state.report_repository = repository
        workflow = build_use_case(instance.state.settings).workflow
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
    application.state.intake_use_case = build_intake_use_case(application.state.settings)

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
    application.include_router(intake_router)
    return application


app = create_app()
