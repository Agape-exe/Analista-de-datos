from dataclasses import dataclass

import pytest

from app.application.dto.datasource import LoadedDataset
from app.application.errors import DatasetRegistryError
from app.application.services.dataset_registry import DatasetRegistry
from app.domain.models.dataset import DatasetSchema


@dataclass(frozen=True)
class MemoryTable:
    columns: dict[str, list[object]]

    def column(self, name: str) -> list[object]:
        return self.columns[name]


def loaded(dataset_id: str = "dataset-1") -> LoadedDataset:
    return LoadedDataset(
        dataset_id=dataset_id,
        schema=DatasetSchema(columns=[{"name": "value", "data_type": "int"}]),
        row_count=2,
        table=MemoryTable({"value": [1, 2]}),
    )


def test_registry_registers_retrieves_and_releases_local_dataset() -> None:
    registry = DatasetRegistry()
    dataset = loaded()

    registry.register(dataset)

    assert registry.ids() == ("dataset-1",)
    assert registry.get("dataset-1").table.column("value") == [1, 2]
    registry.release("dataset-1")
    assert registry.ids() == ()
    with pytest.raises(DatasetRegistryError, match="Unknown dataset"):
        registry.get("dataset-1")


def test_registry_rejects_duplicate_unknown_and_inconsistent_datasets() -> None:
    registry = DatasetRegistry()
    dataset = loaded()
    registry.register(dataset)

    with pytest.raises(DatasetRegistryError, match="already registered"):
        registry.register(dataset)
    with pytest.raises(DatasetRegistryError, match="Unknown dataset"):
        registry.release("missing")
    inconsistent = LoadedDataset(
        dataset_id="bad",
        schema=DatasetSchema(columns=[{"name": "value", "data_type": "int"}]),
        row_count=2,
        table=MemoryTable({"value": [1]}),
    )
    with pytest.raises(DatasetRegistryError, match="inconsistent row count"):
        registry.register(inconsistent)


def test_registry_instances_are_isolated_and_clear_releases_references() -> None:
    first = DatasetRegistry()
    second = DatasetRegistry()
    first.register(loaded())

    assert first.get("dataset-1").dataset_id == "dataset-1"
    with pytest.raises(DatasetRegistryError, match="Unknown dataset"):
        second.get("dataset-1")
    first.clear()
    assert first.ids() == ()
