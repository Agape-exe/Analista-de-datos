"""Traceable descriptive reviews for measured results, with explicit uncertainty."""

from collections import defaultdict
from math import isfinite
from numbers import Real
from uuid import uuid4

from app.shared.application.result_descriptions import describe_result
from app.shared.domain.models.analysis import AnalysisResult
from app.shared.domain.models.evidence import Evidence, RelationshipAssessment


def _finite(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and isfinite(value)


def _eligible(result: AnalysisResult) -> bool:
    if result.status != "SUCCESS" or len(set(result.variables)) != len(result.variables):
        return False
    if len(result.variables) < 2:
        return False
    values = result.result if isinstance(result.result, dict) else {}
    if result.method in {"pearson", "spearman"}:
        coefficient = result.effect_size
        if coefficient is None:
            coefficient = values.get("correlation", values.get("coefficient"))
        return _finite(coefficient) and abs(coefficient) <= 1
    if result.method in {"chi_square", "anova_one_way", "cramers_v"}:
        key = {
            "chi_square": "chi_square",
            "anova_one_way": "f_statistic",
            "cramers_v": "cramers_v",
        }[result.method]
        value = values.get(key)
        return _finite(value) and value >= 0 and (key != "cramers_v" or value <= 1)
    if result.method == "additive_identity":
        count, matched = values.get("complete_rows"), values.get("matched_rows")
        tolerance, residual = values.get("absolute_tolerance"), values.get("max_absolute_residual")
        confirmed = values.get("identity_confirmed")
        return (
            len(result.variables) == 3
            and type(count) is int
            and count > 0
            and type(matched) is int
            and 0 <= matched <= count
            and type(confirmed) is bool
            and confirmed == (matched == count)
            and _finite(tolerance)
            and tolerance > 0
            and _finite(residual)
            and residual >= 0
            and (not confirmed or residual <= tolerance)
        )
    return False


def review_measured_results(
    results: list[AnalysisResult],
    evidence: list[Evidence],
    assessments: list[RelationshipAssessment],
) -> None:
    """Extend reviews using genuine result IDs; never infer a negative spurious label."""
    groups = defaultdict(list)
    for result in results:
        if _eligible(result):
            groups[frozenset(result.variables)].append(result)
    for variables, measured in groups.items():
        assessment = next((item for item in assessments if set(item.variables) == variables), None)
        has_robustness = assessment is not None
        if assessment is None:
            identity = next((item for item in measured if item.method == "additive_identity"), None)
            rationale = (
                "Se contrastó una identidad aritmética sobre las observaciones completas. "
                "Una suma observada no constituye un hallazgo causal independiente."
                if identity is not None
                else "Se revisaron resultados estadísticos calculados. La robustez y la espuriedad "
                "permanecen indeterminadas con las comprobaciones disponibles."
            )
            assessment = RelationshipAssessment(
                variables=list(measured[0].variables),
                potentially_spurious=None,
                rationale=rationale,
                limitations=[
                    "Evaluación descriptiva; no se ha establecido causalidad.",
                    "La significación estadística por sí sola no demuestra robustez ni espuriedad.",
                ],
            )
            if identity is None:
                assessment.limitations.append(
                    "No hay comprobaciones de robustez adicionales evaluables para esta relación."
                )
            assessments.append(assessment)
        linked = {
            item.analysis_id for item in evidence if item.evidence_id in assessment.evidence_ids
        }
        by_method = {item.method: item for item in measured}
        comparison = ""
        if "pearson" in by_method and "spearman" in by_method:

            def coefficient(item):
                return (
                    item.effect_size
                    if item.effect_size is not None
                    else item.result.get("correlation", item.result.get("coefficient"))
                )

            difference = abs(coefficient(by_method["pearson"]) - coefficient(by_method["spearman"]))
            comparison = f" Diferencia absoluta Pearson-Spearman: {difference:.6g}."
            comparison += (
                " Requiere revisar discrepancias entre asociación lineal y monotónica."
                if difference >= 0.2
                else " La concordancia no demuestra causalidad ni descarta confusión."
            )
        for result in measured:
            if result.analysis_id in linked:
                continue
            description = describe_result(result)
            if result.method == "spearman":
                description += comparison
            item = Evidence(
                evidence_id=str(uuid4()),
                analysis_id=result.analysis_id,
                description=description,
                limitations=list(result.warnings)
                + ["Evidencia de resultados observados; no demuestra causalidad."],
            )
            evidence.append(item)
            assessment.evidence_ids.append(item.evidence_id)
        if has_robustness and comparison:
            assessment.rationale = (assessment.rationale or "") + comparison
