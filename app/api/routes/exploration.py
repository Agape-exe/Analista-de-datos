from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_exploration_use_case
from app.application.dto.exploration import ToolCatalog, ToolRunRequest
from app.application.errors import DatasetNotFoundError, ToolRegistryError
from app.application.use_cases.explore_dataset import ExploreDataset
from app.domain.models.analysis import AnalysisResult

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
    dataset_id: str,
    tool_name: str,
    use_case: Annotated[ExploreDataset, Depends(get_exploration_use_case)],
    body: ToolRunRequest | None = None,
) -> AnalysisResult:
    """SKIPPED/FAILED tool outcomes are returned with 200; they are analysis results."""
    try:
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
