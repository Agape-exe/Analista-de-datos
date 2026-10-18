"""Pure univariate profiling computations returning JSON-ready dictionaries."""

from collections import Counter

import numpy as np
from scipy import stats

from app.modules.exploration.adapters.analytics.base import finite, probability


def numeric_summary(values: np.ndarray) -> dict[str, object]:
    observed = values[~np.isnan(values)]
    n = len(observed)
    summary: dict[str, object] = {"count": n, "missing": int(len(values) - n)}
    if not n:
        return summary
    q1, median, q3 = np.percentile(observed, [25, 50, 75])
    mean = float(observed.mean())
    std = float(observed.std(ddof=1)) if n > 1 else None
    summary.update(
        {
            "mean": finite(mean),
            "std": finite(std),
            "min": finite(observed.min()),
            "q1": finite(q1),
            "median": finite(median),
            "q3": finite(q3),
            "max": finite(observed.max()),
            "iqr": finite(q3 - q1),
            "coefficient_of_variation": finite(std / mean) if std is not None and mean else None,
            "skewness": finite(stats.skew(observed, bias=False))
            if n > 2 and np.ptp(observed)
            else None,
            "kurtosis": finite(stats.kurtosis(observed, bias=False))
            if n > 3 and np.ptp(observed)
            else None,
        }
    )
    return summary


def grouped_summary(
    values: np.ndarray, labels: np.ndarray, max_groups: int, minimum_sample_size: int
) -> dict[str, object]:
    """Per-category numeric summary of existing groups, largest first, with omissions explicit.

    Groups are the categories already present in the data; nothing is discovered or clustered.
    Rows without a category are counted apart instead of forming a group.
    """
    labelled = np.not_equal(labels, None)
    grouped: dict[str, list[int]] = {}
    for position in np.flatnonzero(labelled):
        grouped.setdefault(str(labels[position]), []).append(int(position))
    ordered = sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0]))
    shown, omitted = ordered[:max_groups], ordered[max_groups:]
    groups = []
    for label, positions in shown:
        summary = numeric_summary(values[positions])
        groups.append(
            {
                "label": label,
                "rows": len(positions),
                **summary,
                "small_sample": int(summary["count"]) < minimum_sample_size,
            }
        )
    omitted_rows = sum(len(positions) for _, positions in omitted)
    unlabelled = values[~labelled]
    return {
        "total_groups": len(ordered),
        "shown_groups": len(shown),
        "max_groups": max_groups,
        "minimum_sample_size": minimum_sample_size,
        "groups": groups,
        "omitted": {
            "groups": len(omitted),
            "rows": omitted_rows,
            "observed": int(sum((~np.isnan(values[positions])).sum() for _, positions in omitted)),
        },
        "missing_group": {
            "rows": len(unlabelled),
            "observed": int((~np.isnan(unlabelled)).sum()),
        },
        "overall": numeric_summary(values),
    }


def frequencies(labels: list[str], top: int) -> dict[str, object]:
    counts = Counter(labels)
    total = len(labels)
    ranked = counts.most_common()
    shown = ranked[:top]
    other = total - sum(count for _, count in shown)
    return {
        "count": total,
        "unique": len(counts),
        "mode": ranked[0][0] if ranked else None,
        "mode_frequency": ranked[0][1] if ranked else 0,
        "top_values": [
            {"value": value, "count": count, "percentage": finite(100 * count / total)}
            for value, count in shown
        ],
        "other_count": other,
    }


def histogram(values: np.ndarray, max_bins: int) -> dict[str, object]:
    observed = values[~np.isnan(values)]
    if not len(observed):
        return {"edges": [], "counts": []}
    edges = np.histogram_bin_edges(observed, bins="auto")
    if len(edges) - 1 > max_bins:
        edges = np.histogram_bin_edges(observed, bins=max_bins)
    counts, edges = np.histogram(observed, bins=edges)
    return {"edges": [finite(edge) for edge in edges], "counts": counts.tolist()}


def normality(values: np.ndarray, alpha: float) -> dict[str, object]:
    """D'Agostino-Pearson for n >= 20, Shapiro-Wilk for smaller samples (n >= 3)."""
    observed = values[~np.isnan(values)]
    if len(observed) < 3 or np.ptp(observed) == 0:
        return {"test": None, "p_value": None, "normal": None}
    if len(observed) >= 20:
        test, p_value = "dagostino_pearson", float(stats.normaltest(observed).pvalue)
    else:
        test, p_value = "shapiro_wilk", float(stats.shapiro(observed).pvalue)
    return {"test": test, "p_value": probability(p_value), "normal": p_value > alpha}


def shape(skewness: object) -> str | None:
    if not isinstance(skewness, float):
        return None
    if skewness > 0.5:
        return "right-skewed"
    if skewness < -0.5:
        return "left-skewed"
    return "approximately symmetric"


def outliers(
    values: np.ndarray, iqr_multiplier: float, mad_threshold: float, max_examples: int
) -> dict[str, object]:
    """Tukey IQR fences and robust z-scores (median absolute deviation)."""
    present_mask = ~np.isnan(values)
    original_positions = np.flatnonzero(present_mask)
    observed = values[present_mask]
    n = len(observed)
    q1, median, q3 = np.percentile(observed, [25, 50, 75])
    iqr = q3 - q1
    lower, upper = q1 - iqr_multiplier * iqr, q3 + iqr_multiplier * iqr
    iqr_mask = (observed < lower) | (observed > upper)
    mad = float(np.median(np.abs(observed - median)))
    mad_result: dict[str, object] = {"threshold": mad_threshold, "count": None, "percentage": None}
    if mad > 0:
        robust_z = 0.6745 * (observed - median) / mad
        mad_mask = np.abs(robust_z) > mad_threshold
        mad_result.update(count=int(mad_mask.sum()), percentage=finite(100 * mad_mask.sum() / n))
    flagged = observed[iqr_mask]
    selection = np.argsort(-np.abs(flagged - median), kind="stable")[:max_examples]
    extremes = flagged[selection]
    example_positions = original_positions[iqr_mask][selection]
    return {
        "count": n,
        "iqr": {
            "multiplier": iqr_multiplier,
            "lower_fence": finite(lower),
            "upper_fence": finite(upper),
            "count": int(iqr_mask.sum()),
            "percentage": finite(100 * iqr_mask.sum() / n),
            "examples": [finite(value) for value in extremes],
            "example_rows": [
                {"row_index": int(position), "value": finite(value)}
                for position, value in zip(example_positions, extremes, strict=True)
            ],
        },
        "mad": mad_result,
    }
