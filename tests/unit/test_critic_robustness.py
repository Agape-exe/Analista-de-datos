import pytest

from app.modules.critical_review.domain.robustness import (
    calculate_correlation_disagreement,
    calculate_outlier_impact,
    calculate_subgroup_heterogeneity,
    calculate_temporal_variation,
    calculate_weakening,
    detect_sign_change,
    is_control_sensitive,
)


# PRUEBA 1: Verificar el debilitamiento de una correlación
def test_calculate_weakening():
    resultado = calculate_weakening(0.81, 0.16)

    assert resultado == pytest.approx(0.8024691358)


# PRUEBA 2: Verificar cuando la correlación aumenta
def test_no_weakening_when_correlation_increases():
    resultado = calculate_weakening(0.60, 0.85)

    assert resultado == 0.0


# PRUEBA 3: Detectar un cambio de signo
def test_detect_sign_change():
    resultado = detect_sign_change(0.75, -0.40)

    assert resultado is True


# PRUEBA 4: Detectar una asociación sensible a variables de control
def test_is_control_sensitive():
    resultado = is_control_sensitive(0.81, 0.16)

    assert resultado is True


# PRUEBA 5: Comparar correlaciones Pearson y Spearman
def test_calculate_correlation_disagreement():
    resultado = calculate_correlation_disagreement(0.81, 0.78)

    assert resultado == pytest.approx(0.03)


# PRUEBA 6: Medir el impacto de los valores atípicos
def test_calculate_outlier_impact():
    # Correlación original con todos los datos
    original = 0.85

    # Correlación después de excluir outliers
    without_outliers = 0.30

    # Calcular cuánto cambió la correlación
    resultado = calculate_outlier_impact(
        original,
        without_outliers,
    )

    # Comprobar la diferencia absoluta esperada
    assert resultado == pytest.approx(0.55)


# PRUEBA 7: Medir la heterogeneidad entre subgrupos
def test_calculate_subgroup_heterogeneity():
    # Correlaciones obtenidas en diferentes regiones
    correlations = [0.80, -0.40]

    # Calcular la diferencia entre subgrupos
    resultado = calculate_subgroup_heterogeneity(correlations)

    # Verificar que la diferencia sea 1.20
    assert resultado == pytest.approx(1.20)


# PRUEBA 8: Evaluar la variación temporal de correlaciones
def test_calculate_temporal_variation():
    # Correlaciones ordenadas cronológicamente
    correlations = [0.80, 0.75, -0.30]

    # Calcular la mayor variación entre periodos
    resultado = calculate_temporal_variation(correlations)

    # Verificar que la mayor diferencia sea 1.05
    assert resultado == pytest.approx(1.05)


# ==========================================================
# AUD-034: PRUEBAS DE FRONTERAS Y CASOS EXTREMOS
# ==========================================================


# PRUEBA 9: Verificar casos adicionales de debilitamiento
@pytest.mark.parametrize(
    ("original", "adjusted", "expected"),
    [
        (-0.80, -0.20, 0.75),
        (0.60, 0.80, 0.0),
        (0.80, 0.0, 1.0),
        (1.0, 0.50, 0.50),
    ],
)
def test_weakening_boundary_cases(original, adjusted, expected):
    resultado = calculate_weakening(original, adjusted)
    assert resultado == pytest.approx(expected)


# PRUEBA 10: Validar cambios de signo y valores cercanos a cero
@pytest.mark.parametrize(
    ("original", "adjusted", "expected"),
    [
        (0.02, -0.02, True),
        (0.0, -0.20, False),
        (-0.50, 0.0, False),
        (-0.50, 0.25, True),
        (0.40, 0.20, False),
    ],
)
def test_sign_change_boundary_cases(original, adjusted, expected):
    assert detect_sign_change(original, adjusted) is expected


