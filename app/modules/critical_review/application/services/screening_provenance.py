"""Conserva la procedencia de asociaciones calculadas por screening."""

from pydantic import Field

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
    )


def attach_screening_provenance(
    results: list[AnalysisResult],
    assessments: list[RelationshipAssessment],
) -> None:
    """Añade procedencia del screening a evaluaciones existentes."""

    for analysis in results:
        provenance = extract_screening_provenance(analysis)

        if provenance is None:
            continue

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

            supporting = [
                f"{item.method} (r={item.strength}, p={item.p_value})"
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
