import type { components, operations } from "../types/api";
import type { AnalysisResult, ToolRunRequest } from "../types/exploration";
import { validQuality, type DatasetQuality } from "./quality-response";

export type { DatasetQuality } from "./quality-response";
import type { IntakeDraft, IntakeResponse } from "../types/intake";

export class ApiError extends Error {
  constructor(message: string, public readonly requestId?: string, public readonly code?: string) {
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
export class PreviewTooLargeError extends ApiError {}

export async function getDatasetQuality(datasetId: string, signal?: AbortSignal): Promise<DatasetQuality> {
  if (!datasetId) throw new ApiError("El identificador del dataset no es válido.", undefined, "VALIDATION_ERROR");
  const payload = await request<unknown>(`/datasets/${encodeURIComponent(datasetId)}/quality`, { method: "GET", signal });
  if (!validQuality(payload, datasetId)) throw new ApiError("La respuesta de calidad es inválida.", undefined, "INVALID_RESPONSE");
  return payload;
}

export type DatasetPreview = components["schemas"]["DatasetPreview"];
type PreviewQuery = NonNullable<operations["preview_dataset_datasets__dataset_id__preview_get"]["parameters"]["query"]>;

const natural = (value: unknown): value is number => typeof value === "number" && Number.isSafeInteger(value) && value >= 0;

function validPreview(payload: unknown, datasetId: string, offset: number, limit: number): payload is DatasetPreview {
  if (!payload || typeof payload !== "object") return false;
  const page = payload as Partial<DatasetPreview>;
  if (page.dataset_id !== datasetId || page.offset !== offset || page.limit !== limit
    || !natural(page.total_rows) || !natural(page.returned_rows) || typeof page.has_more !== "boolean"
    || !Array.isArray(page.columns) || page.columns.length > 1000 || !Array.isArray(page.rows)
    || page.rows.length !== page.returned_rows || page.returned_rows !== Math.min(limit, Math.max(0, page.total_rows - offset))
    || page.columns.length * page.returned_rows > 10_000) return false;
  if (!page.columns.every((column) => column && typeof column.name === "string" && column.name.length > 0
    && typeof column.data_type === "string" && (column.nullable === undefined || typeof column.nullable === "boolean"))) return false;
  if (new Set(page.columns.map((column) => column.name)).size !== page.columns.length) return false;
  const width = page.columns.length;
  if (!page.rows.every((row) => Array.isArray(row) && row.length === width && row.every((value) => value === null
    || typeof value === "string" || typeof value === "boolean" || (typeof value === "number" && Number.isFinite(value))))) return false;
  const end = offset + page.returned_rows;
  return page.has_more === (end < page.total_rows)
    && page.next_offset === (page.has_more ? end : null)
    && (!page.has_more || page.returned_rows > 0);
}

export async function getDatasetPreview(datasetId: string, query: PreviewQuery = {}, signal?: AbortSignal): Promise<DatasetPreview> {
  const offset = query.offset ?? 0;
  const limit = query.limit ?? 20;
  if (!datasetId || !natural(offset) || !Number.isSafeInteger(limit) || limit < 1 || limit > 100) {
    throw new ApiError("Los parámetros de la vista previa no son válidos.", undefined, "VALIDATION_ERROR");
  }
  const params = new URLSearchParams({ offset: String(offset), limit: String(limit) });
  const payload = await request<unknown>(`/datasets/${encodeURIComponent(datasetId)}/preview?${params}`, { method: "GET", signal });
  if (!validPreview(payload, datasetId, offset, limit)) {
    throw new ApiError("La respuesta de la vista previa está incompleta o no corresponde a esta página.", undefined, "INVALID_RESPONSE");
  }
  return payload;
}

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
    throw new ApiError("No se puede conectar con el backend. Verifica que FastAPI esté en ejecución e inténtalo de nuevo.", undefined, "NETWORK_ERROR");
  }
  const requestId = response.headers.get("X-Request-ID") || undefined;
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiError("El servidor devolvió una respuesta ilegible. Revisa la conexión con la API.", requestId, "INVALID_RESPONSE");
  }
  if (!response.ok) {
    const code = errorCode(payload) ?? (response.status === 422 ? "VALIDATION_ERROR" : undefined);
    const Failure = code === "DATASET_NOT_FOUND" ? DatasetExpiredError : code === "PREVIEW_TOO_LARGE" ? PreviewTooLargeError : ApiError;
    throw new Failure(errorMessage(payload), requestId, code);
  }
  return payload as T;
}

function errorCode(payload: unknown): string | undefined {
  if (typeof payload !== "object" || payload === null || !("detail" in payload)) return undefined;
  const detail = payload.detail;
  return typeof detail === "object" && detail !== null && "code" in detail ? String(detail.code) : undefined;
}
