"""Synthetic registered frames for preview tests; no private data or profiling."""

import pandas as pd

from app.modules.data_intake.adapters.datasource.delimited_source import PandasLocalTable
from app.shared.contracts.datasource import LoadedDataset, RegisteredDataset
from app.shared.domain.models.dataset import (
    ColumnProfile,
    ColumnSchema,
    DatasetProfile,
    DatasetSchema,
)


def registered_frame(
    frame: pd.DataFrame, dataset_id: str = "synthetic-preview"
) -> RegisteredDataset:
    schema = DatasetSchema(
        columns=[
            ColumnSchema(name=name, data_type=str(frame[name].dtype)) for name in frame.columns
        ]
    )
    return RegisteredDataset(
        LoadedDataset(dataset_id, schema, len(frame), PandasLocalTable(frame)),
        DatasetProfile(
            dataset_id=dataset_id,
            row_count=len(frame),
            columns=[
                ColumnProfile(column_name=column.name, data_type=column.data_type)
                for column in schema.columns
            ],
        ),
    )
