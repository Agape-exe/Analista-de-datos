from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.modules.exploration.adapters.http.dependencies import get_exploration_use_case
from app.modules.exploration.application.dto import ToolCatalog, ToolRunRequest
from app.modules.exploration.application.use_cases.explore_dataset import ExploreDataset
from app.shared.adapters.http.protection import enforce_request_limit, reserve_operation_capacity
from app.shared.application.errors import DatasetNotFoundError, ToolRegistryError
from app.shared.domain.models.analysis import AnalysisResult

router = APIRouter()


@router.get("/tools", response_model=ToolCatalog)
async def tools(
    use_case: Annotated[ExploreDataset, Depends(get_exploration_use_case)],
) -> ToolCatalog:
    return ToolCatalog(tools=use_case.tool_names())


@router.post(
    "/datasets/{dataset_id}/tools/{tool_name}",
    response_model=AnalysisResult,
    responses={404: {"description": "Dataset not in memory or unknown tool"}},
)
async def run_tool(
    request: Request,
    dataset_id: str,
    tool_name: str,
    use_case: Annotated[ExploreDataset, Depends(get_exploration_use_case)],
    body: ToolRunRequest | None = None,
) -> AnalysisResult:
    """SKIPPED/FAILED tool outcomes are returned with 200; they are analysis results."""
    try:
        await enforce_request_limit(request, "exploration")
        async with reserve_operation_capacity(request):
            return await use_case.run(dataset_id, tool_name, body or ToolRunRequest())
    except DatasetNotFoundError as error:
        raise HTTPException(
            404,
            detail={
                "code": "DATASET_NOT_FOUND",
                "message": "The dataset is no longer in memory. Upload it again to explore it.",
            },
        ) from error
    except ToolRegistryError as error:
        raise HTTPException(
            404, detail={"code": "TOOL_NOT_FOUND", "message": str(error)}
        ) from error
