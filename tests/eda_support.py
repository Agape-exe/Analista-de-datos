"""Synthetic datasets with known relationships for EDA and association tests."""

from dataclasses import dataclass

import numpy as np

from app.modules.data_intake.adapters.datasource.dataset_store import InMemoryDatasetStore
from app.shared.contracts.datasource import LoadedDataset, RegisteredDataset
from app.shared.domain.enums.semantic_type import SemanticType
from app.shared.domain.models.dataset import (
    ColumnProfile,
    ColumnSchema,
    DatasetProfile,
    DatasetSchema,
)


@dataclass(frozen=True)
class ListTable:
    columns: dict[str, list[object]]

    def column(self, name: str) -> list[object]:
        return list(self.columns[name])


def make_dataset(
    columns: dict[str, list[object]], roles: dict[str, SemanticType], dataset_id: str = "ds"
) -> RegisteredDataset:
    rows = len(next(iter(columns.values())))
    schema = DatasetSchema(
        columns=[ColumnSchema(name=name, data_type="object") for name in columns]
    )
    profile = DatasetProfile(
        dataset_id=dataset_id,
        row_count=rows,
        columns=[
            ColumnProfile(
                column_name=name,
                data_type="object",
                semantic_type=roles[name],
                missing_count=sum(value is None for value in values),
                unique_count=len({value for value in values if value is not None}),
            )
            for name, values in columns.items()
        ],
    )
    return RegisteredDataset(LoadedDataset(dataset_id, schema, rows, ListTable(columns)), profile)


def planted_dataset(rows: int = 300, seed: int = 7) -> RegisteredDataset:
    """devengado~girado (linear), region->monto (groups), region~canal (dependent)."""
    rng = np.random.default_rng(seed)
    devengado = rng.normal(1000, 200, rows)
    girado = 0.9 * devengado + rng.normal(0, 40, rows)
    region = rng.choice(["norte", "sur", "este"], rows)
    shift = {"norte": 0.0, "sur": 300.0, "este": 600.0}
    monto = np.asarray([shift[r] for r in region]) + rng.normal(0, 60, rows)
    canal = np.asarray(
        [r if rng.random() < 0.8 else rng.choice(["norte", "sur", "este"]) for r in region]
    )
    ruido = rng.normal(0, 1, rows)
    color = rng.choice(["rojo", "azul"], rows)
    devengado_values: list[object] = [float(v) for v in devengado]
    devengado_values[0] = None
    columns: dict[str, list[object]] = {
        "codigo_id": [f"ID{i}" for i in range(rows)],
        "devengado": devengado_values,
        "girado": [float(v) for v in girado],
        "monto": [float(v) for v in monto],
        "region": list(region),
        "canal": [f"c_{v}" for v in canal],
        "ruido": [float(v) for v in ruido],
        "color": list(color),
        "constante": [1.0] * rows,
    }
    roles = {
        "codigo_id": SemanticType.IDENTIFIER,
        "devengado": SemanticType.NUMERIC,
        "girado": SemanticType.NUMERIC,
        "monto": SemanticType.NUMERIC,
        "region": SemanticType.CATEGORICAL,
        "canal": SemanticType.CATEGORICAL,
        "ruido": SemanticType.NUMERIC,
        "color": SemanticType.CATEGORICAL,
        "constante": SemanticType.NUMERIC,
    }
    return make_dataset(columns, roles)


async def store_with(*datasets: RegisteredDataset) -> InMemoryDatasetStore:
    store = InMemoryDatasetStore(max_datasets=8)
    for dataset in datasets:
        await store.register(dataset)
    return store
