from collections import OrderedDict

from app.shared.application.errors import DatasetNotFoundError
from app.shared.contracts.datasource import RegisteredDataset


class InMemoryDatasetStore:
    """Process-local LRU store; evicts the least recently used dataset when full."""

    def __init__(self, max_datasets: int) -> None:
        if max_datasets < 1:
            raise ValueError("max_datasets must be at least 1")
        self.max_datasets = max_datasets
        self._datasets: OrderedDict[str, RegisteredDataset] = OrderedDict()

    async def register(self, dataset: RegisteredDataset) -> None:
        self._datasets[dataset.dataset_id] = dataset
        self._datasets.move_to_end(dataset.dataset_id)
        while len(self._datasets) > self.max_datasets:
            self._datasets.popitem(last=False)

    async def get(self, dataset_id: str) -> RegisteredDataset:
        try:
            dataset = self._datasets[dataset_id]
        except KeyError as error:
            raise DatasetNotFoundError(f"Dataset not available: {dataset_id}") from error
        self._datasets.move_to_end(dataset_id)
        return dataset

    async def discard(self, dataset_id: str) -> None:
        self._datasets.pop(dataset_id, None)

    def __len__(self) -> int:
        return len(self._datasets)
