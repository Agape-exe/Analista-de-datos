from app.analytics.registry import ToolRegistry
from app.analytics.statistics.correlation import (
    PartialCorrelationTool,
    PearsonCorrelationTool,
    SpearmanCorrelationTool,
)
from app.analytics.statistics.mixed import (
    ChiSquareIndependenceTool,
    CramersVTool,
    OneWayAnovaTool,
)
from app.application.services.dataset_registry import DatasetRegistry


def build_statistical_tool_registry(datasets: DatasetRegistry) -> ToolRegistry:
    """Build an explicit, per-execution registry backed by one local dataset registry."""
    registry = ToolRegistry()
    for tool in (
        PearsonCorrelationTool(datasets),
        SpearmanCorrelationTool(datasets),
        PartialCorrelationTool(datasets),
        ChiSquareIndependenceTool(datasets),
        CramersVTool(datasets),
        OneWayAnovaTool(datasets),
    ):
        registry.register(tool)
    return registry
