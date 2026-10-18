import { Link } from "react-router-dom";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { useIntake } from "../data-intake/IntakeProvider";
import { stageLabel } from "../reports/labels";
import { ReportContextCard } from "../reports/ReportContextCard";
import { useReport } from "../reports/ReportProvider";
import "./trace.css";

const statusNames: Record<string, string> = {
  SUCCESS: "Completado", SKIPPED: "Omitido", FAILED: "Fallido",
};
const valueText = (value: unknown): string => value == null ? "No disponible"
  : typeof value === "string" ? value : JSON.stringify(value);
const statusText = (value: unknown) => typeof value === "string" && statusNames[value]
  ? `${value} · ${statusNames[value]}` : valueText(value);
// Preserve the received precision, including valid zero and very small measurements.
const seconds = (value: unknown) => typeof value === "number" && Number.isFinite(value)
  ? `${value} s` : "No disponible";
const eventFields = new Set(["kind", "method", "status", "duration_seconds"]);

export function TracePage() {
  const { result, loading: intakeLoading } = useIntake();
  const { report, loading, error, notice } = useReport();
  const events = report?.execution_trace;
  const stages = [...new Set([
    ...Object.keys(report?.stage_statuses ?? {}), ...Object.keys(report?.stage_durations ?? {}),
  ])];
  return <div className="dataset-page report-page trace-page">
    <div className="page-heading"><p className="eyebrow">Evaluación / Traza</p>
      <h1>Traza de ejecución</h1><p>Llamadas registradas e información de etapas del reporte.</p></div>
    <Card className="quality-card"><h2>Dataset activo</h2>
      <p>{result ? `${result.filename} · ID: ${result.profile.dataset_id}` : "Sin dataset activo"}</p>
      {intakeLoading && <p role="status">Carga del dataset pendiente.</p>}
      <Button asChild variant="outline"><Link to="/report">Ir a Hallazgos</Link></Button>
      <Button asChild variant="outline"><Link to="/metrics">Ver métricas</Link></Button>
    </Card>
    {loading && <p role="status">Solicitud de reporte pendiente. La traza se actualizará al finalizar.</p>}
    {error && <p role="alert">{error.expired
      ? "El dataset ya no está en memoria del servidor. Vuelve a subirlo en Nuevo análisis."
      : `La solicitud de reporte falló: ${error.message}`}</p>}
    {notice && <p role="status">{notice}</p>}
    {!report ? <Card className="quality-card"><h2>Sin reporte disponible</h2>
      <p>Genera o recupera un reporte en Hallazgos para consultar su traza.</p>
    </Card> : <>
      <ReportContextCard />
      <Card className="quality-card"><h2>Estado del reporte: {statusText(report.status)}</h2>
        <p>Ejecución: {report.run_id}</p>
        {report.status === "FAILED" && <p>La ejecución falló; el reporte se cargó correctamente y puede contener información parcial.</p>}
        <p>Los estados de etapas describen sus resultados, no transiciones. No disponible indica un valor nulo u omitido, nunca un cero.</p>
      </Card>
      <Card className="quality-card" aria-label="Entradas de la traza"><h2>Entradas de la traza</h2>
        <p>Orden recibido del backend. La posición no es una marca de tiempo ni garantiza cronología de inicio.
          Las llamadas no incluyen un identificador de etapa; no se vinculan a las etapas por su posición.</p>
        {events == null ? <p>Este reporte no proporciona execution_trace.</p>
          : events.length === 0 ? <p>Traza vacía: no hay llamadas registradas. Esto no implica que no se hayan ejecutado etapas.</p>
          : <div className="table-scroll" role="region" aria-label="Tabla de llamadas registradas" tabIndex={0}>
            <table className="trace-events-table"><caption>Llamadas registradas · {report.run_id}</caption>
            <thead><tr><th scope="col">Posición recibida</th><th scope="col">Tipo</th><th scope="col">Método</th>
              <th scope="col">Estado</th><th scope="col">Duración (segundos)</th><th scope="col">Detalles recibidos</th></tr></thead>
            <tbody>{events.map((event, index) => {
              const details = Object.entries(event).filter(([key]) => !eventFields.has(key));
              return <tr key={index}><th scope="row">{index + 1}</th><td>{valueText(event.kind)}</td>
                <td>{valueText(event.method)}</td><td>{statusText(event.status)}</td><td>{seconds(event.duration_seconds)}</td>
                <td>{details.length ? <dl>{details.map(([key, value]) => <div key={key}>
                  <dt>{key}</dt><dd>{valueText(value)}</dd>
                </div>)}</dl> : "Sin detalles proporcionados"}</td></tr>;
            })}</tbody></table></div>}
      </Card>
      <Card className="quality-card" aria-label="Información de etapas"><h2>Información de etapas</h2>
        <p>Estados y tiempos agregados, independientes de las llamadas registradas. No se suman como tiempo total.</p>
        {stages.length ? <table><caption>Etapas informadas · {report.run_id}</caption>
          <thead><tr><th scope="col">Etapa</th><th scope="col">Estado</th><th scope="col">Duración (segundos)</th></tr></thead>
          <tbody>{stages.map((stage) => <tr key={stage}><th scope="row">{stageLabel(stage)} ({stage})</th>
            <td>{statusText(report.stage_statuses?.[stage])}</td><td>{seconds(report.stage_durations?.[stage])}</td>
          </tr>)}</tbody></table> : <p>Sin información de etapas disponible.</p>}
      </Card>
      <Card className="quality-card"><h2>Advertencias y errores del reporte</h2>
        <p>Motivos generales del reporte; no se atribuyen a una llamada o etapa concreta.</p>
        {report.warnings?.length ? <ul>{report.warnings.map((message, index) => <li key={index}>{message}</li>)}</ul>
          : <p>Sin advertencias proporcionadas.</p>}
        {report.errors?.length ? <ul>{report.errors.map((message, index) => <li key={index}>{message}</li>)}</ul>
          : <p>Sin errores proporcionados.</p>}
      </Card>
    </>}
  </div>;
}
