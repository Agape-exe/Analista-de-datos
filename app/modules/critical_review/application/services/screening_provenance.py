"""Conserva la procedencia de asociaciones calculadas por screening."""

from pydantic import Field, JsonValue, ValidationError

from app.shared.domain.enums.statuses import AnalysisStatus
from app.shared.domain.models.analysis import (
    AnalysisResult,
    RankedRelationship,
)
from app.shared.domain.models.base import DomainModel
from app.shared.domain.models.evidence import RelationshipAssessment


class ScreeningProvenance(DomainModel):
    """Información estadística original del screening."""

    analysis_id: str
    relationships: list[RankedRelationship] = Field(default_factory=list)
    correction: str | None = None
    significance_level: float | None = Field(default=None, ge=0, le=1)
    skipped_pairs: list[dict[str, str]] = Field(default_factory=list)
    excluded_columns: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    tests_performed: int | None = Field(default=None, ge=0)


def extract_screening_provenance(
    analysis: AnalysisResult,
) -> ScreeningProvenance | None:
    """Extrae resultados reales sin recalcular estadísticas."""

    if analysis.method != "relationship_ranking":
        return None

    if analysis.status != AnalysisStatus.SUCCESS:
        return None

    if not isinstance(analysis.result, dict):
        return None

    data = analysis.result

    relationships = data.get("top_relationships")

    if not isinstance(relationships, list):
        return None

    return ScreeningProvenance(
        analysis_id=analysis.analysis_id,
        relationships=[RankedRelationship.model_validate(item) for item in relationships],
        correction=data.get("correction"),
        significance_level=data.get("significance_level"),
        skipped_pairs=data.get("skipped_pairs", []),
        excluded_columns=data.get("excluded_columns", {}),
        warnings=list(analysis.warnings),
        tests_performed=analysis.metadata.get("tests_performed"),
    )


def extract_screening_summary(
    summary: dict[str, JsonValue],
) -> ScreeningProvenance | None:
    """Read the real Association channel without manufacturing an Analysis result."""
    analysis_id = summary.get("analysis_id")
    relationships = summary.get("top_relationships")
    if not isinstance(analysis_id, str) or not analysis_id or not isinstance(relationships, list):
        return None
    try:
        return ScreeningProvenance(
            analysis_id=analysis_id,
            relationships=relationships,
            correction=summary.get("correction"),
            significance_level=summary.get("significance_level"),
            skipped_pairs=summary.get("skipped_pairs", []),
            excluded_columns=summary.get("excluded_columns", {}),
            warnings=summary.get("warnings", []),
            tests_performed=summary.get("tests_performed"),
        )
    except ValidationError:
        # Historical summaries may lack the current shape; never invent provenance.
        return None


def attach_screening_provenance(
    results: list[AnalysisResult],
    assessments: list[RelationshipAssessment],
    *,
    screening_summary: dict[str, JsonValue] | None = None,
) -> None:
    """Añade procedencia del screening a evaluaciones existentes."""

    summaries = {}
    for analysis in results:
        if (provenance := extract_screening_provenance(analysis)) is not None:
            summaries[provenance.analysis_id] = provenance
    if screening_summary:
        if (provenance := extract_screening_summary(screening_summary)) is not None:
            summaries[provenance.analysis_id] = provenance

    for provenance in summaries.values():
        for relationship in provenance.relationships:
            assessment = next(
                (
                    item
                    for item in assessments
                    if len(item.variables) == 2
                    and set(item.variables) == {relationship.x, relationship.y}
                ),
                None,
            )

            if assessment is None:
                continue

            note = (
                f"Screening {provenance.analysis_id}: "
                f"método={relationship.method}; "
                f"n={relationship.sample_size}; "
                f"p crudo={relationship.p_value}; "
                f"p ajustado={relationship.adjusted_p_value}; "
                f"corrección={provenance.correction or 'no informada'}."
            )
            note += (
                " El ajuste corresponde a las pruebas del screening; "
                "los análisis posteriores son un retesteo independiente."
            )
            if provenance.tests_performed is not None:
                note += f" Pruebas en el ajuste: {provenance.tests_performed}."

            supporting = [
                f"{item.method} (valor={item.strength}, p={item.p_value})"
                for item in relationship.supporting
            ]

            if supporting:
                note += f" Resultados de apoyo: {'; '.join(supporting)}."

            if note not in assessment.limitations:
                assessment.limitations.append(note)

            for warning in [*relationship.warnings, *provenance.warnings]:
                detail = f"Screening {provenance.analysis_id}: {warning}"

                if detail not in assessment.limitations:
                    assessment.limitations.append(detail)
