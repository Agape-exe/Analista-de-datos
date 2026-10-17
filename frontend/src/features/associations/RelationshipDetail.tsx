import { Info, LoaderCircle, TriangleAlert } from "lucide-react";
import { BoxPlot } from "../../components/charts/BoxPlot";
import { formatPValue, formatValue } from "../../components/charts/chart-utils";
import { ScatterPlot } from "../../components/charts/ScatterPlot";
import { Badge } from "../../components/ui/badge";
import type { BoxPlotChart, ChartSpec, RankedRelationship, ScatterChart } from "../../types/exploration";
import { methodLabel, pairKind } from "./methods";
import { useTool } from "./useTool";

const TEST_FOR_KIND = { numeric: "pearson", mixed: "kruskal_wallis", categorical: "cramers_v" } as const;

export function RelationshipDetail({ datasetId, x, y, ranked, numeric }: {
  datasetId: string;
  x: string;
  y: string;
  ranked?: RankedRelationship;
  numeric: string[];
}) {
  const kind = pairKind(x, y, numeric);
  const ordered = numeric.includes(x) ? [x, y] : [y, x];
  const chartTool = kind === "numeric" ? "chart_scatter" : "chart_boxplot";
  const chart = useTool(datasetId, chartTool, kind === "categorical" ? null : ordered);
  const test = useTool(datasetId, TEST_FOR_KIND[kind], ranked ? null : [x, y]);
  const spec = chart.data?.status === "SUCCESS" ? chart.data.result as unknown as ChartSpec : null;

  const stats = ranked
    ? [
      { label: "Method", value: methodLabel(ranked.method) },
      { label: "Score", value: ranked.score.toFixed(2) },
      { label: "Strength", value: formatValue(ranked.strength) },
      { label: "Adjusted p-value", value: formatPValue(ranked.adjusted_p_value) },
      { label: "Raw p-value", value: formatPValue(ranked.p_value) },
      { label: "Complete rows", value: formatValue(ranked.sample_size, 0) },
    ]
    : test.data?.status === "SUCCESS"
      ? [
        { label: "Method", value: methodLabel(test.data.method) },
        { label: "Strength", value: formatValue(test.data.effect_size) },
        { label: "p-value (uncorrected)", value: formatPValue(test.data.p_value) },
        { label: "Complete rows", value: formatValue(test.data.sample_size, 0) },
      ]
      : [];
  const notes = [...(ranked?.warnings ?? []), ...(ranked ? [] : test.data?.warnings ?? []), ...(chart.data?.warnings ?? [])];

  return <div className="relationship-detail">
    <div className="detail-heading">
      <h3><span className="variable-name">{x}</span> <span className="muted">↔</span> <span className="variable-name">{y}</span></h3>
      {ranked ? <Badge tone="info">Ranked candidate</Badge> : <Badge>Not in ranking · single test</Badge>}
    </div>
    <div className="detail-layout">
      <div className="detail-chart">
        {kind === "categorical"
          ? <div className="chart-placeholder"><Info size={16} />Both columns are categorical; a contingency view is not available yet. Use the statistics on the right.</div>
          : chart.error ? <div className="error-panel" role="alert"><TriangleAlert size={16} /><div>{chart.error.message}</div></div>
            : spec?.kind === "scatter" ? <ScatterPlot chart={spec as ScatterChart} stale={chart.stale} />
              : spec?.kind === "boxplot" ? <BoxPlot chart={spec as BoxPlotChart} stale={chart.stale} />
                : chart.data ? <div className="chart-placeholder"><Info size={16} />{chart.data.warnings?.[0] ?? "Chart not available."}</div>
                  : <div className="chart-placeholder"><LoaderCircle size={16} className="spin" />Computing chart…</div>}
      </div>
      <dl className="detail-stats">
        {stats.map((item) => <div key={item.label}><dt>{item.label}</dt><dd>{item.value}</dd></div>)}
        {ranked && ranked.supporting.length > 0 && <div className="supporting"><dt>Supporting evidence</dt>
          <dd>{ranked.supporting.map((item) => <span key={item.method}>
            {methodLabel(item.method)}: <strong>{formatValue(item.strength)}</strong>
            {item.p_value != null && <> · p {formatPValue(item.p_value)}</>}</span>)}</dd></div>}
      </dl>
    </div>
    {notes.length > 0 && <ul className="detail-notes">{notes.map((note) => <li key={note}>{note}</li>)}</ul>}
  </div>;
}
