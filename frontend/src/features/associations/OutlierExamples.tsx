import { LoaderCircle } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { formatValue } from "../../components/charts/chart-utils";
import type { OutlierSummary } from "../../types/exploration";
import { readOutliers } from "./tool-state";
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
  const reading = readOutliers(tool, column);
  let content;
  if (tool.loading || tool.stale) content = <p role="status"><LoaderCircle size={14} className="spin" />Consultando ejemplos IQR…</p>;
  else if (tool.error) content = <div role="alert"><p>{tool.error.expired
    ? "El dataset ya no está disponible en memoria. Vuelve a cargar el archivo."
    : "No se pudieron consultar los ejemplos. Revisa la conexión o espera si el servidor está ocupado."}</p>
    {tool.error.expired ? <Button asChild variant="outline"><Link to="/">Volver a cargar</Link></Button>
      : <Button variant="outline" onClick={tool.retry}>Reintentar ejemplos</Button>}</div>;
  else if (reading.kind === "problem") content = <div role="status"><p>{reading.problem.kind === "skipped"
    ? "La herramienta no pudo evaluar esta columna. No se muestran ejemplos."
    : "La herramienta falló. No se muestran ejemplos."}</p>
    {reading.problem.retryable && <Button variant="outline" onClick={tool.retry}>Reintentar ejemplos</Button>}</div>;
  else if (reading.kind === "pending") content = <p>No hay datos disponibles para consultar ejemplos.</p>;
  else if (reading.kind === "invalid") content = <p>No hay referencias de registro válidas para la columna actual.</p>;
  else if (reading.kind === "small-sample") content = <p role="status">No hay observaciones suficientes para evaluar esta columna. Con una muestra tan pequeña los umbrales no son fiables, así que no se marca ningún valor.</p>;
  else if (reading.constant) content = <p role="status">La columna es constante: todos los valores observados son iguales, así que no hay dispersión ni valores atípicos que evaluar.</p>;
  else {
    const { iqr } = reading.summary;
    if (iqr.example_rows === undefined) content = <p>Esta respuesta no incluye posiciones originales. No se infieren registros a partir de los valores.</p>;
    else if (!validRows(iqr, totalRows)) content = <p role="alert">Las referencias recibidas no son válidas para el dataset actual. No se muestran ejemplos.</p>;
    else if (!iqr.example_rows.length) content = <p>{iqr.count === 0
      ? "No se detectaron valores atípicos IQR."
      : "No se devolvieron ejemplos con posición para esta evaluación."}</p>;
    else content = <div className="table-scroll" role="region" aria-label="Registros de ejemplos IQR" tabIndex={0}>
      <table className="outlier-examples-table"><caption className="sr-only">Ejemplos IQR de {column}</caption>
        <thead><tr><th scope="col">Registro</th><th scope="col">Valor</th><th scope="col">Método</th></tr></thead>
        <tbody>{iqr.example_rows.map((row) => <tr key={row.row_index}><th scope="row">Registro {row.row_index + 1}</th>
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
