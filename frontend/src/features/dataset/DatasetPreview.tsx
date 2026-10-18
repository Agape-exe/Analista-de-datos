import { ArrowLeft, ArrowRight, LoaderCircle, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import type { DatasetPreview } from "../../lib/api-client";
import { formatNumber } from "../../lib/utils";
import { useDatasetPreview } from "./useDatasetPreview";

function unsafeNumber(value: unknown) {
  return typeof value === "number" && Number.isInteger(value) && !Number.isSafeInteger(value);
}

function PreviewValue({ value }: { value: DatasetPreview["rows"][number][number] }) {
  if (value === null) return <span className="preview-null">Sin dato</span>;
  if (unsafeNumber(value)) return <span className="warning-text" title="El número JSON supera el rango seguro de JavaScript. Su valor exacto no puede garantizarse; consulta el archivo original.">Precisión no garantizada</span>;
  if (value === "") return <span className="muted">Texto vacío</span>;
  return <>{String(value)}</>;
}

export function DatasetPreviewTable({ page }: { page: DatasetPreview }) {
  return <div className="table-scroll preview-scroll" role="region" aria-label="Filas del dataset" tabIndex={0}>
    <table className="preview-table"><caption className="sr-only">Filas de la página actual, en el orden original del archivo</caption>
      <thead><tr>{page.columns.map((column) => <th scope="col" key={column.name}>
        <span>{column.name}</span><small>{column.data_type}</small>
      </th>)}</tr></thead>
      <tbody>{page.rows.map((row, rowIndex) => <tr key={page.offset + rowIndex}>
        {row.map((value, columnIndex) => <td key={page.columns[columnIndex].name}><PreviewValue value={value} /></td>)}
      </tr>)}</tbody>
    </table>
  </div>;
}

export function DatasetPreviewPanel({ datasetId }: { datasetId: string }) {
  const [query, setQuery] = useState({ offset: 0, limit: 20 });
  const { page, loading, error, retry } = useDatasetPreview(datasetId, query.offset, query.limit);
  const unsafe = page?.rows.some((row) => row.some(unsafeNumber));
  return <Card className="column-card preview-card" aria-labelledby="preview-heading">
    <div className="card-heading"><div><h2 id="preview-heading">Vista previa del dataset</h2>
      <p>Filas reales en el orden del archivo. Se consulta únicamente la página solicitada.</p></div><Badge>Solo lectura</Badge></div>
    <div className="preview-toolbar"><label htmlFor="preview-limit">Filas por página</label>
      <select id="preview-limit" value={query.limit} disabled={loading || error?.kind === "unavailable"}
        onChange={(event) => setQuery({ offset: 0, limit: Number(event.target.value) })}>
        {[10, 20, 50, 100].map((size) => <option key={size} value={size}>{size}</option>)}
      </select>
      <span>Hasta 100 filas por consulta</span>
    </div>
    {loading && <div className="processing-panel" role="status" aria-live="polite"><LoaderCircle size={18} className="spin" /><p>Cargando filas del dataset…</p></div>}
    {error && <div className="error-panel" role="alert"><TriangleAlert size={18} /><div>
      <strong>{error.kind === "unavailable" ? "El dataset ya no está disponible" : error.kind === "too-large" ? "La página es demasiado grande" : "No se pudo cargar la vista previa"}</strong>
      <p>{error.message}</p>
      {error.kind === "unavailable" ? <Button asChild variant="outline"><Link to="/">Volver a Nuevo análisis</Link></Button>
        : <Button variant="outline" onClick={retry}>Reintentar</Button>}
    </div></div>}
    {page && <>
      <p className="preview-range" role="status" aria-live="polite">{page.returned_rows > 0
        ? `Filas ${formatNumber(page.offset + 1)}–${formatNumber(page.offset + page.returned_rows)} de ${formatNumber(page.total_rows)} · ${formatNumber(page.returned_rows)} registros mostrados`
        : `0 registros mostrados de ${formatNumber(page.total_rows)}`}</p>
      {unsafe && <div className="info-note preview-precision"><TriangleAlert size={16} /><p>Hay números fuera del rango seguro de JavaScript. Se marcan como «Precisión no garantizada»; consulta el archivo original para conocer su valor exacto.</p></div>}
      {page.returned_rows > 0 ? <DatasetPreviewTable page={page} />
        : <p className="preview-empty">{page.total_rows === 0 ? "Este dataset no contiene filas disponibles." : "No hay filas en esta página. Puedes volver a la página anterior."}</p>}
    </>}
    <nav className="preview-pagination" aria-label="Paginación de filas">
      <Button variant="outline" disabled={loading || !page || page.offset === 0}
        onClick={() => page && setQuery({ offset: Math.max(0, page.offset - page.limit), limit: page.limit })}>
        <ArrowLeft size={14} />Anterior</Button>
      <Button variant="outline" disabled={loading || !page?.has_more || page.next_offset === null}
        onClick={() => page?.next_offset != null && setQuery({ offset: page.next_offset, limit: page.limit })}>
        Siguiente<ArrowRight size={14} /></Button>
    </nav>
    <p className="table-footnote">Los rangos indican posiciones de consulta, no identificadores de negocio. «Sin dato» representa un valor nulo. Puedes desplazar la tabla horizontalmente con el teclado.</p>
  </Card>;
}
