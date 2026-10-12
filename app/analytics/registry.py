from app.application.errors import ToolRegistryError
from app.ports.analytics_tool import AnalyticsTool


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

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))
