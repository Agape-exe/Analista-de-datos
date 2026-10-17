import json
from math import isfinite
from numbers import Real

from app.shared.domain.models.analysis import AnalysisResult


def _number(value: object) -> str:
    if isinstance(value, Real) and not isinstance(value, bool) and isfinite(value):
        return f"{value:.3g}"
    return str(value)


def describe_result(result: AnalysisResult) -> str:
    """Present calculated results without changing their interpretation."""
    names = " y ".join(result.variables)
    values = result.result
    detail = ""

    if isinstance(values, dict):
        if result.method in {
            "pearson",
            "spearman",
            "partial_correlation",
            "correlation_without_outliers",
        }:
            coefficient = values.get("correlation")
            if coefficient is None:
                coefficient = values.get("coefficient")

            if coefficient is not None:
                labels = {
                    "pearson": "La correlación de Pearson",
                    "spearman": "La correlación de Spearman",
                    "partial_correlation": "La correlación parcial",
                    "correlation_without_outliers": "La correlación de Pearson tras el filtro IQR",
                }
                detail = f"{labels[result.method]} entre {names} fue de {_number(coefficient)}."

                if result.method == "partial_correlation":
                    control = result.metadata.get("control_variable")
                    if control is not None:
                        detail += f" Variable de control: {control}."

        elif result.method == "analyze_subgroups":
            groups = values.get("groups", [])
            measured = [
                g
                for g in groups
                if isinstance(g, dict)
                and isinstance(g.get("correlation"), Real)
                and isfinite(g["correlation"])
            ]
            if measured:
                low = min(measured, key=lambda g: g["correlation"])
                high = max(measured, key=lambda g: g["correlation"])
                detail = (
                    f"Se evaluaron {len(measured)} grupos por {values.get('group_by')} "
                    f"para {names}. Las correlaciones van de {_number(low['correlation'])} "
                    f"({low.get('group')}, n={low.get('sample_size')}) a "
                    f"{_number(high['correlation'])} ({high.get('group')}, "
                    f"n={high.get('sample_size')}). Los grupos con pocas observaciones "
                    "requieren cautela; estas diferencias no demuestran espuriedad."
                )
        elif result.method == "additive_identity" and len(result.variables) == 3:
            confirmed = values.get("identity_confirmed")
            detail = (
                f"La suma propuesta {result.variables[0]} + {result.variables[1]} = "
                f"{result.variables[2]} "
                + ("se verificó" if confirmed is True else "no se verificó en todas las filas")
                + f" en {values.get('matched_rows')} de {values.get('complete_rows')} "
                + "observaciones, "
                + f"con tolerancia absoluta {values.get('absolute_tolerance')}. "
                + "Una relación aritmética observada no es un hallazgo causal independiente."
            )
        elif result.method == "chi_square" and "chi_square" in values:
            detail = (
                f"La prueba de chi-cuadrado entre {names} "
                f"obtuvo un estadístico de {_number(values['chi_square'])}."
            )

        elif result.method == "cramers_v" and "cramers_v" in values:
            detail = f"La V de Cramér entre {names} fue de {_number(values['cramers_v'])}."

        elif result.method == "anova_one_way" and "f_statistic" in values:
            detail = (
                f"El ANOVA de una vía para {names} "
                f"obtuvo un estadístico F de {_number(values['f_statistic'])}."
            )

    if not detail:
        serialized = json.dumps(values, ensure_ascii=False, sort_keys=True)
        detail = f"Resultado de {result.method} para {names}: {serialized}."

    if result.sample_size is not None:
        detail += f" Muestra utilizada: {result.sample_size} observaciones."

    if result.effect_size is not None and result.method not in {
        "pearson",
        "spearman",
        "partial_correlation",
        "correlation_without_outliers",
        "cramers_v",
    }:
        detail += f" Tamaño del efecto reportado: {_number(result.effect_size)}."

    if result.p_value is not None:
        detail += (
            " Valor p < 0.001."
            if result.p_value < 0.001
            else f" Valor p: {_number(result.p_value)}."
        )

    return detail
