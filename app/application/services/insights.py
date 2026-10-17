import json

from app.domain.enums.statuses import AnalysisStatus
from app.domain.models.analysis import AnalysisResult
from app.domain.models.data_dictionary import DataDictionary
from app.domain.models.evidence import Evidence, RelationshipAssessment
from app.domain.models.insight import Insight


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
                detail = f"{labels[result.method]} entre {names} fue de {coefficient}."

                if result.method == "partial_correlation":
                    control = result.metadata.get("control_variable")
                    if control is not None:
                        detail += f" Variable de control: {control}."

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
                f"obtuvo un estadístico de {values['chi_square']}."
            )

        elif result.method == "cramers_v" and "cramers_v" in values:
            detail = f"La V de Cramér entre {names} fue de {values['cramers_v']}."

        elif result.method == "anova_one_way" and "f_statistic" in values:
            detail = (
                f"El ANOVA de una vía para {names} "
                f"obtuvo un estadístico F de {values['f_statistic']}."
            )

    if not detail:
        serialized = json.dumps(values, ensure_ascii=False, sort_keys=True)
        detail = f"Resultado de {result.method} para {names}: {serialized}."

    if result.sample_size is not None:
        detail += f" Muestra utilizada: {result.sample_size} observaciones."

    if result.effect_size is not None:
        detail += f" Tamaño del efecto reportado: {result.effect_size}."

    if result.p_value is not None:
        detail += f" Valor p reportado: {result.p_value}."

    return detail


def generate_insights(
    results: list[AnalysisResult],
    evidence: list[Evidence],
    assessments: list[RelationshipAssessment],
    dictionary: DataDictionary | None = None,
) -> tuple[list[Insight], list[str]]:
    """Explain supplied evidence without calculating statistics or judging confounding."""
    successful = {r.analysis_id: r for r in results if r.status == AnalysisStatus.SUCCESS}
    if len({r.analysis_id for r in results}) != len(results):
        raise ValueError("Duplicate analysis IDs")
    if len({e.evidence_id for e in evidence}) != len(evidence):
        raise ValueError("Duplicate evidence IDs")
    evidence_map = {e.evidence_id: e for e in evidence}
    warnings: list[str] = []
    insights: list[Insight] = []
    if not assessments:
        return [], ["No relationship assessments supplied; insight generation skipped."]
    for index, assessment in enumerate(assessments):
        if not assessment.variables or not assessment.evidence_ids:
            warnings.append(f"Assessment {index}: variables or evidence missing.")
            continue
        linked = [evidence_map.get(eid) for eid in assessment.evidence_ids]
        if any(e is None or e.analysis_id not in successful for e in linked):
            warnings.append(f"Assessment {index}: unknown or unsuccessful evidence reference.")
            continue
        relevant = [successful[e.analysis_id] for e in linked if e is not None]
        if any(not set(assessment.variables).issubset(result.variables) for result in relevant):
            warnings.append(f"Assessment {index}: evidence refers to different variables.")
            continue
        if any(
            result.result is None and result.p_value is None and result.effect_size is None
            for result in relevant
        ):
            warnings.append(f"Assessment {index}: calculated values missing.")
            continue
        names = " y ".join(assessment.variables)
        if assessment.potentially_spurious is True:
            interpretation = (
                f"La relación entre {names} fue marcada por el módulo crítico como "
                "potencialmente espuria. Esta clasificación no demuestra causalidad."
            )
        elif assessment.potentially_spurious is False:
            interpretation = (
                f"El módulo crítico no marcó la relación entre {names} como potencialmente "
                "espuria en las comprobaciones realizadas. Esto no demuestra causalidad."
            )
        else:
            interpretation = (
                f"La evaluación de la relación entre {names} es indeterminada; "
                "no existe una clasificación concluyente."
            )
        measurements = [describe_result(result) for result in relevant]
        rationale = (
            f" Justificación del módulo crítico: {assessment.rationale}"
            if assessment.rationale
            else ""
        )
        limitations = list(assessment.limitations)
        for item in linked:
            if item is not None:
                limitations.extend(item.limitations)
        for result in relevant:
            limitations.extend(result.warnings)
        if dictionary is not None:
            for entry in dictionary.entries:
                if entry.column_name in assessment.variables and entry.source == "inferred":
                    limitations.append(f"El significado de {entry.column_name} es inferido.")
        limitations.append("Los resultados describen asociaciones y no prueban causalidad.")
        insights.append(
            Insight(
                insight_id=f"insight_{index + 1}",
                statement=interpretation
                + " Evidencia calculada: "
                + " ".join(measurements)
                + rationale,
                evidence_ids=list(dict.fromkeys(assessment.evidence_ids)),
                limitations=list(dict.fromkeys(limitations)),
            )
        )
    return insights, warnings
