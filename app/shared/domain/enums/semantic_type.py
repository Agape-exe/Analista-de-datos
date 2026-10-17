from enum import StrEnum


class SemanticType(StrEnum):
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    TEMPORAL = "temporal"
    IDENTIFIER = "identifier"
    TEXT = "text"
    UNKNOWN = "unknown"
