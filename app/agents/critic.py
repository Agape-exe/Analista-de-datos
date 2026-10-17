from uuid import uuid4

from app.agents.base import SkeletonAgent
from app.analytics.statistics.robustness import (
    calculate_correlation_disagreement,
    calculate_outlier_impact,
    calculate_subgroup_heterogeneity,
    calculate_temporal_variation,
    calculate_weakening,
    detect_sign_change,
    is_control_sensitive,
)
from app.application.dto.agent import AgentContext, AgentResult, AgentUpdate
from app.domain.enums.statuses import AnalysisStatus
from app.domain.models.analysis import AssociationResult
from app.domain.models.evidence import Evidence, RelationshipAssessment


class CriticAgent(SkeletonAgent):
    name = "Critic"

    # Umbrales provisionales de evaluación
    OUTLIER_IMPACT_THRESHOLD = 0.30
    SUBGROUP_HETEROGENEITY_THRESHOLD = 0.50
    TEMPORAL_VARIATION_THRESHOLD = 0.50

    # Resultados que se reportan como preliminares si no hay pruebas de robustez
    PRELIMINARY_ALPHA = 0.05
    PRELIMINARY_METHODS = frozenset(
        {"pearson", "spearman", "chi_square", "cramers_v", "anova_one_way"}
    )

    # PASO 70: Evitar alertas por cambios de signo cercanos a cero
    MIN_SIGN_CHANGE_MAGNITUDE = 0.30

    async def run(self, context: AgentContext) -> AgentResult:
        new_evidence = []
        new_assessments = []
        associations = list(context.associations)

        for analysis in context.analysis_results:
            if analysis.status != AnalysisStatus.SUCCESS:
                continue
            if analysis.method not in ("pearson", "spearman"):
                continue
            if len(analysis.variables) != 2 or analysis.effect_size is None:
                continue

            already_present = any(
                item.method == analysis.method and set(item.variables) == set(analysis.variables)
                for item in associations
            )
            if already_present:
                continue

            associations.append(
                AssociationResult(
                    method=analysis.method,
                    variables=list(analysis.variables),
                    strength=analysis.effect_size,
                    p_value=analysis.p_value,
                )
            )

        # 1. Revisar las correlaciones originales
        for association in associations:
            if association.method not in ("pearson", "pearson_correlation"):
                continue

            if len(association.variables) != 2 or association.strength is None:
                continue

            original = association.strength
            evidence_ids = []

            suspicious = False
            outlier_sensitive = False
            subgroup_sensitive = False
            temporal_sensitive = False

            # 2. Buscar Spearman para las mismas variables
            spearman_note = ""

            for other in associations:
                if other.method not in ("spearman", "spearman_correlation"):
                    continue

                if len(other.variables) != 2 or other.strength is None:
                    continue

                if set(other.variables) != set(association.variables):
                    continue

                try:
                    disagreement = calculate_correlation_disagreement(
                        original,
                        other.strength,
                    )
                except ValueError:
                    continue

                spearman_note = (
                    f"Spearman: {other.strength:.3f}. "
                    f"Diferencia Pearson-Spearman: {disagreement:.3f}. "
                )
                break

            # 3. Evaluar correlaciones parciales
            for analysis in context.analysis_results:
                if analysis.status != AnalysisStatus.SUCCESS:
                    continue

                if analysis.method != "partial_correlation":
                    continue

                if analysis.effect_size is None:
                    continue

                if len(analysis.variables) < 2:
                    continue

                if set(analysis.variables[:2]) != set(association.variables):
                    continue

                # Verificar las variables de control
                control_variables = analysis.metadata.get("control_variables")

                if control_variables is None:
                    control_variable = analysis.metadata.get("control_variable")

                    if isinstance(control_variable, str):
                        control_variables = [control_variable]

                if not isinstance(control_variables, list) or not control_variables:
                    continue

                if not all(
                    isinstance(variable, str) and variable.strip() for variable in control_variables
                ):
                    continue

                if set(control_variables) & set(association.variables):
                    continue

                adjusted = analysis.effect_size

                # 4. Aplicar funciones de robustez
                try:
                    weakening = calculate_weakening(original, adjusted)

                    sign_change = detect_sign_change(
                        original,
                        adjusted,
                    )

                    control_sensitive = is_control_sensitive(
                        original,
                        adjusted,
                    )

                except ValueError:
                    continue

                # 5. PASO 70: Evaluar la importancia del cambio de signo
                meaningful_sign_change = (
                    sign_change
                    and min(abs(original), abs(adjusted)) >= self.MIN_SIGN_CHANGE_MAGNITUDE
                )

                # Activar alerta solo si existe evidencia relevante
                suspicious = suspicious or control_sensitive or meaningful_sign_change

                # 6. Registrar evidencia de correlación parcial
                evidence = Evidence(
                    evidence_id=str(uuid4()),
                    analysis_id=analysis.analysis_id,
                    description=(
                        f"Correlación original: {original:.3f}. "
                        f"{spearman_note}"
                        f"Correlación parcial: {adjusted:.3f}. "
                        f"Variables de control: {', '.join(control_variables)}. "
                        f"Debilitamiento: {weakening:.2%}. "
                        f"Cambio de signo: {sign_change}. "
                        f"Cambio de signo relevante: "
                        f"{meaningful_sign_change}."
                    ),
                    limitations=[
                        "La asociación estadística no demuestra causalidad.",
                        "Los cambios de signo requieren revisión adicional.",
                        "Los umbrales utilizados son provisionales.",
                    ],
                )

                new_evidence.append(evidence)
                evidence_ids.append(evidence.evidence_id)

            # 7. Evaluar el impacto de los outliers
            for analysis in context.analysis_results:
                if analysis.status != AnalysisStatus.SUCCESS:
                    continue

                if analysis.method != "correlation_without_outliers":
                    continue

                if analysis.effect_size is None:
                    continue

                if len(analysis.variables) != 2:
                    continue

                if set(analysis.variables) != set(association.variables):
                    continue

                outlier_method = analysis.metadata.get("outlier_method")
                removed_count = analysis.metadata.get("removed_count")

                if not isinstance(outlier_method, str) or not outlier_method.strip():
                    continue

                if type(removed_count) is not int or removed_count < 1:
                    continue

                try:
                    impact = calculate_outlier_impact(
                        original,
                        analysis.effect_size,
                    )
                except ValueError:
                    continue

                significant_impact = impact >= self.OUTLIER_IMPACT_THRESHOLD

                outlier_sensitive = outlier_sensitive or significant_impact

                # Registrar evidencia de outliers
                evidence = Evidence(
                    evidence_id=str(uuid4()),
                    analysis_id=analysis.analysis_id,
                    description=(
                        f"Correlación original: {original:.3f}. "
                        f"Correlación sin outliers: "
                        f"{analysis.effect_size:.3f}. "
                        f"Impacto absoluto: {impact:.3f}. "
                        f"Método de detección: {outlier_method}. "
                        f"Observaciones eliminadas: {removed_count}. "
                        f"Impacto elevado: {significant_impact}."
                    ),
                    limitations=[
                        "La exclusión de outliers puede eliminar datos legítimos.",
                        "El impacto observado no demuestra espuriedad.",
                    ],
                )

                new_evidence.append(evidence)
                evidence_ids.append(evidence.evidence_id)

            # 8. Evaluar diferencias entre subgrupos
            for analysis in context.analysis_results:
                if analysis.status != AnalysisStatus.SUCCESS:
                    continue

                if analysis.method != "analyze_subgroups":
                    continue

                if len(analysis.variables) != 2:
                    continue

                if set(analysis.variables) != set(association.variables):
                    continue

                data = analysis.result

                if not isinstance(data, dict):
                    continue

                group_by = data.get("group_by")
                groups = data.get("groups")

                if not isinstance(group_by, str) or not group_by.strip():
                    continue

                if group_by in association.variables:
                    continue

                if not isinstance(groups, list) or len(groups) < 2:
                    continue

                correlations = []
                group_descriptions = []
                group_names = set()
                valid_groups = True

                # Validar cada subgrupo
                for group in groups:
                    if not isinstance(group, dict):
                        valid_groups = False
                        break

                    name = group.get("group")
                    correlation = group.get("correlation")
                    sample_size = group.get("sample_size")

                    if not isinstance(name, str) or not name.strip():
                        valid_groups = False
                        break

                    if name in group_names:
                        valid_groups = False
                        break

                    if type(correlation) not in (int, float):
                        valid_groups = False
                        break

                    if type(sample_size) is not int or sample_size < 3:
                        valid_groups = False
                        break

                    group_names.add(name)
                    correlations.append(correlation)

                    group_descriptions.append(f"{name}: r={correlation:.3f}, n={sample_size}")

                if not valid_groups:
                    continue

                # 9. Calcular la heterogeneidad
                try:
                    heterogeneity = calculate_subgroup_heterogeneity(correlations)
                except ValueError:
                    continue

                significant_heterogeneity = heterogeneity >= self.SUBGROUP_HETEROGENEITY_THRESHOLD

                subgroup_sensitive = subgroup_sensitive or significant_heterogeneity

                # Registrar evidencia por subgrupos
                evidence = Evidence(
                    evidence_id=str(uuid4()),
                    analysis_id=analysis.analysis_id,
                    description=(
                        f"Variable de agrupación: {group_by}. "
                        f"Resultados: {'; '.join(group_descriptions)}. "
                        f"Heterogeneidad: {heterogeneity:.3f}. "
                        f"Alerta de heterogeneidad: "
                        f"{significant_heterogeneity}."
                    ),
                    limitations=[
                        "Las diferencias entre subgrupos son descriptivas.",
                        "No se han calculado intervalos de confianza.",
                        "Los tamaños de muestra pueden afectar "
                        "la estabilidad de las correlaciones.",
                        "La heterogeneidad no demuestra espuriedad.",
                    ],
                )

                new_evidence.append(evidence)
                evidence_ids.append(evidence.evidence_id)

            # 10. Evaluar cambios temporales
            for analysis in context.analysis_results:
                if analysis.status != AnalysisStatus.SUCCESS:
                    continue

                if analysis.method != "analyze_temporal":
                    continue

                if len(analysis.variables) != 2:
                    continue

                if set(analysis.variables) != set(association.variables):
                    continue

                data = analysis.result

                if not isinstance(data, dict):
                    continue

                time_column = data.get("time_column")
                periods = data.get("periods")

                if not isinstance(time_column, str) or not time_column.strip():
                    continue

                if not isinstance(periods, list) or len(periods) < 2:
                    continue

                correlations = []
                period_descriptions = []
                period_names = set()
                valid_periods = True

                # El contrato exige periodos en orden cronológico
                for period in periods:
                    if not isinstance(period, dict):
                        valid_periods = False
                        break

                    name = period.get("period")
                    correlation = period.get("correlation")
                    sample_size = period.get("sample_size")

                    if not isinstance(name, str) or not name.strip():
                        valid_periods = False
                        break

                    if name in period_names:
                        valid_periods = False
                        break

                    if type(correlation) not in (int, float):
                        valid_periods = False
                        break

                    if type(sample_size) is not int or sample_size < 3:
                        valid_periods = False
                        break

                    period_names.add(name)
                    correlations.append(correlation)

                    period_descriptions.append(f"{name}: r={correlation:.3f}, n={sample_size}")

                if not valid_periods:
                    continue

                # 11. Calcular la mayor variación temporal
                try:
                    variation = calculate_temporal_variation(correlations)
                except ValueError:
                    continue

                significant_variation = variation >= self.TEMPORAL_VARIATION_THRESHOLD

                temporal_sensitive = temporal_sensitive or significant_variation

                # Registrar evidencia temporal
                evidence = Evidence(
                    evidence_id=str(uuid4()),
                    analysis_id=analysis.analysis_id,
                    description=(
                        f"Variable temporal: {time_column}. "
                        f"Periodos: {'; '.join(period_descriptions)}. "
                        f"Variación temporal máxima: {variation:.3f}. "
                        f"Alerta temporal: {significant_variation}."
                    ),
                    limitations=[
                        "Se presupone que los periodos están ordenados cronológicamente.",
                        "No se ha verificado la autocorrelación temporal.",
                        "No se han calculado intervalos de confianza.",
                        "La variación temporal no demuestra espuriedad.",
                    ],
                )

                new_evidence.append(evidence)
                evidence_ids.append(evidence.evidence_id)

            # 12. No generar evaluaciones sin evidencia
            if not evidence_ids:
                continue

            # 13. Construir las razones de la evaluación
            reasons = []

            if suspicious:
                reasons.append(
                    "Se detectó debilitamiento importante o cambio "
                    "de signo relevante después de aplicar "
                    "variables de control."
                )

            if outlier_sensitive:
                reasons.append(
                    "La asociación presenta sensibilidad elevada "
                    "a la exclusión de valores atípicos."
                )

            if subgroup_sensitive:
                reasons.append(
                    "Se detectó heterogeneidad elevada entre subgrupos. "
                    "La relación requiere revisión adicional."
                )

            if temporal_sensitive:
                reasons.append(
                    "Se detectó inestabilidad temporal elevada. "
                    "La asociación cambia entre periodos consecutivos."
                )

            if not reasons:
                reasons.append(
                    "No se activaron alertas en las pruebas disponibles. "
                    "Se necesitan más análisis para concluir."
                )

            # 14. Construir la evaluación final
            assessment = RelationshipAssessment(
                variables=association.variables,
                evidence_ids=evidence_ids,
                potentially_spurious=True if suspicious else None,
                rationale=" ".join(reasons),
                limitations=[
                    "Evaluación preliminar basada en pruebas disponibles.",
                    "Los umbrales utilizados requieren validación.",
                    "La sensibilidad a outliers, subgrupos y periodos "
                    "no demuestra por sí sola una relación espuria.",
                    "La asociación estadística no demuestra causalidad.",
                ],
            )

            new_assessments.append(assessment)

        # 15. Hallazgos preliminares: asociaciones significativas sin pruebas de robustez
        assessed = {frozenset(item.variables) for item in new_assessments}
        preliminary: dict[frozenset[str], list[Evidence]] = {}
        for analysis in context.analysis_results:
            pair = frozenset(analysis.variables)
            if (
                analysis.status != AnalysisStatus.SUCCESS
                or analysis.method not in self.PRELIMINARY_METHODS
                or len(pair) != 2
                or pair in assessed
                or analysis.p_value is None
                or analysis.p_value > self.PRELIMINARY_ALPHA
            ):
                continue
            preliminary.setdefault(pair, []).append(
                Evidence(
                    evidence_id=str(uuid4()),
                    analysis_id=analysis.analysis_id,
                    description=(
                        f"Resultado de {analysis.method} con valor p "
                        f"{analysis.p_value:.4g}, sin pruebas de robustez disponibles."
                    ),
                    limitations=[
                        "La asociación estadística no demuestra causalidad.",
                        "No se evaluaron variables de control, outliers, subgrupos "
                        "ni estabilidad temporal.",
                    ],
                )
            )
        for analysis in context.analysis_results:
            evidences = preliminary.pop(frozenset(analysis.variables), None)
            if evidences is None:
                continue
            new_evidence.extend(evidences)
            new_assessments.append(
                RelationshipAssessment(
                    variables=list(analysis.variables),
                    evidence_ids=[item.evidence_id for item in evidences],
                    potentially_spurious=None,
                    rationale=(
                        "Hallazgo preliminar: la asociación es estadísticamente "
                        f"significativa (p <= {self.PRELIMINARY_ALPHA}), pero no se "
                        "ejecutaron pruebas de robustez, como el control por otra variable."
                    ),
                    limitations=[
                        "Evaluación preliminar sin pruebas de robustez.",
                        "La asociación estadística no demuestra causalidad.",
                    ],
                )
            )

        # 16. Omitir si no existe evidencia evaluable
        if not new_assessments:
            return AgentResult(
                agent_name=self.name,
                status=AnalysisStatus.SKIPPED,
                warnings=["Critic: no hay resultados estadísticos válidos para evaluar."],
            )

        # 17. Devolver evidencias y evaluaciones
        return AgentResult(
            agent_name=self.name,
            status=AnalysisStatus.SUCCESS,
            update=AgentUpdate(
                evidence=[*context.evidence, *new_evidence],
                relationship_assessments=[
                    *context.relationship_assessments,
                    *new_assessments,
                ],
            ),
        )
