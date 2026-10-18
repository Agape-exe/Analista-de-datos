import { useState } from "react";
import { PRIORITY } from "../../lib/api-client";
import { BoxPlot } from "../../components/charts/BoxPlot";
import { formatValue } from "../../components/charts/chart-utils";
import { Histogram } from "../../components/charts/Histogram";
import { Card } from "../../components/ui/card";
import type { BoxPlotChart, HistogramChart, NumericSummary } from "../../types/exploration";
import { OutlierExamples } from "./OutlierExamples";
import { readOutliers, toolProblem, type OutlierReading } from "./tool-state";
import { ToolNotice } from "./ToolNotice";
import { useTool } from "./useTool";

export function ColumnExplorer({ datasetId, numeric, categorical, totalRows }: {
  datasetId: string;
  numeric: string[];
  categorical: string[];
  totalRows: number;
}) {
  const [column, setColumn] = useState(numeric[0]);
  const [groupBy, setGroupBy] = useState("");
  const histogram = useTool(datasetId, "chart_histogram", [column]);
  const box = useTool(datasetId, "chart_boxplot", groupBy ? [column, groupBy] : [column]);
  const summary = useTool(datasetId, "descriptive_statistics", [column]);
  // Outliers run after the column-dependent requests so they never compete with them.
  // Grouping only the boxplot does not change the outlier query or trigger another evaluation.
  const waiting = histogram.loading || summary.loading;
  const outliers = useTool(datasetId, "outliers", column && !waiting ? [column] : null, {}, { priority: PRIORITY.secondary });
  const outlierTool = { ...outliers, loading: waiting || outliers.loading };
  const stats = summary.data?.status === "SUCCESS"
    ? (summary.data.result as Record<string, NumericSummary> | undefined)?.[column] : undefined;
  const summaryProblem = toolProblem(summary);
  const reading = readOutliers(outlierTool, column);
  const [iqrText, madText] = outlierCells(reading, outlierTool.loading);
  const note = outlierNote(reading);

  return <Card className="explorer-card">
    <div className="card-heading"><div><h2>Distribución de columna</h2>
      <p>Histograma, diagrama de caja y detección de valores atípicos para una columna numérica.</p></div>
      <div className="explorer-controls">
        <div className="field"><label htmlFor="explore-column">Columna</label>
          <select id="explore-column" value={column} onChange={(event) => setColumn(event.target.value)}>
            {numeric.map((name) => <option key={name}>{name}</option>)}</select></div>
        <div className="field"><label htmlFor="explore-group">Agrupar diagrama de caja por</label>
          <select id="explore-group" value={groupBy} onChange={(event) => setGroupBy(event.target.value)}>
            <option value="">Sin agrupar</option>
            {categorical.map((name) => <option key={name}>{name}</option>)}</select></div>
      </div>
    </div>
    <dl className="stat-strip">
      {[
        ["Media", stats?.mean], ["Mediana", stats?.median], ["Desv. estándar", stats?.std],
        ["Mínimo", stats?.min], ["Máximo", stats?.max], ["Asimetría", stats?.skewness],
      ].map(([label, value]) => <div key={label as string}><dt>{label}</dt><dd>{formatValue(value as number | null | undefined)}</dd></div>)}
      <div><dt>Atípicos (IQR)</dt><dd>{iqrText}</dd></div>
      <div><dt>Atípicos robustos (MAD)</dt><dd>{madText}</dd></div>
    </dl>
    {summaryProblem && <ToolNotice tool={summary} />}
    {note && <p className="chart-note outlier-state-note" role="note">{note}</p>}
    <div className="explorer-charts">
      <div><h3 className="chart-title">Distribución</h3>
        {histogram.data?.status === "SUCCESS"
          ? <Histogram chart={histogram.data.result as unknown as HistogramChart} stale={histogram.stale} />
          : <ToolNotice tool={histogram} />}
      </div>
      <div><h3 className="chart-title">Dispersión{groupBy && ` por ${groupBy}`}</h3>
        {box.data?.status === "SUCCESS"
          ? <BoxPlot chart={box.data.result as unknown as BoxPlotChart} stale={box.stale} />
          : <ToolNotice tool={box} />}
        {box.data?.warnings?.map((note) => <p className="chart-note" key={note}>{note}</p>)}
      </div>
    </div>
    <OutlierExamples column={column} totalRows={totalRows} tool={outlierTool} />
  </Card>;
}

const percent = (value: number | null | undefined) => value == null ? "" : ` (${formatValue(value, 1)}%)`;

/** Stat-strip text for the IQR and MAD cells; never presents an unevaluated criterion as zero. */
function outlierCells(reading: OutlierReading, loading: boolean): [string, string] {
  switch (reading.kind) {
    case "pending": return loading ? ["…", "…"] : ["—", "—"];
    case "problem": return ["No disponible", "No disponible"];
    case "invalid": return ["—", "—"];
    case "small-sample": return ["No evaluable", "No evaluable"];
    case "evaluated": {
      const { iqr, mad } = reading.summary;
      if (reading.constant) return ["No aplica", "No aplica"];
      return [
        `${iqr.count}${percent(iqr.percentage)}`,
        reading.madZero || mad?.count == null ? "No evaluable" : `${mad.count}${percent(mad.percentage)}`,
      ];
    }
  }
}

function outlierNote(reading: OutlierReading): string | null {
  if (reading.kind === "small-sample") return "Muestra pequeña: con tan pocas observaciones los umbrales IQR y MAD no son fiables, así que no se evalúan atípicos.";
  if (reading.kind !== "evaluated") return null;
  if (reading.constant) return "Columna constante: todos los valores observados son iguales. Sin dispersión no hay valores atípicos que evaluar.";
  const notes: string[] = [];
  if (reading.iqrZero) notes.push("IQR = 0: el rango intercuartílico es nulo, así que cualquier valor distinto de los cuartiles queda fuera de los límites. Interpreta el conteo IQR con cautela.");
  if (reading.madZero) notes.push("MAD = 0: la mitad o más de los valores coincide con la mediana, por lo que el puntaje robusto no está definido y el criterio MAD no es evaluable.");
  return notes.length ? notes.join(" ") : null;
}
