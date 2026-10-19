import { useEffect } from "react";
import { Link } from "react-router-dom";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import type { GroundedReference } from "../../lib/api-client";
import { ReportContextCard } from "../reports/ReportContextCard";
import { useReport } from "../reports/ReportProvider";
import { useChat } from "./ChatProvider";

const anchor = (prefix: string, id: string) => `${prefix}-${encodeURIComponent(id)}`;

function referenceDestination(reference: GroundedReference): string {
  if (reference.evidence_id) return `/report#${anchor("evidence", reference.evidence_id)}`;
  if (reference.analysis_id) return `/report#${anchor("analysis", reference.analysis_id)}`;
  if (reference.path.startsWith("/metrics/")) return "/metrics";
  if (reference.path.startsWith("/relationship_assessments/")) return "/relations";
  if (reference.path.startsWith("/dataset_profile/")) return "/summary";
  if (reference.path.startsWith("/warnings/")) return "/trace";
  return "/report";
}

function referenceLabel(reference: GroundedReference): string {
  if (reference.evidence_id) return `Evidencia ${reference.evidence_id}`;
  if (reference.analysis_id) return `Resultado ${reference.analysis_id}`;
  return reference.path;
}

export function ChatPage() {
  const { report } = useReport();
  const { catalog, catalogLoading, catalogError, loadCatalog, question, setQuestion,
    history, loading, error, notice, ask, cancel } = useChat();

  useEffect(() => { if (report) void loadCatalog(); }, [loadCatalog, report]);

  return <div className="dataset-page chat-page">
    <div className="page-heading"><p className="eyebrow">Asistente / Reporte</p>
      <h1>Chat fundamentado</h1>
      <p>Consulta un reporte guardado. Las respuestas se limitan al catálogo y enlazan sus fuentes.</p></div>
    {!report ? <Card className="empty-state">
      <h2>Sin reporte disponible</h2>
      <p>Genera o recupera un reporte antes de consultar sus resultados.</p>
      <Button asChild><Link to="/report">Ir a Hallazgos</Link></Button>
    </Card> : <>
      <ReportContextCard />
      <Card className="quality-card chat-compose">
        <h2>Pregunta sobre la ejecución {report.run_id}</h2>
        <p>El asistente no ejecuta análisis nuevos ni completa información ausente.</p>
        <div className="chat-examples" aria-label="Preguntas soportadas">
          <h3>Ejemplos soportados</h3>
          {catalogLoading && <p role="status">Cargando catálogo de preguntas…</p>}
          {catalogError && <div role="alert"><p>{catalogError}</p>
            <Button variant="outline" size="small" onClick={() => void loadCatalog()}>Reintentar catálogo</Button></div>}
          {Object.entries(catalog).map(([key, label]) => <Button key={key} variant="outline" size="small"
            disabled={loading} aria-label={`Usar pregunta: ${label}`} onClick={() => setQuestion(key)}>{label}</Button>)}
        </div>
        <label>Pregunta <input aria-label="Pregunta para el reporte" value={question} disabled={loading}
          placeholder="Selecciona un ejemplo o escribe una clave del catálogo"
          onChange={(event) => setQuestion(event.target.value)} /></label>
        <div className="inline-actions">
          <Button disabled={loading || !question.trim()} onClick={() => void ask()}>{loading ? "Consultando…" : "Preguntar"}</Button>
          {loading && <Button variant="outline" onClick={cancel}>Cancelar espera</Button>}
        </div>
        {loading && <p role="status">Consultando exclusivamente el reporte guardado…</p>}
        {notice && <p role="status">{notice}</p>}
        {error && <p role="alert">{error}</p>}
      </Card>
      <Card className="quality-card chat-history" aria-label="Historial de chat">
        <h2>Historial de esta sesión</h2>
        {!history.length && <p>Aún no hay respuestas para este reporte.</p>}
        {history.map((item) => <article key={item.id}>
          <div className="chat-answer-heading"><h3>{catalog[item.question] ?? item.question}</h3>
            <Badge tone={item.status === "ANSWERED" ? "success" : "warning"}>
              {item.status === "ANSWERED" ? "Respondida" : "Abstención"}</Badge></div>
          <p>{item.answer}</p>
          {item.references?.length ? <div aria-label="Referencias verificables">
            <h4>Referencias verificables</h4><ul>{item.references.map((reference, index) => <li key={`${reference.path}-${index}`}>
              <Link to={referenceDestination(reference)}>{referenceLabel(reference)}</Link> <code>{reference.path}</code>
            </li>)}</ul></div> : <p>Sin referencias: el sistema se abstuvo de responder.</p>}
        </article>)}
      </Card>
    </>}
  </div>;
}
