import { LoaderCircle } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { formatValue } from "../../components/charts/chart-utils";
import type { OutlierSummary } from "../../types/exploration";
import type { useTool } from "./useTool";

type ExampleRow = { row_index: number; value: number | null };
function validRows(iqr: NonNullable<OutlierSummary["iqr"]>, totalRows: number): iqr is NonNullable<OutlierSummary["iqr"]> & { example_rows: ExampleRow[] } {
  const rows = iqr.example_rows, examples = iqr.examples;
  return Number.isSafeInteger(totalRows) && totalRows >= 0 && Array.isArray(rows) && Array.isArray(examples)
    && Number.isSafeInteger(iqr.count) && iqr.count >= rows.length && rows.length === examples.length
    && rows.every((row, index) => row && Number.isSafeInteger(row.row_index) && row.row_index >= 0 && row.row_index < totalRows
      && (row.value === null || (typeof row.value === "number" && Number.isFinite(row.value)))
      && row.value === examples[index])
    && new Set(rows.map((row) => row.row_index)).size === rows.length;
}

export function OutlierExamples({ column, totalRows, tool }: {
  column: string | undefined;
  totalRows: number;
  tool: ReturnType<typeof useTool>;
}) {
  let content;
  if (tool.loading || tool.stale) content = <p role="status"><LoaderCircle size={14} className="spin" />Consultando ejemplos IQR…</p>;
  else if (tool.error) content = <div role="alert"><p>{tool.error.expired
    ? "El dataset ya no está disponible en memoria. Vuelve a cargar el archivo."
    : "No se pudieron consultar los ejemplos. Revisa la conexión o espera si el servidor está ocupado."}</p>
    {tool.error.expired ? <Button asChild variant="outline"><Link to="/">Volver a cargar</Link></Button>
      : <Button variant="outline" onClick={tool.retry}>Reintentar ejemplos</Button>}</div>;
  else if (!column || !tool.data) content = <p>No hay datos disponibles para consultar ejemplos.</p>;
  else if (tool.data.status !== "SUCCESS") content = <p role="status">{tool.data.status === "SKIPPED"
    ? "La herramienta no pudo evaluar esta columna. No se muestran ejemplos."
    : "La herramienta falló. No se muestran ejemplos."}</p>;
  else {
    const result = tool.data.result;
    const summary = result && typeof result === "object" && !Array.isArray(result)
      ? (result as Record<string, unknown>)[column] as OutlierSummary | undefined : undefined;
    if (tool.data.method !== "outliers" || !Array.isArray(tool.data.variables) || tool.data.variables.length !== 1 || tool.data.variables[0] !== column || !summary) {
      content = <p>No hay referencias de registro válidas para la columna actual.</p>;
    } else if (summary.skipped) content = <p role="status">No hay observaciones suficientes para evaluar esta columna.</p>;
    else if (!summary.iqr || summary.iqr.example_rows === undefined) content = <p>Esta respuesta no incluye posiciones originales. No se infieren registros a partir de los valores.</p>;
    else if (!validRows(summary.iqr, totalRows)) content = <p role="alert">Las referencias recibidas no son válidas para el dataset actual. No se muestran ejemplos.</p>;
    else if (!summary.iqr.example_rows.length) content = <p>{summary.iqr.count === 0
      ? "No se detectaron valores atípicos IQR."
      : "No se devolvieron ejemplos con posición para esta evaluación."}</p>;
    else content = <div className="table-scroll" role="region" aria-label="Registros de ejemplos IQR" tabIndex={0}>
      <table className="outlier-examples-table"><caption className="sr-only">Ejemplos IQR de {column}</caption>
        <thead><tr><th scope="col">Registro</th><th scope="col">Valor</th><th scope="col">Método</th></tr></thead>
        <tbody>{summary.iqr.example_rows.map((row) => <tr key={row.row_index}><th scope="row">Registro {row.row_index + 1}</th>
          <td>{row.value === null ? "Valor no representable" : formatValue(row.value, 6)}</td><td><Badge tone="info">IQR</Badge></td></tr>)}</tbody>
      </table>
    </div>;
  }
  return <section className="outlier-examples" aria-label="Ejemplos de valores atípicos">
    <h3>Ejemplos de valores atípicos <Badge tone="info">IQR</Badge></h3>
    <p>Columna: <strong>{column ?? "Sin seleccionar"}</strong>. Un atípico estadístico puede ser una observación válida; no implica un error ni se elimina.</p>
    {content}
    <p className="outlier-position-note">Registro = row_index + 1, según el orden del dataset y su vista previa. No es un identificador de negocio, el índice del DataFrame ni la línea física del CSV.</p>
  </section>;
}
