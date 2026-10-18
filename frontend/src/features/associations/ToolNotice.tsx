import { LoaderCircle } from "lucide-react";
import { Button } from "../../components/ui/button";
import { toolProblem } from "./tool-state";
import type { useTool } from "./useTool";
import type { AnalysisResult } from "../../types/exploration";

export function ColumnOutcomes({ data }: { data?: AnalysisResult }) {
  const omitted = Object.entries(data?.column_results ?? {}).filter(([, item]) => item.status !== "SUCCESS");
  if (!omitted.length) return null;
  return <div role="note"><strong>{data?.completeness === "partial" ? "Resultado parcial" : "Columnas no evaluadas"}</strong>
    <ul>{omitted.map(([column, item]) => <li key={column}>{column}: {item.status === "FAILED" ? "Fallida" : "Omitida"} · {item.warnings?.join("; ")}</li>)}</ul></div>;
}

/** Placeholder for a chart slot: spinner while loading, otherwise why there is nothing to draw. */
export function ToolNotice({ tool, loadingLabel = "Calculando…", emptyLabel = "No disponible." }: {
  tool: ReturnType<typeof useTool>;
  loadingLabel?: string;
  emptyLabel?: string;
}) {
  const problem = toolProblem(tool);
  if (!problem) {
    return <div className="chart-placeholder" role={tool.loading ? "status" : undefined}>
      {tool.loading ? <><LoaderCircle size={16} className="spin" />{loadingLabel}</> : emptyLabel}
    </div>;
  }
  return <div className="chart-placeholder tool-notice" role={problem.kind === "skipped" ? "status" : "alert"}>
    <p>{problem.message}</p>
    {problem.detail && <small>Detalle técnico: {problem.detail}</small>}
    {problem.requestId && <small>ID de solicitud: {problem.requestId}</small>}
    {problem.retryable && <Button variant="outline" size="small" onClick={tool.retry}>Reintentar</Button>}
  </div>;
}
