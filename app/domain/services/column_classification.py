import math
import re
from datetime import date, datetime
from numbers import Real
from uuid import UUID

from app.domain.enums.semantic_type import SemanticType
from app.domain.enums.statuses import DictionarySource
from app.domain.models.data_dictionary import DataDictionaryEntry
from app.domain.models.dataset import ColumnProfile, ColumnSchema, ProfilingOptions


def _name_tokens(name: str) -> set[str]:
    # "N°" (degree sign) is a common spelling of "Nº"; unify it so both form one token.
    separated = re.sub(r"([a-z])([A-Z])", r"\1_\2", name.replace("°", "º"))
    text = separated.casefold().replace("_", " ")
    tokens = set(re.findall(r"\w+", text))
    # "Nº de pagos" counts things, whereas "Nº predio" names one; only the latter is an ID.
    if re.search(r"\bnº\s+de\b", text):
        tokens.discard("nº")
    return tokens


def _is_uuid(value: object) -> bool:
    try:
        UUID(str(value))
    except (ValueError, AttributeError):
        return False
    return True


def _date_format(values: list[object], options: ProfilingOptions) -> str | None:
    if all(isinstance(value, date) for value in values):
        return "native datetime"
    if not all(isinstance(value, str) for value in values):
        return None
    # A format is abandoned once its failures make the configured ratio unreachable.
    allowed_failures = len(values) - math.ceil(options.temporal_parse_ratio * len(values))
    for date_format in options.temporal_formats:
        failures = 0
        for value in values:
            try:
                datetime.strptime(str(value).strip(), date_format)
            except ValueError:
                failures += 1
                if failures > allowed_failures:
                    break
        else:
            return date_format
    return None


def _infer(
    name: str, values: list[object], unique: int, options: ProfilingOptions
) -> tuple[SemanticType, str, list[str]]:
    if not values:
        return SemanticType.UNKNOWN, "No non-null values available for inference.", []
    tokens = _name_tokens(name)
    numeric = all(isinstance(value, Real) and not isinstance(value, bool) for value in values)
    discrete = all(
        (isinstance(value, Real) and not isinstance(value, bool) and float(value).is_integer())
        or (
            isinstance(value, str)
            and not any(char.isspace() for char in value)
            and len(value) <= options.identifier_max_length
        )
        for value in values
    )
    if tokens.intersection(options.identifier_name_tokens) and discrete:
        warnings = (
            []
            if unique == len(values)
            else ["Identifier candidate is not unique; it may be a foreign key, not a primary key."]
        )
        return SemanticType.IDENTIFIER, "Identifier name token and discrete values.", warnings
    if all(_is_uuid(value) for value in values):
        return SemanticType.IDENTIFIER, "Values have UUID structure.", []
    date_format = _date_format(values, options)
    if date_format:
        return SemanticType.TEMPORAL, f"Values match configured date format {date_format}.", []
    if all(isinstance(value, bool) for value in values):
        return SemanticType.CATEGORICAL, "Boolean values represent categories.", []
    if numeric:
        return SemanticType.NUMERIC, "Observed numeric values; uniqueness alone is not an ID.", []
    if all(isinstance(value, str) for value in values):
        if unique / len(values) >= options.identifier_unique_ratio and all(
            re.fullmatch(r"0\d+", str(value)) for value in values
        ):
            return SemanticType.IDENTIFIER, "Near-unique digit codes with leading zeros.", []
        if tokens.intersection(options.text_name_tokens):
            return SemanticType.TEXT, "Column name suggests free text; meaning is unverified.", []
        short = all(len(str(value)) <= options.categorical_max_length for value in values)
        if short and (
            unique <= options.categorical_max_unique
            or unique / len(values) <= options.categorical_unique_ratio
        ):
            return SemanticType.CATEGORICAL, "Short labels and configured cardinality policy.", []
        return SemanticType.TEXT, "Text values outside the categorical policy.", []
    return SemanticType.UNKNOWN, "Mixed or unsupported local value types.", []


def _compatible(role: SemanticType, values: list[object], options: ProfilingOptions) -> bool:
    if not values:
        return False
    if role == SemanticType.NUMERIC:
        return all(isinstance(value, Real) and not isinstance(value, bool) for value in values)
    if role == SemanticType.TEMPORAL:
        return _date_format(values, options) is not None
    return True


def classify_column(
    schema: ColumnSchema,
    values: list[object],
    options: ProfilingOptions,
    declared: DataDictionaryEntry | None = None,
) -> ColumnProfile:
    """Infer a role locally and respect compatible explicit dictionary annotations."""
    observed = [value for value in values if value is not None]
    unique = len(set(observed))
    role, reason, warnings = _infer(schema.name, observed, unique, options)
    source = DictionarySource.INFERRED
    if declared is not None and declared.semantic_type is not None:
        try:
            declared_role = SemanticType(declared.semantic_type)
        except ValueError:
            warnings.append(f"Unsupported dictionary semantic type: {declared.semantic_type}")
        else:
            if _compatible(declared_role, observed, options):
                if declared_role != role:
                    warnings = []
                role = declared_role
                reason = "Compatible semantic role supplied by the data dictionary."
                source = (
                    DictionarySource.INFERRED
                    if "semantic_type" in declared.inferred_fields
                    else declared.source
                )
            else:
                warnings.append("Dictionary semantic role contradicts observed values.")
    return ColumnProfile(
        column_name=schema.name,
        data_type=schema.data_type,
        semantic_type=role,
        missing_count=len(values) - len(observed),
        unique_count=unique,
        classification_source=source,
        classification_reason=reason,
        warnings=warnings,
    )
