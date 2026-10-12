import logging
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response

from app.api.routes.analysis import router as analysis_router
from app.api.routes.health import router as health_router
from app.config.settings import Settings, load_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Composition root for HTTP; no analytics or persistence operations here."""
    application = FastAPI(title="Multiagent Data Analyst", version="0.1.0")
    application.state.settings = settings if settings is not None else load_settings()

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
    return application


app = create_app()
