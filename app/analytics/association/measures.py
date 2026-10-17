"""Pure association measures with a common, comparable score in [0, 1].

The score is correlation-like so different methods can be ranked together:
|r| (Pearson), |rho| (Spearman), Cramer's V, eta (sqrt of eta squared) for ANOVA,
sqrt(epsilon squared) for Kruskal-Wallis and Linfoot's informational coefficient
sqrt(1 - exp(-2 MI)) for mutual information.
"""

import math
import warnings
from dataclasses import dataclass, field

import numpy as np
from scipy import stats
from sklearn.feature_selection import mutual_info_classif, mutual_info_regression

from app.analytics.columns import present
from app.application.errors import AnalysisNotApplicableError

Detail = float | int | str | bool | list[float] | list[int] | None


@dataclass
class Measure:
    method: str
    statistic: float
    effect_size: float
    score: float
    sample_size: int
    p_value: float | None = None
    details: dict[str, Detail] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _clip_score(value: float) -> float:
    return float(min(max(value, 0.0), 1.0)) if math.isfinite(value) else 0.0


def _paired_numeric(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mask = ~np.isnan(x) & ~np.isnan(y)
    x, y = x[mask], y[mask]
    if len(x) < 3:
        raise AnalysisNotApplicableError("At least 3 complete pairs are required.")
    if np.ptp(x) == 0 or np.ptp(y) == 0:
        raise AnalysisNotApplicableError("Correlation is undefined for a constant column.")
    return x, y


def pearson(x: np.ndarray, y: np.ndarray) -> Measure:
    x, y = _paired_numeric(x, y)
    result = stats.pearsonr(x, y)
    interval = result.confidence_interval()
    r = float(result.statistic)
    return Measure(
        method="pearson",
        statistic=r,
        effect_size=r,
        score=_clip_score(abs(r)),
        sample_size=len(x),
        p_value=float(result.pvalue),
        details={"confidence_interval": [float(interval.low), float(interval.high)]},
    )


def spearman(x: np.ndarray, y: np.ndarray) -> Measure:
    x, y = _paired_numeric(x, y)
    result = stats.spearmanr(x, y)
    rho = float(result.statistic)
    return Measure(
        method="spearman",
        statistic=rho,
        effect_size=rho,
        score=_clip_score(abs(rho)),
        sample_size=len(x),
        p_value=float(result.pvalue),
    )


def contingency_table(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, list[str], list[str]]:
    mask = present(x) & present(y)
    rows, row_index = np.unique(x[mask].astype(str), return_inverse=True)
    columns, column_index = np.unique(y[mask].astype(str), return_inverse=True)
    table = np.zeros((len(rows), len(columns)), dtype=int)
    np.add.at(table, (row_index, column_index), 1)
    return table, rows.tolist(), columns.tolist()


def _chi_square(table: np.ndarray) -> tuple[float, float, int, np.ndarray]:
    if table.shape[0] < 2 or table.shape[1] < 2:
        raise AnalysisNotApplicableError("Both columns need at least 2 observed categories.")
    result = stats.chi2_contingency(table, correction=False)
    return float(result.statistic), float(result.pvalue), int(result.dof), result.expected_freq


def _expected_warning(expected: np.ndarray) -> list[str]:
    small = float(np.mean(expected < 5))
    if small > 0.2:
        return [
            f"{small:.0%} of expected frequencies are below 5; "
            "the chi-square approximation may be unreliable."
        ]
    return []


def _cramers_v(chi2: float, table: np.ndarray) -> float:
    return math.sqrt(chi2 / (int(table.sum()) * (min(table.shape) - 1)))


def chi_square(x: np.ndarray, y: np.ndarray) -> Measure:
    table, _, _ = contingency_table(x, y)
    chi2, p_value, dof, expected = _chi_square(table)
    v = _cramers_v(chi2, table)
    return Measure(
        method="chi_square",
        statistic=chi2,
        effect_size=v,
        score=_clip_score(v),
        sample_size=int(table.sum()),
        p_value=p_value,
        details={"degrees_of_freedom": dof, "cramers_v": v, "shape": list(table.shape)},
        warnings=_expected_warning(expected),
    )


def cramers_v(x: np.ndarray, y: np.ndarray) -> Measure:
    table, _, _ = contingency_table(x, y)
    chi2, p_value, dof, expected = _chi_square(table)
    v = _cramers_v(chi2, table)
    return Measure(
        method="cramers_v",
        statistic=v,
        effect_size=v,
        score=_clip_score(v),
        sample_size=int(table.sum()),
        p_value=p_value,
        details={"chi_square": chi2, "degrees_of_freedom": dof},
        warnings=_expected_warning(expected),
    )


def numeric_groups(values: np.ndarray, labels: np.ndarray) -> dict[str, np.ndarray]:
    """Group numeric values by label after pairwise deletion; groups need 2+ values."""
    groups: dict[str, list[float]] = {}
    for value, label in zip(values, labels, strict=True):
        if label is not None and not np.isnan(value):
            groups.setdefault(str(label), []).append(float(value))
    usable = {label: np.asarray(items) for label, items in groups.items() if len(items) >= 2}
    if len(usable) < 2:
        raise AnalysisNotApplicableError("At least 2 groups with 2+ observations are required.")
    if np.ptp(np.concatenate(list(usable.values()))) == 0:
        raise AnalysisNotApplicableError("The numeric column is constant across groups.")
    return dict(sorted(usable.items()))


def _excluded_groups(values: np.ndarray, labels: np.ndarray, used: int) -> list[str]:
    observed = {
        str(label)
        for value, label in zip(values, labels, strict=True)
        if label is not None and not np.isnan(value)
    }
    excluded = len(observed) - used
    return (
        [f"{excluded} group(s) with fewer than 2 observations were excluded."] if excluded else []
    )


def group_assumptions(groups: dict[str, np.ndarray], alpha: float) -> dict[str, Detail]:
    """Shapiro-Wilk per group (3..5000 obs) and Levene for equal variances."""
    normal: bool | None = None
    testable = [g for g in groups.values() if 3 <= len(g) <= 5000 and np.ptp(g) > 0]
    if testable:
        normal = all(float(stats.shapiro(group).pvalue) > alpha for group in testable)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        levene_p = float(stats.levene(*groups.values()).pvalue)
    equal_variances = None if math.isnan(levene_p) else levene_p > alpha
    return {"normal_groups": normal, "equal_variances": equal_variances}


def anova(values: np.ndarray, labels: np.ndarray, alpha: float) -> Measure:
    groups = numeric_groups(values, labels)
    result = stats.f_oneway(*groups.values())
    pooled = np.concatenate(list(groups.values()))
    total = float(np.sum((pooled - pooled.mean()) ** 2))
    between = sum(len(g) * float((g.mean() - pooled.mean()) ** 2) for g in groups.values())
    eta_squared = between / total if total else 0.0
    assumptions = group_assumptions(groups, alpha)
    notes = _excluded_groups(values, labels, len(groups))
    if assumptions["normal_groups"] is False or assumptions["equal_variances"] is False:
        notes.append("ANOVA assumptions are not met; prefer Kruskal-Wallis.")
    return Measure(
        method="anova",
        statistic=float(result.statistic),
        effect_size=eta_squared,
        score=_clip_score(math.sqrt(max(eta_squared, 0.0))),
        sample_size=len(pooled),
        p_value=float(result.pvalue),
        details={"groups": len(groups), "eta_squared": eta_squared, **assumptions},
        warnings=notes,
    )


def kruskal_wallis(values: np.ndarray, labels: np.ndarray) -> Measure:
    groups = numeric_groups(values, labels)
    result = stats.kruskal(*groups.values())
    n = sum(len(group) for group in groups.values())
    epsilon_squared = float(result.statistic) / (n - 1)
    return Measure(
        method="kruskal_wallis",
        statistic=float(result.statistic),
        effect_size=epsilon_squared,
        score=_clip_score(math.sqrt(max(epsilon_squared, 0.0))),
        sample_size=n,
        p_value=float(result.pvalue),
        details={"groups": len(groups), "epsilon_squared": epsilon_squared},
        warnings=_excluded_groups(values, labels, len(groups)),
    )


def group_difference(values: np.ndarray, labels: np.ndarray, alpha: float) -> Measure:
    """ANOVA when groups look normal with equal variances, otherwise Kruskal-Wallis."""
    assumptions = group_assumptions(numeric_groups(values, labels), alpha)
    if assumptions["normal_groups"] and assumptions["equal_variances"]:
        return anova(values, labels, alpha)
    measure = kruskal_wallis(values, labels)
    measure.details.update(assumptions)
    return measure


def _encode(values: np.ndarray) -> tuple[np.ndarray, bool]:
    if values.dtype == object:
        _, codes = np.unique(values.astype(str), return_inverse=True)
        return codes.astype(float), True
    return values.astype(float), False


def mutual_information(x: np.ndarray, y: np.ndarray, neighbors: int, seed: int) -> Measure:
    """kNN mutual information in nats; no p-value, so it is supporting evidence only."""
    mask = present(x) & present(y)
    features, x_discrete = _encode(x[mask])
    target, y_discrete = _encode(y[mask])
    n = len(target)
    if n <= neighbors + 1:
        raise AnalysisNotApplicableError(
            f"Mutual information needs more than {neighbors + 1} rows."
        )
    if np.ptp(features) == 0 or np.ptp(target) == 0:
        raise AnalysisNotApplicableError("Mutual information is undefined for a constant column.")
    estimator = mutual_info_regression
    if y_discrete:
        estimator, target = mutual_info_classif, target.astype(int)
    mi = float(
        estimator(
            features.reshape(-1, 1),
            target,
            discrete_features=[x_discrete],
            n_neighbors=neighbors,
            random_state=seed,
        )[0]
    )
    mi = max(mi, 0.0)
    return Measure(
        method="mutual_information",
        statistic=mi,
        effect_size=mi,
        score=_clip_score(math.sqrt(1 - math.exp(-2 * mi))),
        sample_size=n,
        details={"unit": "nats"},
    )


def benjamini_hochberg(p_values: list[float]) -> list[float]:
    """False discovery rate adjusted p-values, returned in the original order."""
    if not p_values:
        return []
    return [float(value) for value in stats.false_discovery_control(p_values, method="bh")]
