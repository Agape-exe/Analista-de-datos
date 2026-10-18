import json
import re

from app.shared.domain.models.report import AnalysisReport


def plain(value: str) -> str:
    text = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = text.replace("\n", " ").replace("\r", " ")
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", text)


class MarkdownReportRenderer:
    def render(self, report: AnalysisReport) -> str:
        lines = [
            "# Informe de análisis",
            f"Ejecución: {plain(report.run_id)}",
            f"Estado: {report.status}",
        ]
        if report.dataset_profile:
            lines.extend(
                [
                    "## Dataset",
                    f"Filas: {report.dataset_profile.row_count}",
                    f"Columnas: {report.dataset_profile.column_count}",
                ]
            )
        lines.extend(
            [
                "## Contexto y plan",
                plain(report.user_question or "Sin pregunta registrada"),
                "Dataset: " + plain(report.dataset_id or "Sin identificador registrado"),
                "Política: "
                + plain(
                    report.analysis_plan.policy_version
                    if report.analysis_plan
                    else "Sin plan registrado"
                ),
            ]
        )
        if report.audit_version is None:
            lines.append(
                "Reporte histórico sin snapshot de auditoría ni instrumentación garantizada."
            )
        for step in report.analysis_plan.steps if report.analysis_plan else []:
            lines.append(
                plain(
                    f"{step.step_id}: {step.request.method} ({', '.join(step.request.variables)})"
                )
            )
        lines.extend(
            [
                "## Configuración efectiva",
                "```json",
                json.dumps(report.configuration, ensure_ascii=False, indent=2),
                "```",
            ]
        )
        lines.append("## Traza")
        for event in report.execution_trace:
            lines.append(plain(json.dumps(event, ensure_ascii=False)))
        lines.append("## Insights")
        if not report.insights:
            lines.append("No se generaron insights respaldados por evidencia.")
        for insight in report.insights:
            lines.extend(
                [plain(insight.statement), "Evidencias: " + ", ".join(insight.evidence_ids)]
            )
            lines.extend("- " + plain(value) for value in insight.limitations)
        lines.append("## Evidencia calculada")
        for result in report.analysis_results:
            lines.append(
                plain(
                    f"{result.analysis_id} | {result.method} | {result.status} | "
                    f"{json.dumps(result.result, ensure_ascii=False)}"
                )
            )
        lines.append("## Advertencias y errores")
        lines.extend("- " + plain(value) for value in report.warnings + report.errors)
        lines.extend(["## Métricas", "```json", report.metrics.model_dump_json(indent=2), "```"])
        return "\n\n".join(lines) + "\n"
