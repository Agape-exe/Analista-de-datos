from app.shared.application.result_descriptions import describe_result
from app.shared.domain.enums.statuses import AnalysisStatus
from app.shared.domain.models.analysis import AnalysisResult
from app.shared.domain.models.data_dictionary import DataDictionary
from app.shared.domain.models.evidence import Evidence, RelationshipAssessment
from app.shared.domain.models.insight import Insight


def _limitations(items: list[str]) -> list[str]:
    translations = {
        (
            "ANOVA assumes independent observations, approximately normal residuals, "
            "and similar variances."
        ): (
            "ANOVA presupone observaciones independientes, "
            "residuos aproximadamente normales y varianzas similares."
        ),
        (
            "Subgroup correlations are descriptive; small or constant groups are explicitly "
            "excluded, and no confidence intervals are calculated."
        ): (
            "Los subgrupos son descriptivos; se excluyen grupos insuficientes o constantes "
            "y no se calculan intervalos de confianza."
        ),
        (
            "Only the proposed sum is tested on complete observations; an arithmetic "
            "relationship is not independent causal evidence."
        ): ("Solo se comprueba la suma propuesta sobre observaciones completas."),
    }
    cleaned = []
    causal = "Los resultados describen asociaciones y no prueban causalidad."
    for item in items:
        text = translations.get(item, item)
        lower = text.casefold()
        if "causal" in lower or "causation" in lower:
            text = causal
        elif "no se han calculado intervalos de confianza" in lower:
            text = "No se han calculado intervalos de confianza."
        if text not in cleaned:
            cleaned.append(text)
    return cleaned


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
        if any(result.method == "additive_identity" for result in relevant):
            interpretation = "Comprobación de consistencia aritmética."
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
                limitations=_limitations(limitations),
            )
        )
    return insights, warnings
