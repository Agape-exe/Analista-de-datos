import { ArrowRight, Info, TriangleAlert } from "lucide-react";
import { Fragment, useState } from "react";
import { Link } from "react-router-dom";
import { BoxPlot } from "../../components/charts/BoxPlot";
import { formatValue } from "../../components/charts/chart-utils";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { PRIORITY } from "../../lib/api-client";
import type { BoxPlotChart } from "../../types/exploration";
import { ColumnOutcomes, ToolNotice } from "../associations/ToolNotice";
import type { OutlierReading } from "../associations/tool-state";
import { useTool } from "../associations/useTool";
import { useIntake } from "../data-intake/IntakeProvider";
import { columnState, mergeExamples, readAnomalies, type ColumnAnomalies } from "./anomalies-contract";
import { RecordDetail } from "./RecordDetail";

type Evaluated = Extract<OutlierReading, { kind: "evaluated" }>;

const count = (value: number | null | undefined, percentage: number | null | undefined) =>
  value == null ? "No evaluable" : `${value}${percentage == null ? "" : ` (${formatValue(percentage, 1)}%)`}`;

export function AnomaliesPage() {
  const { result } = useIntake();
  const datasetId = result?.profile.dataset_id;
  const numeric = result?.summary.numeric_columns ?? [];

  if (!result || !datasetId) return <Card className="empty-state"><span className="upload-icon"><TriangleAlert size={28} /></span>
    <h1>Aún no hay dataset</h1><p>Primero sube un CSV o TSV. Los valores atípicos se evalúan sobre el dataset que queda en memoria tras la ingesta.</p>
    <Button asChild><Link to="/">Subir dataset <ArrowRight size={15} /></Link></Button>
  </Card>;

  return <div className="anomalies-page">
    <div className="provenance-bar"><Badge tone="info">Calculado en Python</Badge>
      <span>Criterios estadísticos deterministas · sin interpretación de LLM</span></div>
    <div className="page-heading"><p className="eyebrow">Exploración / Anomalías</p><h1>Valores atípicos</h1>
      <p>Observaciones inusuales de las columnas numéricas de {result.filename} según dos criterios: IQR y MAD.</p></div>
    <div className="info-note candidates-note"><Info size={16} /><div>
      <strong>Un valor atípico no es necesariamente un error.</strong>
      <p>Es una observación inusual según un criterio estadístico. Puede ser un valor válido y relevante; no se corrige
        ni se elimina. Revisa el registro original antes de concluir que hay un problema de calidad.</p>
    </div></div>
    {numeric.length
      ? <AnomalyExplorer key={datasetId} datasetId={datasetId} totalRows={result.profile.row_count}
        categorical={result.summary.categorical_columns ?? []} />
      : <div className="info-note"><Info size={16} /><div><strong>No hay columnas numéricas.</strong>
        <p>IQR y MAD solo se aplican a columnas numéricas.</p></div></div>}
  </div>;
}

function AnomalyExplorer({ datasetId, totalRows, categorical }: { datasetId: string; totalRows: number; categorical: string[] }) {
  const tool = useTool(datasetId, "outliers", [], {}, { priority: PRIORITY.primary });
  const reading = readAnomalies(tool);
  const [picked, setPicked] = useState<string | null>(null);
  const columns = reading.kind === "ready" ? reading.columns : [];
  const selected = columns.find((item) => item.column === picked) ?? columns[0];

  return <>
    <Card className="anomalies-card">
      <div className="card-heading"><div><h2>Resumen por columna</h2>
        <p>Atípicos por criterio en cada columna numérica. Selecciona una para ver umbrales, distribución y registros.</p></div></div>
      {reading.kind === "invalid" && <div className="chart-placeholder" role="alert">La respuesta de atípicos está incompleta. No se muestran resultados.</div>}
      {reading.kind !== "ready" && reading.kind !== "invalid" && <ToolNotice tool={tool} loadingLabel="Evaluando columnas…" />}
      {reading.kind === "ready" && <OverviewTable columns={columns} selected={selected?.column} onSelect={setPicked} />}
      <ColumnOutcomes data={tool.data} />
    </Card>
    {selected && <ColumnDetail key={selected.column} datasetId={datasetId} totalRows={totalRows} item={selected} categorical={categorical} />}
  </>;
}

