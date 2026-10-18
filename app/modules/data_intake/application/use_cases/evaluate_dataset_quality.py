from app.modules.data_intake.application.quality_dto import (
    DatasetQuality,
    QualityColumnMetrics,
    QualityDuplicateMetrics,
    QualityMissingMetrics,
)
from app.modules.data_intake.domain.quality import (
    QualityLimits,
    QualityTooLargeError,
    QualityUnsupportedError,
    evaluate_quality_rules,
)
from app.modules.data_intake.ports.dataset_provider import DatasetProvider
from app.modules.data_intake.ports.dataset_quality import DatasetQualityReader


def _percentage(count: int, total: int) -> float:
    return 100 * count / total if total else 0.0


class EvaluateDatasetQuality:
    def __init__(
        self,
        datasets: DatasetProvider,
        reader: DatasetQualityReader,
        limits: QualityLimits | None = None,
    ) -> None:
        self.datasets = datasets
        self.reader = reader
        self.limits = limits if limits is not None else QualityLimits()

    async def execute(self, dataset_id: str) -> DatasetQuality:
        registered = await self.datasets.get(dataset_id)
        dataset = registered.dataset
        rows, columns = dataset.row_count, dataset.schema.columns
        self.limits.check_shape(rows, len(columns))
        # Bound schema serialization before physical evaluation as well as final output.
        metadata_bytes = 0
        for column in columns:
            if len(column.name) + len(column.data_type) > self.limits.max_response_bytes:
                raise QualityTooLargeError
            try:
                metadata_bytes += len(column.model_dump_json().encode("utf-8"))
            except (ValueError, UnicodeError) as error:
                raise QualityUnsupportedError from error
            if metadata_bytes > self.limits.max_response_bytes:
                raise QualityTooLargeError
        counts = await self.reader.measure(registered, self.limits)
        if (
            len(counts.missing_by_column) != len(columns)
            or any(not 0 <= count <= rows for count in counts.missing_by_column)
            or not 0 <= counts.incomplete_rows <= rows
            or not 0 <= counts.duplicate_rows <= max(0, rows - 1)
            or not 0 <= counts.duplicate_groups <= counts.duplicate_rows
            or bool(counts.duplicate_groups) != bool(counts.duplicate_rows)
            or counts.duplicate_rows + counts.duplicate_groups > rows
        ):
            raise QualityUnsupportedError
        missing = sum(counts.missing_by_column)
        if not counts.incomplete_rows <= missing <= counts.incomplete_rows * len(columns):
            raise QualityUnsupportedError
        result = DatasetQuality(
            dataset_id=dataset.dataset_id,
            status="EVALUATED" if rows and columns else "NOT_EVALUATED",
            total_rows=rows,
            total_columns=len(columns),
            total_cells=rows * len(columns),
            missing=QualityMissingMetrics(
                missing_cells=missing,
                missing_percentage=_percentage(missing, rows * len(columns)),
                incomplete_rows=counts.incomplete_rows,
                complete_rows=rows - counts.incomplete_rows,
                columns=[
                    QualityColumnMetrics(
                        column_name=column.name,
                        data_type=column.data_type,
                        missing_count=count,
                        missing_percentage=_percentage(count, rows),
                    )
                    for column, count in zip(columns, counts.missing_by_column, strict=True)
                ],
            ),
            duplicates=QualityDuplicateMetrics(
                duplicate_rows=counts.duplicate_rows,
                duplicate_percentage=_percentage(counts.duplicate_rows, rows),
                duplicate_groups=counts.duplicate_groups,
            ),
            rules=evaluate_quality_rules(rows, len(columns), missing, counts.duplicate_rows),
        )
        if len(result.model_dump_json().encode("utf-8")) > self.limits.max_response_bytes:
            raise QualityTooLargeError
        return result
