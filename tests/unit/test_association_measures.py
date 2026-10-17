import numpy as np
import pytest

from app.analytics.association import measures
from app.application.errors import AnalysisNotApplicableError

RNG = np.random.default_rng(3)


def labels(values: list[str]) -> np.ndarray:
    return np.asarray(values, dtype=object)


def test_pearson_detects_linear_relationship() -> None:
    x = RNG.normal(size=200)
    y = 2 * x + RNG.normal(scale=0.3, size=200)
    result = measures.pearson(x, y)
    assert result.effect_size > 0.9
    assert result.p_value < 1e-10
    assert result.score == pytest.approx(abs(result.effect_size))
    low, high = result.details["confidence_interval"]
    assert low < result.effect_size < high


def test_pearson_uses_pairwise_complete_rows_and_sign() -> None:
    x = np.asarray([1.0, 2.0, 3.0, np.nan, 5.0, 6.0])
    y = np.asarray([6.0, 5.0, 4.0, 3.0, np.nan, 1.0])
    result = measures.pearson(x, y)
    assert result.sample_size == 4
    assert result.effect_size == pytest.approx(-1.0)


def test_spearman_captures_monotonic_non_linear_relationship() -> None:
    x = np.linspace(0, 10, 100)
    rho = measures.spearman(x, np.exp(x)).effect_size
    assert rho == pytest.approx(1.0)
    assert measures.pearson(x, np.exp(x)).effect_size < rho


def test_constant_columns_are_not_applicable() -> None:
    with pytest.raises(AnalysisNotApplicableError, match="constant"):
        measures.pearson(np.ones(10), np.arange(10.0))


def test_chi_square_and_cramers_v() -> None:
    a = labels(["x", "y"] * 100)
    dependent = labels(["p", "q"] * 100)
    independent = labels(["p", "p", "q", "q"] * 50)
    strong = measures.cramers_v(a, dependent)
    assert strong.effect_size == pytest.approx(1.0)
    assert strong.p_value < 1e-10
    chi = measures.chi_square(a, independent)
    assert chi.effect_size == pytest.approx(0.0)
    assert chi.p_value == pytest.approx(1.0)
    assert chi.details["degrees_of_freedom"] == 1


def test_chi_square_warns_about_small_expected_frequencies() -> None:
    result = measures.chi_square(labels(list("abcab")), labels(list("xyzzx")))
    assert any("expected frequencies" in warning for warning in result.warnings)


def test_chi_square_needs_two_categories() -> None:
    with pytest.raises(AnalysisNotApplicableError):
        measures.chi_square(labels(["a"] * 10), labels(["x", "y"] * 5))


def test_anova_and_kruskal_detect_group_differences() -> None:
    groups = labels(["a"] * 50 + ["b"] * 50 + ["c"] * 50)
    values = np.concatenate([RNG.normal(0, 1, 50), RNG.normal(3, 1, 50), RNG.normal(6, 1, 50)])
    anova = measures.anova(values, groups, alpha=0.05)
    kruskal = measures.kruskal_wallis(values, groups)
    assert anova.p_value < 1e-10 and anova.details["eta_squared"] > 0.7
    assert anova.score == pytest.approx(anova.effect_size**0.5)
    assert kruskal.p_value < 1e-10 and 0 < kruskal.effect_size <= 1


def test_group_difference_switches_to_kruskal_for_skewed_groups() -> None:
    groups = labels(["a"] * 80 + ["b"] * 80)
    values = np.concatenate([RNG.exponential(1, 80), RNG.exponential(5, 80)])
    result = measures.group_difference(values, groups, alpha=0.05)
    assert result.method == "kruskal_wallis"
    assert result.details["normal_groups"] is False


def test_group_difference_keeps_anova_for_normal_groups() -> None:
    groups = labels(["a"] * 60 + ["b"] * 60)
    values = np.concatenate([RNG.normal(0, 1, 60), RNG.normal(1, 1, 60)])
    assert measures.group_difference(values, groups, alpha=0.01).method == "anova"


def test_groups_with_one_observation_are_excluded() -> None:
    groups = labels(["a"] * 10 + ["b"] * 10 + ["c"])
    values = np.concatenate([np.arange(10.0), np.arange(10.0) + 5, [1.0]])
    result = measures.kruskal_wallis(values, groups)
    assert result.details["groups"] == 2
    assert "1 group(s)" in result.warnings[0]


def test_numeric_groups_keep_row_order_and_skip_missing_pairs() -> None:
    groups = labels(["b", "a", None, "b", "a", "c", "b"])
    values = np.asarray([1.0, 2.0, 3.0, np.nan, 4.0, 5.0, 6.0])
    result = measures.numeric_groups(values, groups)
    assert list(result) == ["a", "b"]
    assert result["a"].tolist() == [2.0, 4.0]
    assert result["b"].tolist() == [1.0, 6.0]
    with pytest.raises(AnalysisNotApplicableError):
        measures.numeric_groups(np.asarray([np.nan, 1.0]), labels(["a", None]))


def test_mutual_information_detects_non_linear_dependence() -> None:
    x = RNG.uniform(-3, 3, 500)
    y = x**2 + RNG.normal(scale=0.1, size=500)
    mi = measures.mutual_information(x, y, neighbors=3, seed=0)
    assert abs(measures.pearson(x, y).effect_size) < 0.2
    assert mi.score > 0.8
    assert mi.p_value is None
    repeated = measures.mutual_information(x, y, neighbors=3, seed=0)
    assert repeated.statistic == mi.statistic


def test_mutual_information_with_categorical_target() -> None:
    target = labels(["a", "b"] * 100)
    values = np.asarray([0.0, 10.0] * 100) + RNG.normal(scale=0.1, size=200)
    assert measures.mutual_information(values, target, neighbors=3, seed=0).score > 0.8


def test_mutual_information_samples_large_inputs_reproducibly() -> None:
    x = RNG.uniform(-3, 3, 2000)
    y = x**2 + RNG.normal(scale=0.1, size=2000)
    x[0] = np.nan
    sampled = measures.mutual_information(x, y, neighbors=3, seed=0, max_rows=500)
    assert sampled.sample_size == 500
    assert sampled.details["observed_rows"] == 1999
    assert sampled.score > 0.8
    repeated = measures.mutual_information(x, y, neighbors=3, seed=0, max_rows=500)
    assert repeated.statistic == sampled.statistic
    full = measures.mutual_information(x, y, neighbors=3, seed=0, max_rows=1999)
    assert full.sample_size == 1999
    assert "observed_rows" not in full.details


def test_benjamini_hochberg_matches_reference_values() -> None:
    adjusted = measures.benjamini_hochberg([0.01, 0.04, 0.03, 0.2])
    assert adjusted == pytest.approx([0.04, 0.0533333, 0.0533333, 0.2], rel=1e-5)
    assert measures.benjamini_hochberg([]) == []
