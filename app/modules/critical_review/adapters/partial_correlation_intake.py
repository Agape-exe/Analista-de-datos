"""Adaptador para ejecutar correlación parcial sobre datasets de intake."""

from collections.abc import Callable

from app.modules.data_intake.ports.dataset_provider import DatasetProvider
from app.shared.application.dataset_registry import DatasetRegistry
from app.shared.domain.models.analysis import AnalysisResult, ToolRequest
from app.shared.ports.analytics_tool import AnalyticsTool


class PartialCorrelationIntakeAdapter:
    """Conecta un dataset activo con la herramienta estadística existente."""

    name = "partial_correlation"

    def __init__(
        self,
        datasets: DatasetProvider,
        create_tool: Callable[[DatasetRegistry], AnalyticsTool],
    ) -> None:
        self.datasets = datasets
        self.create_tool = create_tool

    def supports(self, request: ToolRequest) -> bool:
        control = request.parameters.get("control_variable")

        return (
            request.method == self.name
            and len(request.variables) == 2
            and len(set(request.variables)) == 2
            and set(request.parameters) == {"control_variable"}
            and isinstance(control, str)
            and bool(control.strip())
            and control not in request.variables
        )

    async def execute(self, request: ToolRequest) -> AnalysisResult:
        # Recuperar el dataset registrado después del intake.
        registered = await self.datasets.get(request.dataset_id)

        # Crear un registro temporal por solicitud.
        registry = DatasetRegistry()
        registry.register(registered.dataset)

        try:
            # Reutilizar el algoritmo estadístico existente.
            tool = self.create_tool(registry)
            return await tool.execute(request)
        finally:
            # Liberar las referencias temporales al finalizar.
            registry.clear()
