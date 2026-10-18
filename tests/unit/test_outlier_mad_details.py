import numpy as np
import pytest

from app.modules.exploration.adapters.analytics.profiling.measures import outliers

NORMAL = list(range(-20, 21))


def run(values: list[float | None], limit: int = 20) -> dict:
    return outliers(np.asarray([np.nan if v is None else v for v in values]), 1.5, 3.5, limit)


def test_bounds_in_value_units_match_the_robust_z_rule() -> None:
    values = [None, 500.0] + NORMAL + [-400.0, 30.0]
    mad = run(values)["mad"]
    observed = np.asarray([v for v in values if v is not None])
    median = float(np.median(observed))
    deviation = float(np.median(np.abs(observed - median)))
    assert mad["median"] == round(median, 6) and mad["mad"] == round(deviation, 6)
    spread = 3.5 * deviation / 0.6745
    assert mad["lower_bound"] == round(median - spread, 6)
    assert mad["upper_bound"] == round(median + spread, 6)
    flagged = [v for v in observed if abs(v - median) > spread]
    assert mad["count"] == len(flagged) == len(mad["example_rows"])


def test_examples_reference_original_rows_ordered_by_robust_z() -> None:
    values = [None, 500.0] + NORMAL + [-400.0, None, 600.0]
    mad = run(values)["mad"]
    rows = mad["example_rows"]
    assert [row["row_index"] for row in rows] == [45, 1, 43]
    assert [row["value"] for row in rows] == mad["examples"] == [600.0, 500.0, -400.0]
    for row in rows:
        assert values[row["row_index"]] == row["value"]
        assert abs(row["robust_z"]) > 3.5
        assert np.sign(row["robust_z"]) == np.sign(row["value"])


@pytest.mark.parametrize("limit", [0, 1, 2])
def test_max_examples_bounds_mad_examples_without_affecting_counts(limit: int) -> None:
    mad = run([500.0, -500.0] + NORMAL + [600.0], limit)["mad"]
    assert mad["count"] == 3
    assert len(mad["examples"]) == len(mad["example_rows"]) == limit


@pytest.mark.parametrize(
    "values", [[7.0] * 40, [5.0] * 30 + [1.0, 2.0, 100.0]], ids=["constant", "mad-zero"]
)
def test_mad_zero_keeps_bounds_and_examples_empty(values: list[float]) -> None:
    mad = run(values)["mad"]
    assert mad["mad"] == 0
    assert mad["count"] is None and mad["percentage"] is None
    assert mad["lower_bound"] is None and mad["upper_bound"] is None
    assert mad["examples"] == [] and mad["example_rows"] == []
