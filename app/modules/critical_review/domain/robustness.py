from math import isfinite


# FUNCIÓN 1: CALCULAR EL DEBILITAMIENTO DE UNA CORRELACIÓN
def calculate_weakening(original: float, adjusted: float) -> float:
    """
    Calcula la reducción proporcional en la magnitud
    de una correlación después de aplicar un control.
    """

    if not isfinite(original) or not isfinite(adjusted):
        raise ValueError("Las correlaciones deben ser finitas.")

    if abs(original) > 1 or abs(adjusted) > 1:
        raise ValueError("Las correlaciones deben estar entre -1 y 1.")

    if original == 0:
        raise ValueError("La correlación original no puede ser cero.")

    weakening = (abs(original) - abs(adjusted)) / abs(original)

    return max(0.0, weakening)


# FUNCIÓN 2: DETECTAR CAMBIOS DE SIGNO
def detect_sign_change(original: float, adjusted: float) -> bool:
    """
    Detecta si una correlación cambia de positiva
    a negativa o viceversa.
    """

    if not isfinite(original) or not isfinite(adjusted):
        raise ValueError("Las correlaciones deben ser finitas.")

    if abs(original) > 1 or abs(adjusted) > 1:
        raise ValueError("Las correlaciones deben estar entre -1 y 1.")

    return original * adjusted < 0


# FUNCIÓN 3: DETECTAR SENSIBILIDAD A VARIABLES DE CONTROL
def is_control_sensitive(original: float, adjusted: float) -> bool:
    """
    Identifica una asociación que se debilita notablemente
    después de controlar una tercera variable.

    Los umbrales utilizados son provisionales.
    """

    weakening = calculate_weakening(original, adjusted)

    return abs(original) >= 0.50 and abs(adjusted) < 0.30 and weakening >= 0.70


# FUNCIÓN 4: COMPARAR CORRELACIONES PEARSON Y SPEARMAN
def calculate_correlation_disagreement(
    pearson: float,
    spearman: float,
) -> float:
    """
    Calcula la diferencia absoluta entre los
    coeficientes de Pearson y Spearman.

    Una diferencia elevada requiere revisión,
    pero no demuestra una relación espuria.
    """

    if not isfinite(pearson) or not isfinite(spearman):
        raise ValueError("Las correlaciones deben ser finitas.")

    if abs(pearson) > 1 or abs(spearman) > 1:
        raise ValueError("Las correlaciones deben estar entre -1 y 1.")

    disagreement = abs(pearson - spearman)

    return disagreement


# FUNCIÓN 5: MEDIR EL IMPACTO DE LOS VALORES ATÍPICOS
def calculate_outlier_impact(
    original: float,
    without_outliers: float,
) -> float:
    """
    Calcula cuánto cambia una correlación después
    de eliminar los valores atípicos.

    No realiza la eliminación de outliers.
    Compara dos resultados estadísticos existentes.
    """

    impact = calculate_correlation_disagreement(
        original,
        without_outliers,
    )

    return impact


# FUNCIÓN 6: MEDIR DIFERENCIAS ENTRE SUBGRUPOS
def calculate_subgroup_heterogeneity(
    correlations: list[float],
) -> float:
    """
    Calcula la diferencia entre la correlación máxima
    y mínima de distintos subgrupos.

    Una diferencia elevada puede indicar heterogeneidad
    en la asociación, pero no demuestra espuriedad.
    """

    # Se necesitan al menos dos subgrupos
    if len(correlations) < 2:
        raise ValueError("Se necesitan al menos dos subgrupos.")

    # Validar los coeficientes de correlación
    if not all(isfinite(value) and abs(value) <= 1 for value in correlations):
        raise ValueError("Las correlaciones deben ser finitas y estar entre -1 y 1.")

    # Calcular la diferencia máxima entre subgrupos
    heterogeneity = max(correlations) - min(correlations)

    return heterogeneity


# FUNCIÓN 7: MEDIR CAMBIOS TEMPORALES EN CORRELACIONES
def calculate_temporal_variation(
    correlations: list[float],
) -> float:
    """
    Calcula la mayor diferencia absoluta entre las
    correlaciones de periodos consecutivos.

    Las correlaciones deben estar ordenadas
    cronológicamente.

    Una variación elevada requiere revisión,
    pero no demuestra que la relación sea espuria.
    """

    # Se necesitan al menos dos periodos
    if len(correlations) < 2:
        raise ValueError("Se necesitan al menos dos periodos.")

    # Validar que las correlaciones sean válidas
    if not all(isfinite(value) and abs(value) <= 1 for value in correlations):
        raise ValueError("Las correlaciones deben ser finitas y estar entre -1 y 1.")

    # Calcular diferencias entre periodos consecutivos
    variations = [abs(correlations[i] - correlations[i - 1]) for i in range(1, len(correlations))]

    # Devolver el mayor cambio detectado
    return max(variations)
