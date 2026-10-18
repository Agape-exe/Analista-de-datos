import { Link } from "react-router-dom";
import { Card } from "../../components/ui/card";
import { useIntake } from "../data-intake/IntakeProvider";
import { stageLabel, statusLabel } from "./labels";
import { useReport } from "./ReportProvider";

export function TracePage() {
  const { report, loading, error } = useReport();
  const { result } = useIntake();
  if (!report) return <Card><h1>Traza de ejecución</h1>
    <p>{loading ? "Cargando reporte…" : "Genera o recupera un reporte en Hallazgos para consultar su traza."}</p>
    {error && <p role="alert">{error.message}</p>}<Link to="/report">Ir a Hallazgos</Link></Card>;
  const datasetId = report.dataset_id ?? report.dataset_profile?.dataset_id;
  const events = report.execution_trace ?? [];
  const resultIds = new Set(report.analysis_results?.map((item) => item.analysis_id));
  return <div className="dataset-page report-page"><div className="page-heading"><h1>Traza de ejecución</h1>
    <p>Ejecución: {report.run_id} · Dataset del reporte: {datasetId ?? "No registrado"}</p>
    <p>Pregunta: {report.user_question ?? "No registrada"}</p>
    {result && datasetId !== result.profile.dataset_id && <p role="note">Este reporte pertenece a otro contexto; el dataset cargado actualmente no se usa para reconstruir la traza.</p>}
    <Link to="/report">Volver al reporte</Link></div>
    {!report.audit_version && <Card><h2>Reporte histórico sin instrumentación verificable</h2>
      <p>No contiene el contrato de auditoría actual. Los pasos o tiempos ausentes no se reconstruyen ni se interpretan como cero.</p></Card>}
    <Card className="quality-card"><h2>Agentes</h2><ul>{Object.entries(report.stage_statuses ?? {}).map(([name, status]) =>
      <li key={name}>{stageLabel(name)}: {statusLabel(status)} · {report.stage_durations?.[name]?.toFixed(4) ?? "Sin medición"} s</li>)}</ul></Card>
    <Card className="quality-card"><h2>Plan y decisiones</h2>
      {report.analysis_plan ? <><p>Política: {report.analysis_plan.policy_version}</p><ol>
        {report.analysis_plan.steps?.map((step) => <li key={step.step_id}>
          <strong>{step.step_id}</strong>: {step.request.method} · {step.request.variables?.join(" / ")}
          <p>Hipótesis: {step.hypothesis_id ?? "No registrada"} · Dependencias: {step.depends_on?.join(", ") || "Ninguna"}</p>
          <pre>{JSON.stringify(step.request.parameters ?? {})}</pre></li>)}</ol>
        </> : <p>No hay plan registrado.</p>}
      <ul>{(report.planning_decisions ?? report.analysis_plan?.decisions ?? []).map((decision, index) => <li key={index}>
        <strong>{decision.selected ? "Seleccionada" : "Omitida"}</strong>: {Array.isArray(decision.variables) ? decision.variables.join(" / ") : "Planificación"}
        <p>{String(decision.reason ?? "Sin motivo registrado")}</p>
        <details><summary>Detalle de la decisión</summary><pre>{JSON.stringify(decision, null, 2)}</pre></details></li>)}</ul>
    </Card>
    <Card className="quality-card"><h2>Eventos reales</h2>
      <p>Screening: {report.metrics?.screening_calls ?? "Sin medición"} llamadas · Analysis presupuestado: {report.metrics?.tool_calls ?? "Sin medición"} llamadas.</p>
      {!events.length && <p>No hay eventos instrumentados disponibles.</p>}
      <ol>{events.map((event, index) => <li key={String(event.event_id ?? index)}>
        <strong>{String(event.agent ?? event.kind ?? "Evento")}</strong> · {String(event.method ?? "")} · {String(event.status ?? "Sin estado")}
        <p>Ámbito: {String(event.scope ?? "agente")} · Paso: {String(event.step_id ?? "No aplica")} · Duración: {typeof event.duration_seconds === "number" ? event.duration_seconds.toFixed(4) + " s" : "Sin medición"}</p>
        {typeof event.analysis_id === "string" && resultIds.has(event.analysis_id)
          && <Link to={`/report#result-${encodeURIComponent(event.analysis_id)}`}>Ver resultado {event.analysis_id}</Link>}
        <details><summary>Detalle del evento</summary><pre>{JSON.stringify(event, null, 2)}</pre></details>
      </li>)}</ol>
    </Card>
    <Card className="quality-card"><h2>Omisiones y advertencias</h2><ul>{[...(report.warnings ?? []), ...(report.errors ?? [])].map((note, index) => <li key={index}>{note}</li>)}</ul></Card>
  </div>;
}
