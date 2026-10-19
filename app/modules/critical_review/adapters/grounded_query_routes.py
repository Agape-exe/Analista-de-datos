"""AUD-039: API de preguntas fundamentadas."""

from fastapi import APIRouter, HTTPException, Request

from app.modules.critical_review.application.services.grounded_queries import (
    QUESTIONS,
    GroundedAnswer,
    GroundedQueryRequest,
    answer_grounded_query,
)
from app.shared.adapters.http.protection import enforce_request_limit

router = APIRouter()


@router.get("/questions/catalog")
async def questions_catalog() -> dict[str, dict[str, str]]:
    return {"questions": QUESTIONS}


@router.post(
    "/reports/{run_id}/questions",
    response_model=GroundedAnswer,
)
async def ask_grounded_question(
    run_id: str,
    body: GroundedQueryRequest,
    request: Request,
) -> GroundedAnswer:
    await enforce_request_limit(request, "report")

    report = await request.app.state.report_repository.get(run_id)

    if report is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "REPORT_NOT_FOUND",
                "message": "No existe un reporte con ese ID.",
            },
        )

    return answer_grounded_query(report, body.question)
