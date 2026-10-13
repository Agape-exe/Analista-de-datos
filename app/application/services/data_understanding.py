import asyncio
from time import perf_counter

from app.application.dto.analysis_input import AnalysisInput
from app.application.dto.data_understanding import DataUnderstandingResult
from app.application.dto.datasource import LoadedDataset
from app.application.errors import DataSourceError
from app.domain.enums.statuses import DictionarySource
from app.domain.models.data_dictionary import DataDictionary, DataDictionaryEntry
from app.domain.models.dataset import ColumnProfile, DatasetProfile, ProfilingOptions
from app.domain.services.column_classification import classify_column
from app.ports.datasource import DataSource


def _same_type(declared: str, observed: str) -> bool:
    aliases = {
        "int": "integer",
        "int64": "integer",
        "integer": "integer",
        "float": "number",
        "float64": "number",
        "double": "number",
        "number": "number",
        "str": "string",
        "object": "string",
        "string": "string",
        "text": "string",
        "bool": "boolean",
        "boolean": "boolean",
    }
    return aliases.get(declared.casefold(), declared.casefold()) == aliases.get(
        observed.casefold(), observed.casefold()
    )


def _dictionary_entry(
    profile: ColumnProfile, declared: DataDictionaryEntry | None
) -> DataDictionaryEntry:
    inferred = {
        "description": (
            f"Column '{profile.column_name}' with observed type {profile.data_type} "
            f"and proposed role {profile.semantic_type}. Business meaning is unverified."
        ),
        "data_type": profile.data_type,
        "semantic_type": profile.semantic_type.value if profile.semantic_type is not None else None,
    }
    if declared is None:
        return DataDictionaryEntry(
            column_name=profile.column_name,
            source=DictionarySource.INFERRED,
            **inferred,
            inferred_fields=list(inferred),
            inference_reason=profile.classification_reason,
        )
    fields = {key: value for key, value in inferred.items() if getattr(declared, key) is None}
    # Preserve original provenance; field-level markers identify inferred additions.
    return DataDictionaryEntry.model_validate(
        declared.model_dump()
        | fields
        | {
            "inferred_fields": sorted(set(declared.inferred_fields) | set(fields)),
            "inference_reason": profile.classification_reason
            if fields
            else declared.inference_reason,
        }
    )


class DataUnderstandingService:
    """Read through a port, profile locally, and reconcile dictionary metadata."""

    def __init__(self, datasource: DataSource, options: ProfilingOptions) -> None:
        self.datasource = datasource
        self.options = options

    async def understand(self, analysis_input: AnalysisInput) -> DataUnderstandingResult:
        started = perf_counter()
        dataset = await self.datasource.read(analysis_input.source)
        profile, dictionary, warnings = await asyncio.to_thread(
            self._profile, dataset, analysis_input
        )
        return DataUnderstandingResult(
            dataset=dataset,
            profile=profile,
            data_dictionary=dictionary,
            warnings=warnings,
            profiling_time=perf_counter() - started,
        )

    def _profile(
        self, dataset: LoadedDataset, analysis_input: AnalysisInput
    ) -> tuple[DatasetProfile, DataDictionary, list[str]]:
        observed_names = {column.name for column in dataset.schema.columns}
        warnings: list[str] = []
        declared_schema = analysis_input.dataset_schema
        if declared_schema is not None:
            if {column.name for column in declared_schema.columns} != observed_names:
                raise DataSourceError("Supplied schema columns do not match source columns")
            actual_types = {column.name: column.data_type for column in dataset.schema.columns}
            actual_nullable = {column.name: column.nullable for column in dataset.schema.columns}
            for column in declared_schema.columns:
                if not column.nullable and actual_nullable[column.name]:
                    raise DataSourceError(
                        f"Column '{column.name}' violates the non-nullable supplied schema"
                    )
                if not _same_type(column.data_type, actual_types[column.name]):
                    warnings.append(
                        f"{column.name}: supplied schema type differs from observed type."
                    )
        entries = {
            entry.column_name: entry
            for entry in (analysis_input.data_dictionary or DataDictionary()).entries
        }
        for name in sorted(entries.keys() - observed_names):
            warnings.append(
                f"Dictionary column '{name}' is absent from the source and was excluded."
            )
        profiles: list[ColumnProfile] = []
        dictionary_entries: list[DataDictionaryEntry] = []
        for column in dataset.schema.columns:
            declared = entries.get(column.name)
            values = dataset.table.column(column.name)
            if len(values) != dataset.row_count:
                raise DataSourceError(f"Column '{column.name}' has an inconsistent row count")
            profile = classify_column(column, values, self.options, declared)
            profiles.append(profile)
            warnings.extend(f"{column.name}: {warning}" for warning in profile.warnings)
            if (
                declared
                and declared.data_type
                and not _same_type(declared.data_type, column.data_type)
            ):
                warnings.append(f"{column.name}: dictionary data type differs from observed type.")
            dictionary_entries.append(_dictionary_entry(profile, declared))
        return (
            DatasetProfile(
                dataset_id=dataset.dataset_id, row_count=dataset.row_count, columns=profiles
            ),
            DataDictionary(entries=dictionary_entries),
            warnings,
        )
