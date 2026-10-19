import { Link } from "react-router-dom";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { useIntake } from "../data-intake/IntakeProvider";
import { metricLabel, stageLabel } from "../reports/labels";
import { ReportContextCard } from "../reports/ReportContextCard";
import { useReport } from "../reports/ReportProvider";
import { metricFields, metricUnits } from "./metric-fields";

const statusNames: Record<string, string> = {
  SUCCESS: "Completado", SKIPPED: "Omitido", FAILED: "Fallido",
};
const state = (value: string | undefined) => value == null ? "No disponible"
  : statusNames[value] ? `${value} · ${statusNames[value]}` : value;
const available = (value: unknown) => value == null ? "No disponible" : String(value);

export function MetricsPage() {
  const { result, loading: intakeLoading } = useIntake();
  const { report, loading, error, notice } = useReport();
  const stages = [...new Set([
    ...Object.keys(report?.stage_statuses ?? {}), ...Object.keys(report?.stage_durations ?? {}),
  ])];
  return <div className="dataset-page report-page metrics-page">
    <div className="page-heading"><p className="eyebrow">Evaluación / Métricas</p>
      <h1>Métricas del integrante 5</h1>
      <p>Mediciones entregadas por el backend para la ejecución del reporte.</p></div>
    <Card className="quality-card"><h2>Dataset activo</h2>
      <p>{result ? `${result.filename} · ID: ${result.profile.dataset_id}` : "Sin dataset activo"}</p>
      {intakeLoading && <p role="status">Carga del dataset pendiente.</p>}
      <Button asChild variant="outline"><Link to="/report">Ir a Hallazgos</Link></Button>
    </Card>
    {loading && <p role="status">Solicitud de reporte pendiente. Las mediciones se actualizarán al finalizar.</p>}
    {error && <p role="alert">{error.expired
      ? "El dataset ya no está en memoria del servidor. Vuelve a subirlo en Nuevo análisis."
      : `La solicitud de reporte falló: ${error.message}`}</p>}
    {notice && <p role="status">{notice}</p>}
    {!report ? <Card className="quality-card"><h2>Sin reporte disponible</h2>
      <p>Genera o recupera un reporte en Hallazgos para consultar sus métricas.</p>
    </Card> : <>
      <ReportContextCard />
      <Card className="quality-card" aria-label="Procedencia de las métricas">
        <h2>Estado: {state(report.status)}</h2><p>Ejecución: {report.run_id}</p>
        <p>Fuente: metrics del reporte de análisis.</p>
        <p>Alcance de ejecución: {available(report.configuration?.execution_scope)}</p>
        {report.status === "SUCCESS" && <p>El reporte se completó; esto no implica que todas las métricas estén medidas.</p>}
        {report.status === "SKIPPED" && <p>El reporte contiene etapas omitidas. Se conservan las mediciones disponibles.</p>}
        {report.status === "FAILED" && <p>La ejecución falló. Las mediciones disponibles pueden ser parciales.</p>}
        <p>No disponible indica un campo nulo u omitido, nunca un cero. Las tasas conservan la escala 0–1 del contrato.</p>
        <p>No se dispone de estados ni motivos de ausencia por métrica. Consulta los motivos disponibles en las advertencias y errores del reporte.</p>
      </Card>
      <Card className="quality-card" aria-label="Métricas del reporte"><h2>Mediciones</h2>
        <table><caption>Métricas del reporte · {report.run_id}</caption>
          <thead><tr><th scope="col">Métrica</th><th scope="col">Valor</th><th scope="col">Unidad / escala</th></tr></thead>
          <tbody>{metricFields.map((name) => <tr key={name}>
            <th scope="row">{metricLabel(name)}</th><td>{available(report.metrics?.[name])}</td><td>{metricUnits[name]}</td>
          </tr>)}</tbody></table>
      </Card>
      <Card className="quality-card"><h2>Etapas y tiempos</h2>
        {stages.length ? <table><caption>Estados y tiempos entregados por el backend</caption>
          <thead><tr><th scope="col">Etapa</th><th scope="col">Estado</th><th scope="col">Segundos</th></tr></thead>
          <tbody>{stages.map((stage) => <tr key={stage}>
            <th scope="row">{stageLabel(stage)}</th><td>{state(report.stage_statuses?.[stage])}</td><td>{available(report.stage_durations?.[stage])}</td>
          </tr>)}</tbody></table> : <p>No hay estados ni tiempos de etapas disponibles.</p>}
      </Card>
      <Card className="quality-card"><h2>Advertencias y errores</h2>
        {report.warnings?.length ? <ul>{report.warnings.map((warning, i) => <li key={i}>{warning}</li>)}</ul>
          : <p>Sin advertencias proporcionadas.</p>}
        {report.errors?.length ? <ul role="alert">{report.errors.map((message, i) => <li key={i}>{message}</li>)}</ul>
          : <p>Sin errores proporcionados.</p>}
      </Card>
    </>}
  </div>;
}
