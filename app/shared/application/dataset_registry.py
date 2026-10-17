from app.shared.application.errors import DatasetRegistryError
from app.shared.contracts.datasource import LoadedDataset


class DatasetRegistry:
    """Per-execution in-memory access to validated local datasets.

    Instances deliberately own their references: no dataset is serialized or shared
    across workflow executions, and callers can release it when execution ends.
    """

    def __init__(self) -> None:
        self._datasets: dict[str, LoadedDataset] = {}

    def register(self, dataset: LoadedDataset) -> None:
        dataset_id = dataset.dataset_id.strip()
        if not dataset_id:
            raise DatasetRegistryError("Dataset id cannot be empty")
        if dataset_id != dataset.dataset_id:
            raise DatasetRegistryError("Dataset id cannot contain surrounding whitespace")
        if dataset_id in self._datasets:
            raise DatasetRegistryError(f"Dataset already registered: {dataset_id}")
        self._validate(dataset)
        self._datasets[dataset_id] = dataset

    def get(self, dataset_id: str) -> LoadedDataset:
        try:
            return self._datasets[dataset_id]
        except KeyError as error:
            raise DatasetRegistryError(f"Unknown dataset: {dataset_id}") from error

    def release(self, dataset_id: str) -> None:
        try:
            del self._datasets[dataset_id]
        except KeyError as error:
            raise DatasetRegistryError(f"Unknown dataset: {dataset_id}") from error

    def clear(self) -> None:
        """Release every local reference owned by this execution."""
        self._datasets.clear()

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._datasets))

    @staticmethod
    def _validate(dataset: LoadedDataset) -> None:
        for column in dataset.schema.columns:
            try:
                values = dataset.table.column(column.name)
            except (KeyError, ValueError, TypeError) as error:
                raise DatasetRegistryError(
                    f"Dataset '{dataset.dataset_id}' cannot provide column '{column.name}'"
                ) from error
            if len(values) != dataset.row_count:
                raise DatasetRegistryError(
                    f"Dataset '{dataset.dataset_id}' has an inconsistent row count for "
                    f"column '{column.name}'"
                )