# PRUEBA 11: Verificar las fronteras de sensibilidad
@pytest.mark.parametrize(
    ("original", "adjusted", "expected"),
    [
        (0.50, 0.15, True),  # Justo en el límite de 70 %
        (0.50, 0.150001, False),  # Debilitamiento inferior a 70 %
        (0.499, 0.10, False),  # Correlación original insuficiente
        (0.60, 0.30, False),  # Ajustada debe ser menor que 0.30
        (-0.80, -0.10, True),  # Correlaciones negativas válidas
        (0.50, 0.0, True),  # Debilitamiento completo
    ],
)
def test_control_sensitivity_thresholds(original, adjusted, expected):
    assert is_control_sensitive(original, adjusted) is expected


# PRUEBA 12: Comparar diferencias extremas de correlaciones
@pytest.mark.parametrize(
    ("pearson", "spearman", "expected"),
    [
        (0.80, 0.80, 0.0),
        (1.0, -1.0, 2.0),
        (-0.30, 0.20, 0.50),
    ],
)
def test_correlation_disagreement_boundaries(pearson, spearman, expected):
    resultado = calculate_correlation_disagreement(pearson, spearman)
    assert resultado == pytest.approx(expected)


# PRUEBA 13: Evaluar cambios extremos provocados por outliers
@pytest.mark.parametrize(
    ("original", "adjusted", "expected"),
    [
        (0.85, 0.30, 0.55),
        (0.60, 0.60, 0.0),
        (-0.80, 0.60, 1.40),
    ],
)
def test_outlier_impact_boundary_cases(original, adjusted, expected):
    resultado = calculate_outlier_impact(original, adjusted)
    assert resultado == pytest.approx(expected)


# PRUEBA 14: Evaluar subgrupos homogéneos y heterogéneos
@pytest.mark.parametrize(
    ("correlations", "expected"),
    [
        ([0.10, 0.10], 0.0),
        ([-1.0, 0.0, 1.0], 2.0),
        ([-0.40, 0.80], 1.20),
    ],
)
def test_subgroup_heterogeneity_boundaries(correlations, expected):
    resultado = calculate_subgroup_heterogeneity(correlations)
    assert resultado == pytest.approx(expected)


# PRUEBA 15: Verificar cambios entre periodos consecutivos
@pytest.mark.parametrize(
    ("correlations", "expected"),
    [
        ([1.0, 0.50, 0.0], 0.50),
        ([-0.50, 0.20, 0.10], 0.70),
        ([0.0, 0.0], 0.0),
    ],
)
def test_temporal_variation_boundary_cases(correlations, expected):
    resultado = calculate_temporal_variation(correlations)
    assert resultado == pytest.approx(expected)


# ==========================================================
# AUD-034: PRUEBAS DE ENTRADAS INVÁLIDAS
# ==========================================================


# PRUEBA 16: Rechazar correlaciones originales inválidas
@pytest.mark.parametrize(
    ("original", "adjusted"),
    [
        (0.0, 0.20),
        (1.20, 0.20),
        (float("nan"), 0.20),
        (0.80, float("inf")),
    ],
)
def test_weakening_rejects_invalid_values(original, adjusted):
    with pytest.raises(ValueError):
        calculate_weakening(original, adjusted)


# PRUEBA 17: Rechazar coeficientes inválidos
@pytest.mark.parametrize(
    ("pearson", "spearman"),
    [
        (1.10, 0.50),
        (0.50, -1.20),
        (float("nan"), 0.50),
    ],
)
def test_correlation_disagreement_rejects_invalid_values(pearson, spearman):
    with pytest.raises(ValueError):
        calculate_correlation_disagreement(pearson, spearman)


# PRUEBA 18: Rechazar subgrupos no evaluables
@pytest.mark.parametrize(
    "correlations",
    [
        [],
        [0.50],
        [0.50, 1.20],
        [float("nan"), 0.20],
    ],
)
def test_subgroup_heterogeneity_rejects_invalid_values(correlations):
    with pytest.raises(ValueError):
        calculate_subgroup_heterogeneity(correlations)


# PRUEBA 19: Rechazar periodos no evaluables
@pytest.mark.parametrize(
    "correlations",
    [
        [],
        [0.50],
        [0.20, 1.10],
        [0.20, float("inf")],
    ],
)
def test_temporal_variation_rejects_invalid_values(correlations):
    with pytest.raises(ValueError):
        calculate_temporal_variation(correlations)
