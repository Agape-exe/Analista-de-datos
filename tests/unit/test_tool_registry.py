import pytest

from app.analytics.registry import ToolRegistry
from app.application.errors import ToolRegistryError
from app.domain.models.analysis import AnalysisResult, ToolRequest


class NoOpTool:
    name = "noop"

    def supports(self, request: ToolRequest) -> bool:
        return request.method == self.name

    async def execute(self, request: ToolRequest) -> AnalysisResult:
        return AnalysisResult(method=self.name, status="SKIPPED")


async def test_registry_dispatch_and_errors() -> None:
    registry = ToolRegistry()
    tool = NoOpTool()
    registry.register(tool)
    assert registry.names() == ("noop",)
    request = ToolRequest(dataset_id="small", method="noop")
    assert registry.get("noop").supports(request)
    assert (await registry.get("noop").execute(request)).status == "SKIPPED"
    with pytest.raises(ToolRegistryError, match="already registered"):
        registry.register(tool)
    with pytest.raises(ToolRegistryError, match="Unknown"):
        registry.get("pearson")
