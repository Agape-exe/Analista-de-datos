from typing import Protocol

from app.modules.data_intake.domain.preview import PreviewValue
from app.shared.contracts.datasource import LoadedDataset


class DatasetPreviewReader(Protocol):
    """Read only the requested positional range, normalizing scalars within budgets.

    Implementations must not call column(), re-profile, or materialize the whole table.
    """

    async def read(
        self, dataset: LoadedDataset, offset: int, limit: int
    ) -> list[list[PreviewValue]]: ...
