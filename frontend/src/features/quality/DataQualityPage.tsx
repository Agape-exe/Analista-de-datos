import { ArrowRight, Info, LoaderCircle, ShieldCheck, TriangleAlert } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import type { DatasetQuality } from "../../lib/api-client";
import { formatNumber, formatPercentage } from "../../lib/utils";
import { useIntake } from "../data-intake/IntakeProvider";
import { useDatasetQuality } from "./useDatasetQuality";

const stateLabels = { PASS: "PASS · Cumplida", FAIL: "FAIL · Incumplida", NOT_EVALUATED: "NOT_EVALUATED · No evaluada" } as const;

export function DataQualityPage() {
  const { result, loading, error } = useIntake();
  if (loading) return <div className="processing-panel" role="status"><LoaderCircle className="spin" size={18} /><p>Preparando el dataset para consultar su calidad…</p></div>;
  if (!result?.profile.dataset_id) return <Card className="empty-state data-quality-page">
    <span className="upload-icon"><ShieldCheck size={28} /></span><h1>Aún no hay dataset</h1>
    <p>{error ? "La carga no se completó. Revisa el archivo antes de consultar su calidad." : "Carga un archivo CSV o TSV en Nuevo análisis para consultar sus controles de calidad."}</p>
    <Button asChild><Link to="/">Ir a Nuevo análisis <ArrowRight size={15} /></Link></Button>
  </Card>;
  return <DatasetQualityPanel key={result.profile.dataset_id} datasetId={result.profile.dataset_id} filename={result.filename} />;
}

export function DatasetQualityPanel({ datasetId, filename }: { datasetId: string; filename: string }) {
  const { data, loading, error, retry } = useDatasetQuality(datasetId);
  return <div className="dataset-page data-quality-page">
    <div className="page-heading with-actions"><div><p className="eyebrow">Datos / Calidad de datos</p>
      <h1>Calidad de datos</h1><p>Controles de valores faltantes y filas duplicadas de <strong>{filename}</strong>.</p></div>
      <Button variant="outline" asChild><Link to="/dataset">Ver Dataset <ArrowRight size={14} /></Link></Button>
    </div>
    <div className="provenance-bar"><Badge tone="info"><ShieldCheck size={12} />Métricas calculadas por el servidor</Badge>
      <span>Reglas deterministas · datos originales sin modificar</span></div>
    {loading && <div className="processing-panel" role="status" aria-live="polite"><LoaderCircle className="spin" size={18} /><p>Consultando calidad del dataset…</p></div>}
    {error && <div className="error-panel" role="alert"><TriangleAlert size={18} /><div><h2>{error.title}</h2><p>{error.message}</p>
      <div className="inline-actions">{error.reload ? <Button variant="outline" asChild><Link to="/">Volver a Nuevo análisis</Link></Button>
        : <Button variant="outline" onClick={retry}>Reintentar</Button>}</div>
    </div></div>}
    {data && <QualityResults data={data} />}
  </div>;
}

function QualityResults({ data }: { data: DatasetQuality }) {
  const m = data.missing, d = data.duplicates;
  const metrics = [
    ["Total de filas", formatNumber(data.total_rows)], ["Total de columnas", formatNumber(data.total_columns)],
    ["Total de celdas", formatNumber(data.total_cells)], ["Celdas faltantes", formatNumber(m.missing_cells)],
    ["Porcentaje de celdas faltantes", formatPercentage(m.missing_percentage)],
    ["Filas completas", formatNumber(m.complete_rows)], ["Filas incompletas", formatNumber(m.incomplete_rows)],
    ["Filas duplicadas adicionales", formatNumber(d.duplicate_rows)],
    ["Porcentaje de duplicados", formatPercentage(d.duplicate_percentage)], ["Grupos de duplicados", formatNumber(d.duplicate_groups)],
  ];
  return <>
    <p className="quality-evaluation" role="status"><Badge tone={data.status === "EVALUATED" ? "info" : "neutral"}>
      {data.status === "EVALUATED" ? "Evaluación completada" : "NOT_EVALUATED · Evaluación no realizada"}</Badge>
      {data.status === "NOT_EVALUATED" && <span>No hay filas o columnas suficientes para evaluar las reglas.</span>}</p>
    <section aria-labelledby="quality-summary-heading"><h2 id="quality-summary-heading">Resumen de calidad</h2>
      <dl className="quality-summary-grid">{metrics.map(([label, value]) => <div className="card quality-metric" key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
    </section>
    <Card className="column-card" aria-labelledby="quality-missing-heading"><div className="card-heading"><div>
      <h2 id="quality-missing-heading">Valores faltantes por columna</h2><p>Conteos y porcentajes del servidor, en el orden original de columnas.</p></div></div>
      {m.columns.length ? <div className="table-scroll quality-table-scroll" tabIndex={0} role="region" aria-label="Detalle de valores faltantes">
        <table className="quality-table"><caption className="sr-only">Valores faltantes por columna</caption><thead><tr>
          <th scope="col">Columna</th><th scope="col">Tipo técnico</th><th scope="col">Valores faltantes</th><th scope="col">Porcentaje</th>
        </tr></thead><tbody>{m.columns.map((c) => <tr key={c.column_name}><th scope="row">{c.column_name}</th>
          <td>{c.data_type}</td><td>{formatNumber(c.missing_count)}</td><td>{formatPercentage(c.missing_percentage)}</td></tr>)}</tbody></table>
      </div> : <p>No hay columnas disponibles.</p>}
    </Card>
    <Card className="quality-card" aria-labelledby="quality-duplicates-heading"><div className="card-heading"><h2 id="quality-duplicates-heading">Filas completamente duplicadas</h2></div>
      <p>La comparación incluye todas las columnas y considera iguales los nulos en la misma posición. El conteo adicional excluye la primera aparición de cada grupo.</p>
      <dl className="quality-duplicates-stats"><div><dt>Duplicadas adicionales</dt><dd>{formatNumber(d.duplicate_rows)}</dd></div>
        <div><dt>Porcentaje</dt><dd>{formatPercentage(d.duplicate_percentage)}</dd></div><div><dt>Grupos repetidos</dt><dd>{formatNumber(d.duplicate_groups)}</dd></div></dl>
      <p>Solo se muestran agregados. No se identifican ni eliminan registros individuales.</p>
    </Card>
    <Card className="quality-card" aria-labelledby="quality-rules-heading"><div className="card-heading"><h2 id="quality-rules-heading">Reglas de calidad</h2><Badge>Sin puntaje global</Badge></div>
      <ul className="quality-rules">{data.rules.map((rule) => <li key={rule.rule_id}>
        <div className="quality-rule-heading"><h3>{rule.description}</h3><Badge tone={rule.status === "PASS" ? "success" : rule.status === "FAIL" ? "warning" : "neutral"}>{stateLabels[rule.status]}</Badge></div>
        <code>{rule.rule_id}</code>
        <p>{rule.status === "NOT_EVALUATED" ? "Sin conteo observado" : rule.observed_count == null ? "Conteo no disponible" : `Conteo observado: ${formatNumber(rule.observed_count)}`}</p>
        {rule.reason && <p>{rule.reason}</p>}
      </li>)}</ul>{!data.rules.length && <p>El servidor no devolvió reglas para esta evaluación.</p>}
    </Card>
    <div className="info-note"><Info size={16} /><p>Estos controles describen faltantes y duplicados; no acreditan la calidad general ni la idoneidad del dataset para un análisis. No se aplica limpieza automática.</p></div>
  </>;
}