function OverviewTable({ columns, selected, onSelect }: { columns: ColumnAnomalies[]; selected?: string; onSelect: (column: string) => void }) {
  return <div className="table-scroll" role="region" aria-label="Atípicos por columna" tabIndex={0}>
    <table className="ranking-table"><caption className="sr-only">Atípicos IQR y MAD por columna numérica</caption>
      <thead><tr><th scope="col">Columna</th><th scope="col">Observaciones</th><th scope="col">Atípicos IQR</th>
        <th scope="col">Atípicos MAD</th><th scope="col">Estado</th><th scope="col" aria-label="Acción" /></tr></thead>
      <tbody>{columns.map(({ column, reading }) => {
        const evaluated = reading.kind === "evaluated" ? reading.summary : undefined;
        const state = columnState(reading);
        return <tr key={column} className={column === selected ? "selected" : ""}>
          <th scope="row" className="variable-name">{column}</th>
          <td>{evaluated?.count == null ? "—" : formatValue(evaluated.count, 0)}</td>
          <td>{evaluated && !(reading as Evaluated).constant ? count(evaluated.iqr.count, evaluated.iqr.percentage) : "—"}</td>
          <td>{evaluated && !(reading as Evaluated).constant ? count(evaluated.mad?.count, evaluated.mad?.percentage) : "—"}</td>
          <td>{state ? <span className="muted">{state}</span> : <Badge tone="info">Evaluada</Badge>}</td>
          <td><Button variant="ghost" size="small" aria-pressed={column === selected} aria-label={`Inspeccionar ${column}`}
            onClick={() => onSelect(column)}>Inspeccionar</Button></td>
        </tr>;
      })}</tbody>
    </table>
  </div>;
}

function ColumnDetail({ datasetId, totalRows, item, categorical }: { datasetId: string; totalRows: number; item: ColumnAnomalies; categorical: string[] }) {
  const { column, reading } = item;
  const [groupBy, setGroupBy] = useState("");
  const box = useTool(datasetId, "chart_boxplot", groupBy ? [column, groupBy] : [column]);
  const state = columnState(reading);
  return <Card className="anomalies-card">
    <div className="card-heading"><div><h2>Detalle de {column}</h2>
      <p>Umbrales de cada criterio, distribución y registros originales de los ejemplos.</p></div>
      {categorical.length > 0 && <div className="explorer-controls"><div className="field">
        <label htmlFor="anomalies-group">Agrupar diagrama de caja por</label>
        <select id="anomalies-group" value={groupBy} onChange={(event) => setGroupBy(event.target.value)}>
          <option value="">Sin agrupar</option>{categorical.map((name) => <option key={name}>{name}</option>)}</select>
      </div></div>}
    </div>
    {state && <p className="chart-note outlier-state-note" role="note">{explain(reading)}</p>}
    {reading.kind === "evaluated" && !reading.constant && <MethodCards reading={reading} />}
    <h3 className="chart-title">Distribución de {column}{groupBy && ` por ${groupBy}`}</h3>
    {box.data?.status === "SUCCESS"
      ? <div className="anomalies-chart"><BoxPlot chart={box.data.result as unknown as BoxPlotChart} stale={box.stale} /></div>
      : <ToolNotice tool={box} />}
    <p className="chart-note">Los puntos del diagrama de caja son los valores fuera de los bigotes (criterio IQR).</p>
    {reading.kind === "evaluated" && !reading.constant && <Examples datasetId={datasetId} totalRows={totalRows} column={column} reading={reading} />}
  </Card>;
}

function explain(reading: ColumnAnomalies["reading"]): string {
  if (reading.kind === "small-sample") return "Muestra pequeña: con tan pocas observaciones los umbrales IQR y MAD no son fiables, así que no se evalúan atípicos.";
  if (reading.kind === "invalid") return "La respuesta de esta columna no es válida. No se muestran umbrales ni ejemplos.";
  if (reading.constant) return "Columna constante: todos los valores observados son iguales. Sin dispersión no hay valores atípicos que evaluar.";
  const notes: string[] = [];
  if (reading.iqrZero) notes.push("IQR = 0: cualquier valor distinto de los cuartiles queda fuera de los límites; interpreta el conteo IQR con cautela.");
  if (reading.madZero) notes.push("MAD = 0: la mitad o más de los valores coincide con la mediana, así que el puntaje robusto no está definido y el criterio MAD no es evaluable.");
  return notes.join(" ");
}

