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
