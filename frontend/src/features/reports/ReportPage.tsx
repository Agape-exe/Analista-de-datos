import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { downloadJson } from "../../lib/download";
import type { StoredConfiguration } from "../../lib/api-client";
import { methodLabel } from "../associations/methods";
import { useIntake } from "../data-intake/IntakeProvider";
import { metricLabel, stageLabel, statusLabel } from "./labels";
import { useReport } from "./ReportProvider";

const base = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");

export function ReportPage() {
  const { result } = useIntake();
  const { report, loading, error, generate, recover } = useReport();
  const [runId, setRunId] = useState(report?.run_id ?? "");
  const [question, setQuestion] = useState("");
  const [options, setOptions] = useState<StoredConfiguration>({});
  const [customize, setCustomize] = useState(false);
  const { hash } = useLocation();
  useEffect(() => {
    if (hash.startsWith("#result-")) document.getElementById(hash.slice(1))?.scrollIntoView?.();
  }, [hash, report?.run_id]);
  const [shownRun, setShownRun] = useState(report?.run_id);
  if (report?.run_id !== shownRun) {
    setShownRun(report?.run_id);
    if (report) setRunId(report.run_id);
  }

  return <div className="dataset-page report-page">
    <div className="page-heading"><p className="eyebrow">Análisis / Reporte</p>
      <h1>Hallazgos y evidencia</h1><p>Consulta los hallazgos, sus limitaciones y el estado de cada etapa.</p></div>
    <Card className="quality-card">
      <h2>Ejecutar un análisis</h2>
      {result ? <form onSubmit={(event) => { event.preventDefault(); void generate(question, customize ? options : undefined); }}>
        <p>Dataset: {result.filename} · {result.summary.rows} filas · {result.summary.columns} columnas</p>
        <p>Se reutiliza el dataset ya cargado y comprendido en Nuevo análisis; no se vuelve a leer el archivo.</p>
        <label>Pregunta opcional <input aria-label="Pregunta del análisis" value={question} disabled={loading}
          onChange={(event) => setQuestion(event.target.value)} /></label>
        <label><input type="checkbox" checked={customize} disabled={loading}
          onChange={(event) => setCustomize(event.target.checked)} />Personalizar configuración</label>
        {customize && <fieldset disabled={loading}><legend>Opciones operativas</legend>
          <label>Modo <select aria-label="Modo de planificación" value={options.analysis?.mode ?? ""}
            onChange={(event) => { const analysis = { ...options.analysis }; if (!event.target.value) delete analysis.mode;
              else analysis.mode = event.target.value as "fast" | "standard"; setOptions({ ...options, analysis }); }}>
            <option value="">Valor del servidor</option>
            <option value="fast">Rápido: diversidad de familias</option><option value="standard">Estándar: más candidatas</option></select></label>
          {([ ["max_hypotheses", "Máximo de hipótesis", 1, 20], ["max_tool_calls", "Presupuesto de herramientas", 0, 100],
            ["minimum_sample_size", "Muestra mínima", 2, 250000] ] as const).map(([key, label, min, max]) =>
            <label key={key}>{label}<input aria-label={label} type="number" min={min} max={max}
              placeholder="Valor del servidor" value={options.analysis?.[key] ?? ""}
              onChange={(event) => { const analysis = { ...options.analysis }; if (event.target.value === "") delete analysis[key];
                else analysis[key] = Number(event.target.value); setOptions({ ...options, analysis }); }} /></label>)}
          <label>Timeout (segundos)<input aria-label="Timeout (segundos)" type="number" min="0.1" max="120" step="0.1"
            placeholder="Valor del servidor" value={options.performance?.timeout_seconds ?? ""}
            onChange={(event) => setOptions({ ...options, performance: event.target.value === "" ? {} : { timeout_seconds: Number(event.target.value) } })} /></label>
          <p>Ejecución secuencial. Sin ciclos del crítico ni proveedor LLM. El timeout es cooperativo.</p>
        </fieldset>}
        <Button type="submit" disabled={loading}>
          {loading ? "Procesando…" : report ? "Volver a generar" : "Generar reporte"}</Button>
      </form> : <>
        <p>Primero sube y comprende un dataset en Nuevo análisis; el reporte se genera sobre ese dataset.</p>
        <Button asChild variant="outline"><Link to="/">Ir a Nuevo análisis</Link></Button>
      </>}
    </Card>
    <Card className="quality-card"><h2>Recuperar un reporte</h2>
      <label>ID de ejecución <input aria-label="ID de ejecución" value={runId} disabled={loading}
        onChange={(event) => setRunId(event.target.value)} /></label>
      <Button variant="outline" disabled={loading || !runId.trim()} onClick={() => void recover(runId)}>Consultar</Button>
    </Card>
    {error && <p role="alert">{error.expired
      ? "El dataset ya no está en memoria del servidor. Vuelve a subirlo en Nuevo análisis."
      : error.message}</p>}
    {report && <>
      <Card className="quality-card"><h2>Estado: {statusLabel(report.status)}</h2><p>Ejecución: {report.run_id}</p>
        <p>Contexto del reporte: dataset {report.dataset_id ?? report.dataset_profile?.dataset_id ?? "no registrado"}.
          {result && (report.dataset_id ?? report.dataset_profile?.dataset_id) !== result.profile.dataset_id
            ? " Este reporte no corresponde al dataset cargado actualmente." : ""}</p>
        <p>Pregunta registrada: {report.user_question ?? "No registrada"}</p>
        <Link to="/trace">Ver traza de esta ejecución</Link>
        {report.status === "FAILED" && <ul role="alert">{(report.errors?.length ? report.errors : ["Error no especificado."])
          .map((value, i) => <li key={i}>{value}</li>)}</ul>}
        {report.status === "SKIPPED" && <p>El reporte contiene etapas pendientes. Los campos sin medición no representan cero.</p>}
        <div className="inline-actions"><Button variant="outline" onClick={() => downloadJson("analysis-report.json", report)}>Descargar JSON</Button>
          <a href={`${base}/reports/${encodeURIComponent(report.run_id)}/markdown`}>Descargar informe</a></div>
      </Card>
      <Card className="quality-card"><h2>Configuración efectiva</h2>
        {report.audit_version ? <><pre>{JSON.stringify(report.configuration, null, 2)}</pre>
          <p>Capacidades operativas: ejecución secuencial, sin ciclo crítico ni LLM.</p></>
          : <p>Reporte histórico: la configuración operativa no está verificada por un snapshot de auditoría.</p>}
      </Card>
      <Card className="quality-card"><h2>Hallazgos</h2>
        {report.insights?.length ? report.insights.map((insight) => <article key={insight.insight_id}>
          <p>{insight.statement}</p><details><summary>Ver referencias y limitaciones</summary><p>Evidencias: {insight.evidence_ids?.join(", ")}</p>
          <ul>{insight.limitations?.map((item, i) => <li key={i}>{item}</li>)}</ul></details>
        </article>) : <p>No hay hallazgos respaldados por evidencia disponibles.</p>}
      </Card>
      <Card className="quality-card"><h2>Etapas y tiempos</h2><table><thead><tr><th>Etapa</th><th>Estado</th><th>Segundos</th></tr></thead>
        <tbody>{Object.entries(report.stage_statuses || {}).map(([stage, state]) => <tr key={stage}>
          <td>{stageLabel(stage)}</td><td>{statusLabel(state)}</td><td>{report.stage_durations?.[stage]?.toFixed(4) ?? "Sin medición"}</td></tr>)}</tbody></table>
      </Card>
      <Card className="quality-card"><h2>Métricas</h2><table><tbody>
        {Object.entries(report.metrics || {}).map(([name, value]) => <tr key={name}><th>{metricLabel(name)}</th>
          <td>{value === null ? "Sin medición" : String(value)}</td></tr>)}
      </tbody></table></Card>
      <Card className="quality-card"><h2>Resultados y evidencia</h2>
        {(report.analysis_results || []).map((value) => <article id={`result-${value.analysis_id}`} key={value.analysis_id}>
          <h3>{methodLabel(value.method)} · {value.status}</h3><p>{value.variables?.join(" / ")}</p><details><summary>Ver cálculo completo</summary><pre>{JSON.stringify(value.result, null, 2)}</pre></details>
        </article>)}
        {(report.evidence || []).map((value) => <p key={value.evidence_id}>{value.evidence_id} → {value.analysis_id}: {value.description}</p>)}
      </Card>
      <Card className="quality-card"><h2>Advertencias y errores</h2><ul>
        {[...(report.warnings || []), ...(report.errors || [])].map((value, i) => <li key={i}>{value}</li>)}
      </ul></Card>
    </>}
  </div>;
}
