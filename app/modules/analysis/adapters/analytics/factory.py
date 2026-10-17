from app.modules.analysis.adapters.analytics.correlation import (
    PartialCorrelationTool,
    PearsonCorrelationTool,
    SpearmanCorrelationTool,
)
from app.modules.analysis.adapters.analytics.diagnostics import (
    AdditiveIdentityTool,
    OutlierCorrelationTool,
    SubgroupCorrelationTool,
)
from app.modules.analysis.adapters.analytics.mixed import (
    ChiSquareIndependenceTool,
    CramersVTool,
    OneWayAnovaTool,
)
from app.shared.application.dataset_registry import DatasetRegistry
from app.shared.application.tool_registry import ToolRegistry


def build_statistical_tool_registry(datasets: DatasetRegistry) -> ToolRegistry:
    """Build an explicit, per-execution registry backed by one local dataset registry."""
    registry = ToolRegistry()
    for tool in (
        PearsonCorrelationTool(datasets),
        SpearmanCorrelationTool(datasets),
        PartialCorrelationTool(datasets),
        OutlierCorrelationTool(datasets),
        SubgroupCorrelationTool(datasets),
        AdditiveIdentityTool(datasets),
        ChiSquareIndependenceTool(datasets),
        CramersVTool(datasets),
        OneWayAnovaTool(datasets),
    ):
        registry.register(tool)
    return registry
