"""Deterministic quality rules and local safety policy; no infrastructure."""

from dataclasses import dataclass
from enum import StrEnum

from pydantic import Field

from app.shared.domain.models.base import DomainModel


class QualityTooLargeError(Exception):
    """An exact evaluation exceeds the documented resource budget."""


class QualityUnsupportedError(Exception):
    """The registered table or its values cannot be evaluated safely."""


@dataclass(frozen=True)
class QualityLimits:
    """Per-request ceilings, injectable for tests; not quality score thresholds."""

    max_rows: int = 250_000
    max_columns: int = 1_000
    max_cells: int = 2_000_000
    max_data_bytes: int = 64 * 1024 * 1024
    max_value_chars: int = 65_536
    max_response_bytes: int = 1_048_576

    def __post_init__(self) -> None:
        if any(value < 1 for value in vars(self).values()):
            raise ValueError("Quality budgets must be positive")

    def check_shape(self, rows: int, columns: int) -> None:
        if rows < 0 or columns < 0:
            raise QualityUnsupportedError
        if rows > self.max_rows or columns > self.max_columns or rows * columns > self.max_cells:
            raise QualityTooLargeError


@dataclass(frozen=True)
class QualityCounts:
    """Exact counts only; positions and cell contents never leave the adapter."""

    missing_by_column: tuple[int, ...]
    incomplete_rows: int
    duplicate_rows: int  # Additional occurrences, excluding the first in each group.
    duplicate_groups: int


class QualityRuleStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_EVALUATED = "NOT_EVALUATED"


class QualityRuleResult(DomainModel):
    rule_id: str
    description: str
    status: QualityRuleStatus
    observed_count: int | None = Field(default=None, ge=0)
    reason: str | None = None


def evaluate_quality_rules(
    rows: int, columns: int, missing_cells: int, duplicate_rows: int
) -> list[QualityRuleResult]:
    """No inferred thresholds or global score. Empty tables provide no evidence."""
    rules = (
        ("NO_MISSING_VALUES", "Ausencia de valores faltantes", missing_cells),
        ("NO_DUPLICATE_ROWS", "Ausencia de filas completamente duplicadas", duplicate_rows),
    )
    return [
        QualityRuleResult(
            rule_id=rule_id,
            description=description,
            status=(
                QualityRuleStatus.NOT_EVALUATED
                if not rows or not columns
                else QualityRuleStatus.FAIL
                if count
                else QualityRuleStatus.PASS
            ),
            observed_count=count if rows and columns else None,
            reason=(
                "El dataset no contiene filas o columnas evaluables."
                if not rows or not columns
                else "Se observaron incumplimientos de la regla."
                if count
                else None
            ),
        )
        for rule_id, description, count in rules
    ]
