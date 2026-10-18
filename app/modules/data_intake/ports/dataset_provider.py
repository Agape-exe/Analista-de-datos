from typing import Protocol

from app.shared.contracts.datasource import RegisteredDataset


class DatasetProvider(Protocol):
    """Resolve local data by dataset_id; HTTP consumers expose only explicit bounded DTOs."""

    async def get(self, dataset_id: str) -> RegisteredDataset: ...


class DatasetStore(DatasetProvider, Protocol):
    """Writable provider used by intake stages to publish understood datasets."""

    async def register(self, dataset: RegisteredDataset) -> None: ...

    async def discard(self, dataset_id: str) -> None: ...