function MethodCards({ reading }: { reading: Evaluated }) {
  const { iqr, mad } = reading.summary;
  const detail = mad?.lower_bound !== undefined;
  return <div className="method-cards">
    <section aria-label="Criterio IQR"><h3>IQR (Tukey)</h3><dl>
      <div><dt>Regla</dt><dd>Fuera de Q1 − {formatValue(iqr.multiplier ?? 1.5)}·IQR o Q3 + {formatValue(iqr.multiplier ?? 1.5)}·IQR</dd></div>
      <div><dt>Límite inferior</dt><dd>{formatValue(iqr.lower_fence)}</dd></div>
      <div><dt>Límite superior</dt><dd>{formatValue(iqr.upper_fence)}</dd></div>
      <div><dt>Atípicos</dt><dd>{count(iqr.count, iqr.percentage)}</dd></div>
    </dl></section>
    <section aria-label="Criterio MAD"><h3>MAD (z robusto)</h3><dl>
      <div><dt>Regla</dt><dd>|z robusto| &gt; {formatValue(mad?.threshold ?? 3.5)}</dd></div>
      {detail && <div><dt>Mediana · MAD</dt><dd>{formatValue(mad?.median)} · {formatValue(mad?.mad)}</dd></div>}
      <div><dt>Límites equivalentes</dt><dd>{!detail ? "No disponibles en esta versión del servidor"
        : mad?.lower_bound == null ? "No evaluable (MAD = 0)" : `${formatValue(mad.lower_bound)} a ${formatValue(mad.upper_bound)}`}</dd></div>
      <div><dt>Atípicos</dt><dd>{count(mad?.count, mad?.percentage)}</dd></div>
    </dl></section>
  </div>;
}

function Examples({ datasetId, totalRows, column, reading }: { datasetId: string; totalRows: number; column: string; reading: Evaluated }) {
  const [open, setOpen] = useState<number | null>(null);
  const merged = mergeExamples(reading.summary, totalRows);
  const { iqr, mad } = reading.summary;
  let body;
  if (merged.kind === "no-positions") body = <p>Esta respuesta no incluye posiciones originales. No se infieren registros a partir de los valores.</p>;
  else if (merged.kind === "invalid") body = <p role="alert">Las referencias recibidas no son válidas para el dataset actual. No se muestran ejemplos.</p>;
  else if (!merged.examples.length) body = <p>{iqr.count === 0 && !mad?.count ? "Ningún criterio marcó valores atípicos en esta columna." : "No se devolvieron ejemplos con posición para esta evaluación."}</p>;
  else body = <div className="table-scroll" role="region" aria-label="Registros de ejemplos atípicos" tabIndex={0}>
    <table className="outlier-examples-table"><caption className="sr-only">Ejemplos atípicos de {column} con su registro original</caption>
      <thead><tr><th scope="col">Registro</th><th scope="col">Valor</th><th scope="col">IQR</th><th scope="col">MAD (z robusto)</th>
        <th scope="col" aria-label="Registro completo" /></tr></thead>
      <tbody>{merged.examples.map((example) => <Fragment key={example.rowIndex}>
        <tr>
          <th scope="row">Registro {example.rowIndex + 1}</th>
          <td>{example.value === null ? "Valor no representable" : formatValue(example.value, 6)}</td>
          <td>{example.iqr ? <Badge tone="info">Fuera de límites</Badge> : <span className="muted">—</span>}</td>
          <td>{example.robustZ === null ? <span className="muted">{merged.madDetail ? "—" : "No disponible"}</span> : formatValue(example.robustZ, 2)}</td>
          <td><Button variant="outline" size="small" aria-expanded={open === example.rowIndex}
            aria-label={`${open === example.rowIndex ? "Ocultar" : "Ver"} registro ${example.rowIndex + 1}`}
            onClick={() => setOpen(open === example.rowIndex ? null : example.rowIndex)}>
            {open === example.rowIndex ? "Ocultar registro" : "Ver registro"}</Button></td>
        </tr>
        {open === example.rowIndex && <tr className="record-row"><td colSpan={5}>
          <RecordDetail datasetId={datasetId} rowIndex={example.rowIndex} column={column} /></td></tr>}
      </Fragment>)}</tbody>
    </table>
  </div>;
  const limited = (iqr.example_rows && iqr.count > iqr.example_rows.length) || (mad?.count != null && mad.example_rows && mad.count > mad.example_rows.length);
  return <section className="outlier-examples anomaly-examples" aria-label="Ejemplos de valores atípicos">
    <h3>Ejemplos y registros originales</h3>
    {body}
    {limited && <p className="chart-note">Se muestran los ejemplos más alejados de la mediana de cada criterio, no todos los atípicos.</p>}
    <p className="outlier-position-note">Registro = row_index + 1, según el orden del dataset y su vista previa. No es un identificador de negocio, el índice del DataFrame ni la línea física del CSV.</p>
  </section>;
}
