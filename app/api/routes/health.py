from typing import Literal

from fastapi import APIRouter

from app.shared.domain.models.base import DomainModel

router = APIRouter()


class HealthResponse(DomainModel):
    status: Literal["ok"] = "ok"


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Process liveness; does not assert analytical readiness."""
    return HealthResponse()
