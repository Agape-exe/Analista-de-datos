from app.modules.data_intake.application.dto import DatasetPreview, DatasetPreviewQuery
from app.modules.data_intake.domain.preview import (
    MAX_PREVIEW_BYTES,
    MAX_PREVIEW_CELLS,
    MAX_PREVIEW_COLUMNS,
    PreviewTooLargeError,
    PreviewUnsupportedError,
    preview_value_size,
)
from app.modules.data_intake.ports.dataset_preview import DatasetPreviewReader
from app.modules.data_intake.ports.dataset_provider import DatasetProvider


class PreviewDataset:
    """Resolve a registered dataset and return only an explicitly bounded page."""

    def __init__(self, datasets: DatasetProvider, reader: DatasetPreviewReader) -> None:
        self.datasets = datasets
        self.reader = reader

    async def execute(self, dataset_id: str, query: DatasetPreviewQuery) -> DatasetPreview:
        dataset = (await self.datasets.get(dataset_id)).dataset
        columns = dataset.schema.columns
        count = min(query.limit, max(0, dataset.row_count - query.offset))
        if len(columns) > MAX_PREVIEW_COLUMNS or len(columns) * count > MAX_PREVIEW_CELLS:
            raise PreviewTooLargeError
        metadata_bytes = 0
        for column in columns:
            preview_value_size(column.name)
            preview_value_size(column.data_type)
            metadata_bytes += len(column.model_dump_json().encode("utf-8")) + 1
            if metadata_bytes > MAX_PREVIEW_BYTES:
                raise PreviewTooLargeError
        rows = await self.reader.read(dataset, query.offset, count) if count else []
        if len(rows) != count or any(len(row) != len(columns) for row in rows):
            raise PreviewUnsupportedError
        end = query.offset + len(rows)
        has_more = end < dataset.row_count
        page = DatasetPreview(
            dataset_id=dataset.dataset_id,
            columns=columns,
            rows=rows,
            total_rows=dataset.row_count,
            offset=query.offset,
            limit=query.limit,
            returned_rows=len(rows),
            has_more=has_more,
            next_offset=end if has_more else None,
        )
        if len(page.model_dump_json().encode("utf-8")) > MAX_PREVIEW_BYTES:
            raise PreviewTooLargeError
        return page
