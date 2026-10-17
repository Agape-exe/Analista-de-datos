import { Card } from "../../components/ui/card";
import { formatNumber, formatPercentage } from "../../lib/utils";
import type { IntakeResponse } from "../../types/intake";

export function DatasetMetrics({ result }: { result: IntakeResponse }) {
  const { summary, completeness } = result;
  const metrics = [
    { label: "Filas", value: formatNumber(summary.rows), note: "Registros de datos validados" },
    { label: "Columnas", value: formatNumber(summary.columns), note: `${summary.temporal_columns.length} temporales · ${summary.identifiers.length} identificadores` },
    { label: "Variables numéricas", value: formatNumber(summary.numeric_columns.length), note: "Valores numéricos observados" },
    { label: "Variables categóricas", value: formatNumber(summary.categorical_columns.length), note: "Etiquetas y categorías discretas" },
    { label: "Valores faltantes", value: formatPercentage(completeness.missing_percentage), note: `${formatNumber(completeness.missing_cells)} de ${formatNumber(completeness.total_cells)} celdas` },
    { label: "Puntaje de calidad", value: "—", note: "No evaluado", unavailable: true },
  ];
  return <div className="metrics-grid">{metrics.map((metric) => <Card className="metric-card" key={metric.label}>
    <p>{metric.label}</p><strong className={metric.unavailable ? "muted" : ""}>{metric.value}</strong><small>{metric.note}</small>
  </Card>)}</div>;
}
