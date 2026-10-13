import { Card } from "../../components/ui/card";
import { formatNumber, formatPercentage } from "../../lib/utils";
import type { IntakeResponse } from "../../types/intake";

export function DatasetMetrics({ result }: { result: IntakeResponse }) {
  const { summary, completeness } = result;
  const metrics = [
    { label: "Rows", value: formatNumber(summary.rows), note: "Validated data records" },
    { label: "Columns", value: formatNumber(summary.columns), note: `${summary.temporal_columns.length} temporal · ${summary.identifiers.length} identifiers` },
    { label: "Numerical variables", value: formatNumber(summary.numeric_columns.length), note: "Observed numeric values" },
    { label: "Categorical variables", value: formatNumber(summary.categorical_columns.length), note: "Labels and discrete categories" },
    { label: "Missing values", value: formatPercentage(completeness.missing_percentage), note: `${formatNumber(completeness.missing_cells)} of ${formatNumber(completeness.total_cells)} cells` },
    { label: "Data quality score", value: "—", note: "Not evaluated", unavailable: true },
  ];
  return <div className="metrics-grid">{metrics.map((metric) => <Card className="metric-card" key={metric.label}>
    <p>{metric.label}</p><strong className={metric.unavailable ? "muted" : ""}>{metric.value}</strong><small>{metric.note}</small>
  </Card>)}</div>;
}
