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
