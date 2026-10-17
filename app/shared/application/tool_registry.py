from app.shared.application.errors import ToolRegistryError
from app.shared.domain.models.analysis import AnalysisResult, ToolRequest
from app.shared.ports.analytics_tool import AnalyticsTool


class ToolRegistry:
    """Explicit instance registration; no dynamic code evaluation."""

    def __init__(self) -> None:
        self._tools: dict[str, AnalyticsTool] = {}

    def register(self, tool: AnalyticsTool) -> None:
        if not tool.name.strip():
            raise ToolRegistryError("Tool name cannot be empty")
        if tool.name in self._tools:
            raise ToolRegistryError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> AnalyticsTool:
        try:
            return self._tools[name]
        except KeyError as error:
            raise ToolRegistryError(f"Unknown analytics tool: {name}") from error

    def resolve(self, request: ToolRequest) -> AnalyticsTool:
        """Return an authorized tool only when it declares request compatibility."""
        tool = self.get(request.method)
        if not tool.supports(request):
            raise ToolRegistryError(f"Analytics tool does not support request: {request.method}")
        return tool

    async def execute(self, request: ToolRequest) -> AnalysisResult:
        """Execute through the registry so unregistered tools cannot be dispatched."""
        return await self.resolve(request).execute(request)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))
