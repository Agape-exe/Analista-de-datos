"""Conversion of local column values into arrays for deterministic statistics."""

from numbers import Real

import numpy as np

from app.shared.application.errors import AnalysisNotApplicableError
from app.shared.contracts.datasource import RegisteredDataset
from app.shared.domain.enums.semantic_type import SemanticType

ASSOCIABLE = (SemanticType.NUMERIC, SemanticType.CATEGORICAL)


def numeric_array(values: list[object]) -> np.ndarray:
    """Float array with NaN for missing values; non-numeric values are rejected."""
    converted: list[float] = []
    for value in values:
        if value is None:
            converted.append(np.nan)
        elif isinstance(value, Real) and not isinstance(value, bool):
            converted.append(float(value))
        else:
            raise AnalysisNotApplicableError(f"Non-numeric value found: {value!r}")
    return np.asarray(converted, dtype=float)


def label_array(values: list[object]) -> np.ndarray:
    """Object array of string labels; None marks a missing value."""
    return np.asarray([None if value is None else str(value) for value in values], dtype=object)


def column_array(data: RegisteredDataset, name: str) -> np.ndarray:
    role = data.semantic_type(name)
    if role == SemanticType.NUMERIC:
        return numeric_array(data.values(name))
    if role == SemanticType.CATEGORICAL:
        return label_array(data.values(name))
    raise AnalysisNotApplicableError(f"{name}: semantic type {role} is not supported here.")


def present(values: np.ndarray) -> np.ndarray:
    """Boolean mask of observed (non-missing) entries for numeric or label arrays."""
    if values.dtype == object:
        return np.not_equal(values, None)
    return ~np.isnan(values)


def require_role(data: RegisteredDataset, name: str, *roles: SemanticType) -> None:
    role = data.semantic_type(name)
    if role not in roles:
        expected = " or ".join(str(item) for item in roles)
        raise AnalysisNotApplicableError(f"{name}: expected {expected} column, found {role}.")
