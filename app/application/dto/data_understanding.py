from dataclasses import dataclass, field

from app.application.dto.datasource import LoadedDataset
from app.domain.models.data_dictionary import DataDictionary
from app.domain.models.dataset import DatasetProfile, DatasetSummary


@dataclass(frozen=True)
class DataUnderstandingResult:
    """Local application result; agents receive only its serializable metadata."""

    dataset: LoadedDataset
    profile: DatasetProfile
    data_dictionary: DataDictionary
    profiling_time: float
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> DatasetSummary:
        return self.profile.summary(self.data_dictionary)
