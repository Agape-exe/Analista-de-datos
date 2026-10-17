from pathlib import Path

import pytest
from eda_support import make_dataset

from app.adapters.datasource.dataset_store import InMemoryDatasetStore
from app.application.dto.analysis_input import AnalysisInput
from app.application.errors import DatasetNotFoundError
from app.application.services.registering_understanding import RegisteringDataUnderstanding
from app.bootstrap import build_data_understanding
from app.config.settings import Settings
from app.domain.enums.semantic_type import SemanticType


def dataset(dataset_id: str):
    return make_dataset({"a": [1.0, 2.0]}, {"a": SemanticType.NUMERIC}, dataset_id)


async def test_store_registers_resolves_and_discards() -> None:
    store = InMemoryDatasetStore(max_datasets=2)
    await store.register(dataset("one"))
    resolved = await store.get("one")
    assert resolved.dataset_id == "one"
    assert resolved.semantic_type("a") == SemanticType.NUMERIC
    assert resolved.values("a") == [1.0, 2.0]
    await store.discard("one")
    await store.discard("one")
    with pytest.raises(DatasetNotFoundError):
        await store.get("one")


async def test_store_evicts_least_recently_used() -> None:
    store = InMemoryDatasetStore(max_datasets=2)
    await store.register(dataset("one"))
    await store.register(dataset("two"))
    await store.get("one")
    await store.register(dataset("three"))
    assert len(store) == 2
    await store.get("one")
    with pytest.raises(DatasetNotFoundError):
        await store.get("two")


def test_store_requires_capacity() -> None:
    with pytest.raises(ValueError):
        InMemoryDatasetStore(max_datasets=0)


async def test_registering_understanding_publishes_dataset() -> None:
    settings = Settings(_env_file=None)
    store = InMemoryDatasetStore(max_datasets=1)
    understanding = RegisteringDataUnderstanding(build_data_understanding(settings), store)
    path = Path(__file__).parents[1] / "fixtures" / "sample.csv"
    result = await understanding.understand(AnalysisInput(source={"kind": "csv", "path": path}))
    registered = await store.get(result.dataset.dataset_id)
    assert registered.profile == result.profile
    assert registered.values("age")[0] == 25
