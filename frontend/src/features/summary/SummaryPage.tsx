import { Link } from "react-router-dom";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { formatNumber } from "../../lib/utils";
import { useIntake } from "../data-intake/IntakeProvider";
import { DatasetMetrics } from "../dataset/DatasetMetrics";
import { metricLabel, statusLabel } from "../reports/labels";
import { useReport } from "../reports/ReportProvider";

export function SummaryPage() {
  const { result, loading: intakeLoading, error: intakeError, cancelled } = useIntake();
  const { report, reportIdentity, compatibleReport, loading, error, notice } = useReport();
  // Compatibility establishes provenance; only a completed report supplies summary indicators.
  const completed = compatibleReport?.status === "SUCCESS" ? compatibleReport : null;
  const indicators = [
    { label: "Hallazgos disponibles", value: completed?.insights?.length },
    { label: "Evidencias disponibles", value: completed?.evidence?.length },
    { label: metricLabel("total_response_time"), value: completed?.metrics?.total_response_time },
    { label: metricLabel("tool_calls"), value: completed?.metrics?.tool_calls },
  ];

  return <div className="dataset-page summary-page">
    <div className="page-heading"><p className="eyebrow">Inicio / Resumen</p>
      <h1>Resumen</h1><p>Estado del dataset activo y de su análisis, con acceso a los resultados disponibles.</p></div>

    <Card className="quality-card" aria-label="Dataset activo">
      <h2>{result ? "Dataset activo" : "Sin dataset activo"}</h2>
      {result ? <><p>{result.filename}</p><p>ID: {result.profile.dataset_id}</p>
        <Badge tone="success">Ingesta completada</Badge></>
        : <p>Sube un CSV o TSV en Nuevo análisis para ver sus indicadores.</p>}
      {intakeLoading && <p role="status">Carga del dataset pendiente. Puedes consultar su progreso en Nuevo análisis.</p>}
      {intakeError && <p role="alert">La carga falló: {intakeError.message}</p>}
      {cancelled && <p role="status">Se canceló la espera de carga. Los archivos y opciones se conservan en Nuevo análisis.</p>}
      <div className="inline-actions">
        {result ? <><Button asChild variant="outline"><Link to="/dataset">Ver dataset</Link></Button>
          <Button asChild variant="outline"><Link to="/dictionary">Ver diccionario</Link></Button>
          <Button asChild variant="outline"><Link to="/associations">Explorar asociaciones</Link></Button></>
          : <Button asChild><Link to="/">Ir a Nuevo análisis</Link></Button>}
      </div>
    </Card>
    {result && <section aria-label="Indicadores del dataset activo"><DatasetMetrics result={result} /></section>}

    <Card className="quality-card" aria-label="Análisis del dataset activo">
      <h2>{completed ? "Reporte compatible disponible" : "Sin análisis compatible completado"}</h2>
      {result && !completed && <p>El dataset está cargado; sus indicadores de análisis aún no están disponibles.</p>}
      {!result && <p>Los reportes recuperados se consultan como históricos hasta contar con un dataset activo de identidad coincidente.</p>}
      {loading && <p role="status">Solicitud de reporte pendiente. Los indicadores de análisis no están disponibles durante la espera.</p>}
      {error && <p role="alert">{error.expired
        ? "El dataset ya no está en memoria del servidor. Vuelve a subirlo en Nuevo análisis."
        : `La solicitud de reporte falló: ${error.message}`}</p>}
      {notice && <p role="status">{notice}</p>}
      {compatibleReport && <p>Estado del reporte: {statusLabel(compatibleReport.status)} · Ejecución: {compatibleReport.run_id}</p>}
      {compatibleReport?.status === "FAILED" && <p>El análisis falló. Revisa los errores en Hallazgos.</p>}
      {compatibleReport?.status === "SKIPPED" && <p>El análisis tiene etapas pendientes. No se presentan sus indicadores como resultados completados.</p>}
      <Button asChild variant="outline"><Link to="/report">{completed ? "Ver hallazgos y evidencia" : "Ir a Hallazgos"}</Link></Button>
    </Card>
    {result && <section aria-label="Indicadores del análisis compatible">
      <div className="metrics-grid">{indicators.map(({ label, value }) => <Card className="metric-card" key={label}>
        <p>{label}</p><strong className={value == null ? "muted" : ""}>{value == null ? "—" : formatNumber(value)}</strong>
        <small>{value == null ? "Sin medición disponible" : "Reporte completado del dataset activo"}</small>
      </Card>)}</div>
    </section>}

    {report && reportIdentity && !completed && <Card className="quality-card" aria-label="Contexto del reporte conservado">
      <h2>{reportIdentity.previous ? "Reporte anterior" : reportIdentity.origin === "recovered" ? "Reporte recuperado" : "Reporte generado"}</h2>
      <p>Ejecución: {report.run_id} · Estado: {statusLabel(report.status)}</p>
      <p>Dataset del reporte: {reportIdentity.datasetId ?? "Identidad desconocida"}</p>
      <p>{reportIdentity.matchesActiveDataset === false
        ? "Pertenece a otro dataset. Sus métricas y hallazgos no se atribuyen al dataset activo."
        : reportIdentity.matchesActiveDataset === null
          ? result ? "No se puede verificar su relación con el dataset activo." : "Consulta histórica sin dataset activo."
          : "La identidad coincide con el dataset activo."}</p>
      {reportIdentity.previous && <p>Una solicitud posterior está pendiente, falló o fue cancelada. Este reporte anterior no aporta indicadores al resumen actual.</p>}
      <Button asChild variant="outline"><Link to="/report">Consultar reporte conservado</Link></Button>
    </Card>}
  </div>;
}
