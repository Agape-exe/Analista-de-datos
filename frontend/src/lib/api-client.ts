import type { components } from "../types/api";
import type { AnalysisResult, ToolRunRequest } from "../types/exploration";
import type { IntakeDraft, IntakeResponse } from "../types/intake";

export class ApiError extends Error {
  constructor(message: string, public readonly requestId?: string) {
    super(message);
    this.name = "ApiError";
  }
}

function errorMessage(payload: unknown): string {
  if (typeof payload !== "object" || payload === null || !("detail" in payload)) {
    return "No se pudo completar la solicitud. Inténtalo de nuevo.";
  }
  const detail = payload.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item: { msg?: string }) => item.msg || "Entrada no válida").join("; ");
  }
  if (typeof detail === "object" && detail !== null && "message" in detail) {
    return String(detail.message);
  }
  return "No se pudo procesar el dataset.";
}

export async function submitIntake(draft: IntakeDraft, signal?: AbortSignal): Promise<IntakeResponse> {
  if (!draft.file) throw new ApiError("Primero selecciona un dataset CSV o TSV.");
  const body = new FormData();
  body.append("file", draft.file);
  body.append("delimiter", draft.delimiter);
  body.append("encoding", draft.encoding);
  if (draft.dictionary) body.append("data_dictionary", draft.dictionary);
  return request<IntakeResponse>("/intake", { method: "POST", body, signal });
}

export class DatasetExpiredError extends ApiError {}

export async function runTool(
  datasetId: string, tool: string, body: ToolRunRequest, signal?: AbortSignal,
): Promise<AnalysisResult> {
  const path = `/datasets/${encodeURIComponent(datasetId)}/tools/${encodeURIComponent(tool)}`;
  return request<AnalysisResult>(path, {
    method: "POST", body: JSON.stringify(body), headers: { "Content-Type": "application/json" }, signal,
  });
}

export type AnalysisReport = components["schemas"]["AnalysisReport"];

export async function runStoredAnalysis(
  datasetId: string, userQuestion: string, signal?: AbortSignal,
): Promise<AnalysisReport> {
  return request<AnalysisReport>(`/analysis/datasets/${encodeURIComponent(datasetId)}`, {
    method: "POST", body: JSON.stringify({ user_question: userQuestion.trim() || null }),
    headers: { "Content-Type": "application/json" }, signal,
  });
}

export async function getReport(runId: string, signal?: AbortSignal): Promise<AnalysisReport> {
  return request<AnalysisReport>(`/reports/${encodeURIComponent(runId.trim())}`, { signal });
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  const base = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");
  let response: Response;
  try {
    response = await fetch(`${base}${path}`, init);
  } catch (error) {
    if (init.signal?.aborted) throw error;
    throw new ApiError("No se puede conectar con el backend. Verifica que FastAPI esté en ejecución e inténtalo de nuevo.");
  }
  const requestId = response.headers.get("X-Request-ID") || undefined;
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiError("El servidor devolvió una respuesta ilegible. Revisa la conexión con la API.", requestId);
  }
  if (!response.ok) {
    const Failure = errorCode(payload) === "DATASET_NOT_FOUND" ? DatasetExpiredError : ApiError;
    throw new Failure(errorMessage(payload), requestId);
  }
  return payload as T;
}

function errorCode(payload: unknown): string | undefined {
  if (typeof payload !== "object" || payload === null || !("detail" in payload)) return undefined;
  const detail = payload.detail;
  return typeof detail === "object" && detail !== null && "code" in detail ? String(detail.code) : undefined;
}
