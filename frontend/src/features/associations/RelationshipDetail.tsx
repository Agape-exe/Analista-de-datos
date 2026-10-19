import { Info, LoaderCircle, TriangleAlert } from "lucide-react";
import { BoxPlot } from "../../components/charts/BoxPlot";
import { formatPValue, formatValue } from "../../components/charts/chart-utils";
import { ScatterPlot } from "../../components/charts/ScatterPlot";
import { Badge } from "../../components/ui/badge";
import type { BoxPlotChart, ChartSpec, RankedRelationship, ScatterChart } from "../../types/exploration";
import { ContingencyTable } from "./ContingencyTable";
import { readContingency } from "./contingency-contract";
import { methodLabel, pairKind } from "./methods";
import { explainNote } from "./notes";
import { ToolNotice } from "./ToolNotice";
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
  const contingency = useTool(datasetId, "chart_contingency", kind === "categorical" ? [x, y] : null);
  const table = readContingency(contingency, x, y);
  const spec = chart.data?.status === "SUCCESS" ? chart.data.result as unknown as ChartSpec : null;

  const stats = ranked
    ? [
      { label: "Método", value: methodLabel(ranked.method) },
      { label: "Puntaje (0–1)", value: ranked.score.toFixed(2) },
      { label: "Tamaño del efecto", value: formatValue(ranked.strength) },
      { label: "Valor p ajustado", value: formatPValue(ranked.adjusted_p_value) },
      { label: "Valor p sin ajustar", value: formatPValue(ranked.p_value) },
      { label: "Filas completas", value: formatValue(ranked.sample_size, 0) },
    ]
    : test.data?.status === "SUCCESS"
      ? [
        { label: "Método", value: methodLabel(test.data.method) },
        { label: "Tamaño del efecto", value: formatValue(test.data.effect_size) },
        { label: "Valor p (sin corregir)", value: formatPValue(test.data.p_value) },
        { label: "Filas completas", value: formatValue(test.data.sample_size, 0) },
      ]
      : [];
  const notes = [...(ranked?.warnings ?? []), ...(ranked ? [] : test.data?.warnings ?? []), ...(chart.data?.warnings ?? [])].map(explainNote);
  // An individual test outside the ranking has no multiple-comparison correction.
  if (!ranked && test.data?.status === "SUCCESS") {
    notes.unshift("Prueba individual sin corrección por comparaciones múltiples: un valor p bajo aquí no equivale a una candidata significativa del ranking.");
  }
  if (spec?.kind === "scatter" && (spec as ScatterChart).trend) {
    notes.push("La recta es un ajuste lineal descriptivo de estos datos; no es un modelo predictivo ni causal.");
  }

  return <div className="relationship-detail">
    <div className="detail-heading">
      <h3><span className="variable-name">{x}</span> <span className="muted">↔</span> <span className="variable-name">{y}</span></h3>
      {ranked ? <Badge tone="info">Candidata del ranking</Badge> : <Badge>Fuera del ranking · prueba individual</Badge>}
    </div>
    <div className="detail-layout">
      <div className="detail-chart">
        {kind === "categorical"
          ? table.kind === "ready" ? <ContingencyTable table={table.table} stale={contingency.stale} />
            : table.kind === "invalid" ? <div className="chart-placeholder" role="alert"><Info size={16} />La tabla de contingencia recibida no corresponde a este par o está incompleta. No se muestra.</div>
              : <ToolNotice tool={contingency} loadingLabel="Calculando tabla de contingencia…" />
          : chart.error ? <div className="error-panel" role="alert"><TriangleAlert size={16} /><div>{chart.error.message}</div></div>
            : spec?.kind === "scatter" ? <ScatterPlot chart={spec as ScatterChart} stale={chart.stale} />
              : spec?.kind === "boxplot" ? <BoxPlot chart={spec as BoxPlotChart} stale={chart.stale} />
                : chart.data ? <div className="chart-placeholder"><Info size={16} />{chart.data.warnings?.[0] ?? "Gráfico no disponible."}</div>
                  : <div className="chart-placeholder"><LoaderCircle size={16} className="spin" />Calculando gráfico…</div>}
      </div>
      <dl className="detail-stats">
        {stats.map((item) => <div key={item.label}><dt>{item.label}</dt><dd>{item.value}</dd></div>)}
        {ranked && ranked.supporting.length > 0 && <div className="supporting"><dt>Otras medidas del mismo par</dt>
          <dd>{ranked.supporting.map((item) => <span key={item.method}>
            {methodLabel(item.method)}: <strong>{formatValue(item.strength)}</strong>
            {item.p_value != null && <> · p {formatPValue(item.p_value)}</>}</span>)}</dd></div>}
      </dl>
    </div>
    {notes.length > 0 && <ul className="detail-notes">{notes.map((note) => <li key={note}>{note}</li>)}</ul>}
  </div>;
}
