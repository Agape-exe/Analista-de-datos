"""AUD-039: Consultas determinísticas sobre reportes existentes."""

from typing import Literal

from pydantic import Field

from app.shared.domain.models.base import DomainModel
from app.shared.domain.models.report import AnalysisReport

QUESTIONS = {
    "perfil": "¿Cuál es el perfil del dataset?",
    "analisis": "¿Qué análisis estadísticos se ejecutaron?",
    "relaciones": "¿Cómo se clasificaron las relaciones?",
    "evidencias": "¿Qué evidencias respaldan el reporte?",
    "metricas": "¿Qué métricas se midieron?",
    "advertencias": "¿Qué advertencias registró el reporte?",
}


class GroundedQueryRequest(DomainModel):
    question: str = Field(min_length=1)


class GroundedReference(DomainModel):
    path: str
    analysis_id: str | None = None
    evidence_id: str | None = None


class GroundedAnswer(DomainModel):
    question: str
    status: Literal["ANSWERED", "ABSTAINED"]
    answer: str
    references: list[GroundedReference] = Field(default_factory=list)


def _abstain(question: str, reason: str) -> GroundedAnswer:
    return GroundedAnswer(
        question=question,
        status="ABSTAINED",
        answer=reason,
    )


def answer_grounded_query(
    report: AnalysisReport,
    question: str,
) -> GroundedAnswer:
    """Responder exclusivamente con información registrada en el reporte."""

    if question not in QUESTIONS:
        return _abstain(
            question,
            "Pregunta no soportada. Consulta el catálogo de preguntas disponibles.",
        )

    if question == "perfil":
        profile = report.dataset_profile
        if profile is None:
            return _abstain(question, "El reporte no contiene un perfil de dataset.")

        names = [column.column_name for column in profile.columns]
        return GroundedAnswer(
            question=question,
            status="ANSWERED",
            answer=(
                f"Dataset con {profile.row_count} filas y "
                f"{len(names)} columnas. "
                f"Columnas: {', '.join(names) if names else 'ninguna'}."
            ),
            references=[
                GroundedReference(path="/dataset_profile/row_count"),
                GroundedReference(path="/dataset_profile/columns"),
            ],
        )

    if question == "analisis":
        completed = [
            (index, result)
            for index, result in enumerate(report.analysis_results)
            if result.status == "SUCCESS"
        ]
        if not completed:
            return _abstain(
                question,
                "No existen análisis estadísticos exitosos registrados.",
            )

        descriptions = [
            f"{result.method} ({', '.join(result.variables)})" for _, result in completed[:10]
        ]
        return GroundedAnswer(
            question=question,
            status="ANSWERED",
            answer=(
                f"Análisis exitosos registrados: {len(completed)}. "
                f"Primeros resultados: {'; '.join(descriptions)}."
            ),
            references=[
                GroundedReference(path="/analysis_results"),
                *[
                    GroundedReference(
                        path=f"/analysis_results/{index}",
                        analysis_id=result.analysis_id,
                    )
                    for index, result in completed[:10]
                ],
            ],
        )

    if question == "relaciones":
        if not report.relationship_assessments:
            return _abstain(
                question,
                "No existen evaluaciones de relaciones en el reporte.",
            )

        descriptions = []
        references = []

        for index, assessment in enumerate(report.relationship_assessments[:10]):
            label = (
                "potencialmente espuria"
                if assessment.potentially_spurious is True
                else "no marcada como espuria"
                if assessment.potentially_spurious is False
                else "indeterminada"
            )
            pair = " y ".join(assessment.variables)
            descriptions.append(f"{pair}: {label}")
            references.append(GroundedReference(path=f"/relationship_assessments/{index}"))

        return GroundedAnswer(
            question=question,
            status="ANSWERED",
            answer=(
                "Clasificaciones registradas: "
                + "; ".join(descriptions)
                + ". Estas clasificaciones no prueban causalidad."
            ),
            references=references,
        )

    if question == "evidencias":
        successful_ids = {
            result.analysis_id for result in report.analysis_results if result.status == "SUCCESS"
        }
        valid = [
            (index, item)
            for index, item in enumerate(report.evidence)
            if item.analysis_id in successful_ids
        ]

        if not valid:
            return _abstain(
                question,
                "No hay evidencias vinculadas a cálculos exitosos.",
            )

        return GroundedAnswer(
            question=question,
            status="ANSWERED",
            answer="Evidencias registradas: "
            + "; ".join(item.description for _, item in valid[:10]),
            references=[
                GroundedReference(
                    path=f"/evidence/{index}",
                    evidence_id=item.evidence_id,
                    analysis_id=item.analysis_id,
                )
                for index, item in valid[:10]
            ],
        )

    if question == "metricas":
        measured = report.metrics.model_dump(exclude_none=True)

        if not measured:
            return _abstain(
                question,
                "No existen métricas medidas en este reporte.",
            )

        return GroundedAnswer(
            question=question,
            status="ANSWERED",
            answer="Métricas registradas: "
            + "; ".join(f"{name}={value}" for name, value in measured.items()),
            references=[GroundedReference(path=f"/metrics/{name}") for name in measured],
        )

    if not report.warnings:
        return _abstain(
            question,
            "No hay advertencias registradas para consultar.",
        )

    return GroundedAnswer(
        question=question,
        status="ANSWERED",
        answer="Advertencias: " + "; ".join(report.warnings),
        references=[
            GroundedReference(path=f"/warnings/{index}") for index in range(len(report.warnings))
        ],
    )
