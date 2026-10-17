from dataclasses import dataclass

import pytest

from app.shared.application.dataset_registry import DatasetRegistry
from app.shared.application.errors import ToolRegistryError
from app.shared.application.tool_registry import ToolRegistry
from app.shared.contracts.datasource import LoadedDataset
from app.shared.domain.models.analysis import AnalysisResult, ToolRequest
from app.shared.domain.models.dataset import DatasetSchema


class NoOpTool:
    name = "noop"

    def supports(self, request: ToolRequest) -> bool:
        return request.method == self.name and not request.variables

    async def execute(self, request: ToolRequest) -> AnalysisResult:
        return AnalysisResult(method=self.name, status="SKIPPED")


class LocalValueTool:
    name = "local-values"

    def __init__(self, datasets: DatasetRegistry) -> None:
        self.datasets = datasets

    def supports(self, request: ToolRequest) -> bool:
        return request.method == self.name and request.variables == ["value"]

    async def execute(self, request: ToolRequest) -> AnalysisResult:
        values = self.datasets.get(request.dataset_id).table.column(request.variables[0])
        return AnalysisResult(
            method=self.name,
            variables=request.variables,
            status="SUCCESS",
            result={"count": len(values)},
            sample_size=len(values),
        )


@dataclass(frozen=True)
class MemoryTable:
    values: list[object]

    def column(self, name: str) -> list[object]:
        assert name == "value"
        return self.values


async def test_registry_dispatch_and_errors() -> None:
    registry = ToolRegistry()
    tool = NoOpTool()
    registry.register(tool)
    assert registry.names() == ("noop",)
    request = ToolRequest(dataset_id="small", method="noop")
    assert registry.get("noop").supports(request)
    assert (await registry.execute(request)).status == "SKIPPED"
    with pytest.raises(ToolRegistryError, match="already registered"):
        registry.register(tool)
    with pytest.raises(ToolRegistryError, match="Unknown"):
        registry.get("pearson")


async def test_registry_rejects_unregistered_and_unsupported_requests() -> None:
    registry = ToolRegistry()
    registry.register(NoOpTool())

    with pytest.raises(ToolRegistryError, match="Unknown"):
        await registry.execute(ToolRequest(dataset_id="small", method="pearson"))
    with pytest.raises(ToolRegistryError, match="does not support"):
        await registry.execute(ToolRequest(dataset_id="small", method="noop", variables=["x"]))


async def test_registered_tool_can_resolve_its_local_dataset() -> None:
    datasets = DatasetRegistry()
    datasets.register(
        LoadedDataset(
            dataset_id="local-1",
            schema=DatasetSchema(columns=[{"name": "value", "data_type": "int"}]),
            row_count=2,
            table=MemoryTable([3, 5]),
        )
    )
    registry = ToolRegistry()
    registry.register(LocalValueTool(datasets))

    result = await registry.execute(
        ToolRequest(dataset_id="local-1", method="local-values", variables=["value"])
    )

    assert result.status == "SUCCESS"
    assert result.result == {"count": 2}
