import type { components, operations } from "../types/api";
import type { AnalysisResult, ToolRunRequest } from "../types/exploration";
import { validQuality, type DatasetQuality } from "./quality-response";
import { RequestGate } from "./request-gate";

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
export class RateLimitedError extends ApiError {
  /** retryAfterSeconds is null when the server's Retry-After could not be read. */
  constructor(public readonly retryAfterSeconds: number | null, requestId?: string, code = "REQUEST_RATE_LIMITED") {
    const when = retryAfterSeconds === null ? "en unos segundos" : `en ${retryAfterSeconds} s`;
    super(
      code === "ANALYSIS_CAPACITY_EXCEEDED"
        ? `El servicio de análisis está ocupado. Inténtalo de nuevo ${when}.`
        : `Se alcanzó el límite de solicitudes al backend. Inténtalo de nuevo ${when}.`,
      requestId, code,
    );
  }
}

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

/** Queue order for tool requests: what the page shows first is computed first. */
export const PRIORITY = { primary: 0, normal: 1, secondary: 2 } as const;
const RETRY_PRIORITY = -1;

export async function runTool(
  datasetId: string, tool: string, body: ToolRunRequest, signal?: AbortSignal,
  { priority = PRIORITY.normal }: { priority?: number } = {},
): Promise<AnalysisResult> {
  const path = `/datasets/${encodeURIComponent(datasetId)}/tools/${encodeURIComponent(tool)}`;
  const data = await request<AnalysisResult>(path, {
    method: "POST", body: JSON.stringify(body), headers: { "Content-Type": "application/json" }, signal,
  }, { priority, detachOnAbort: true });
  if (!data || !["SUCCESS", "SKIPPED", "FAILED"].includes(data.status)
    || (data.status !== "SUCCESS" && [data.result, data.p_value, data.effect_size].some((value) => value != null))) {
    throw new ApiError("La herramienta devolvió un estado o resultado incompatible.", undefined, "INVALID_RESPONSE");
  }
  const columns = Object.values(data.column_results ?? {});
  if (columns.some((column) => !column || !["SUCCESS", "SKIPPED", "FAILED"].includes(column.status)
    || (column.status !== "SUCCESS" && column.result != null))
    || (data.status !== "SUCCESS" && columns.some((column) => column.status === "SUCCESS"))
    || (data.status === "SUCCESS" && columns.length > 0 && !columns.some((column) => column.status === "SUCCESS"))
    || (data.status === "SUCCESS" && columns.some((column) => column.status === "SUCCESS")
      && columns.some((column) => column.status !== "SUCCESS") && data.completeness !== "partial")
    || (data.completeness === "partial" && (data.status !== "SUCCESS"
      || !columns.some((column) => column.status === "SUCCESS") || !columns.some((column) => column.status !== "SUCCESS")))) {
    throw new ApiError("El resultado parcial por columna es inconsistente.", undefined, "INVALID_RESPONSE");
  }
  return data;
}

export type AnalysisReport = components["schemas"]["AnalysisReport"];
export type StoredConfiguration = components["schemas"]["StoredConfiguration"];
export type GroundedAnswer = components["schemas"]["GroundedAnswer"];
export type GroundedReference = components["schemas"]["GroundedReference"];

export interface QuestionCatalog {
  questions: Record<string, string>;
}

export async function runStoredAnalysis(
  datasetId: string, userQuestion: string, signal?: AbortSignal, configuration?: StoredConfiguration,
): Promise<AnalysisReport> {
  return request<AnalysisReport>(`/analysis/datasets/${encodeURIComponent(datasetId)}`, {
    method: "POST", body: JSON.stringify({ user_question: userQuestion.trim() || null,
      ...(configuration ? { configuration } : {}) }),
    headers: { "Content-Type": "application/json" }, signal,
  });
}

export async function getReport(runId: string, signal?: AbortSignal): Promise<AnalysisReport> {
  return request<AnalysisReport>(`/reports/${encodeURIComponent(runId.trim())}`, { signal });
}

export async function getQuestionCatalog(signal?: AbortSignal): Promise<QuestionCatalog> {
  const payload = await request<unknown>("/questions/catalog", { signal });
  if (!payload || typeof payload !== "object" || !("questions" in payload)
    || !payload.questions || typeof payload.questions !== "object" || Array.isArray(payload.questions)
    || !Object.entries(payload.questions).every(([key, value]) => key.length > 0 && typeof value === "string" && value.length > 0)) {
    throw new ApiError("El catálogo de preguntas es inválido.", undefined, "INVALID_RESPONSE");
  }
  return payload as QuestionCatalog;
}

export async function askGroundedQuestion(
  runId: string, question: string, signal?: AbortSignal,
): Promise<GroundedAnswer> {
  const expectedQuestion = question.trim();
  const payload = await request<unknown>(`/reports/${encodeURIComponent(runId)}/questions`, {
    method: "POST", body: JSON.stringify({ question: expectedQuestion }),
    headers: { "Content-Type": "application/json" }, signal,
  });
  if (!payload || typeof payload !== "object") {
    throw new ApiError("La respuesta fundamentada es inválida.", undefined, "INVALID_RESPONSE");
  }
  const answer = payload as Partial<GroundedAnswer>;
  const references = answer.references ?? [];
  if (answer.question !== expectedQuestion || !["ANSWERED", "ABSTAINED"].includes(String(answer.status))
    || typeof answer.answer !== "string" || !Array.isArray(references)
    || references.some((reference) => !reference || typeof reference.path !== "string")
    || (answer.status === "ANSWERED" && references.length === 0)
    || (answer.status === "ABSTAINED" && references.length > 0)) {
    throw new ApiError("La respuesta fundamentada no conserva referencias verificables.", undefined, "INVALID_RESPONSE");
  }
  return { ...answer, references } as GroundedAnswer;
}

/**
 * Requests sent at once. Defaults to 1, the production `max_concurrent_operations`
 * (docs/backend-production-readiness.md); a higher client value only turns into 429s.
 */
const MAX_CONCURRENT_REQUESTS = concurrency(import.meta.env.VITE_MAX_CONCURRENT_REQUESTS);
/** ANALYSIS_CAPACITY_EXCEEDED: the server is busy with someone's work; back off, bounded. */
const CAPACITY_BACKOFF_MS = [1_000, 2_000, 4_000, 8_000];
const MAX_RATE_LIMIT_RETRIES = 2;
/** Longer Retry-After waits fail fast with an explanation instead of leaving a silent spinner. */
const MAX_AUTOMATIC_WAIT_MS = 10_000;
/** Retry-After unreadable (e.g. not exposed via CORS): pause instead of retrying in bursts. */
const UNKNOWN_RATE_LIMIT_PAUSE_MS = 15_000;
/** Upper bound for keeping a slot after the caller cancelled a request already sent. */
const DETACHED_HOLD_MAX_MS = 60_000;

function concurrency(raw: unknown): number {
  const value = Number(raw);
  return Number.isSafeInteger(value) && value >= 1 ? value : 1;
}

export const requestGate = new RequestGate(MAX_CONCURRENT_REQUESTS);
let cooldownCode = "REQUEST_RATE_LIMITED";

/** Milliseconds requested by Retry-After (seconds or HTTP date); null when absent or unreadable. */
export function retryAfterMs(header: string | null, now = Date.now()): number | null {
  if (!header) return null;
  const value = header.trim();
  if (/^\d+$/.test(value)) return Number(value) * 1000;
  const date = Date.parse(value);
  return Number.isNaN(date) ? null : Math.max(0, date - now);
}

/** Exponential backoff with ±20 % jitter, never shorter than the server's Retry-After. */
export function capacityDelay(attempt: number, retryAfter: number | null, random = Math.random): number {
  const base = CAPACITY_BACKOFF_MS[Math.min(attempt, CAPACITY_BACKOFF_MS.length - 1)];
  return Math.round(Math.max(base * (0.8 + 0.4 * random()), retryAfter ?? 0));
}

const seconds = (ms: number) => Math.max(1, Math.ceil(ms / 1000));

interface TransportOptions {
  /** Queue order (see PRIORITY); omitted for requests that keep the synchronous fast path. */
  priority?: number;
  /**
   * Once sent, the server keeps computing even if the browser aborts, so a cancelled tool
   * request keeps its slot until the response arrives instead of overlapping the next one.
   */
  detachOnAbort?: boolean;
}

/**
 * Sends a request holding a gate slot. Failures and cancellations free the slot here; a
 * received response is released by the caller once handled, so a 429 cooldown is in
 * place before the next queued request can start.
 */
function send(url: string, init: RequestInit, release: () => void, detach: boolean): Promise<Response> {
  const signal = init.signal;
  const pending = fetch(url, detach && signal ? { ...init, signal: undefined } : init);
  pending.catch(release);
  if (!signal) return pending;
  return new Promise((resolve, reject) => {
    const onAbort = () => {
      if (detach) {
        const hold = setTimeout(release, DETACHED_HOLD_MAX_MS);
        pending.finally(() => { clearTimeout(hold); release(); }).catch(() => undefined);
      } else {
        // Without detach, cancelling frees the slot at once (as an aborted fetch would).
        release();
      }
      reject(signal.reason);
    };
    signal.addEventListener("abort", onAbort, { once: true });
    pending.then(resolve, reject).finally(() => signal.removeEventListener("abort", onAbort));
  });
}

async function request<T>(path: string, init: RequestInit, options: TransportOptions = {}): Promise<T> {
  const base = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");
  let response: Response;
  for (let attempt = 0; ; attempt += 1) {
    const cooldown = requestGate.remainingPause();
    if (cooldown > MAX_AUTOMATIC_WAIT_MS) throw new RateLimitedError(seconds(cooldown), undefined, cooldownCode);
    if (init.signal?.aborted) throw init.signal.reason;
    const release = (attempt === 0 && options.priority === undefined ? requestGate.tryAcquire() : null)
      ?? await requestGate.acquire(init.signal ?? undefined, { priority: attempt > 0 ? RETRY_PRIORITY : options.priority ?? PRIORITY.normal });
    try {
      response = await send(`${base}${path}`, init, release, options.detachOnAbort ?? false);
    } catch (error) {
      if (init.signal?.aborted) throw error;
      throw new ApiError("No se puede conectar con el backend. Verifica que FastAPI esté en ejecución e inténtalo de nuevo.", undefined, "NETWORK_ERROR");
    }
    if (response.status !== 429) {
      release();
      break;
    }
    try {
      const code = errorCode(await response.json().catch(() => null)) ?? "REQUEST_RATE_LIMITED";
      const requestId = response.headers.get("X-Request-ID") || undefined;
      const retryAfter = retryAfterMs(response.headers.get("Retry-After"));
      if (code === "ANALYSIS_CAPACITY_EXCEEDED") {
        if (attempt >= CAPACITY_BACKOFF_MS.length || (retryAfter ?? 0) > MAX_AUTOMATIC_WAIT_MS) {
          throw new RateLimitedError(seconds(retryAfter ?? CAPACITY_BACKOFF_MS[0]), requestId, code);
        }
        requestGate.pause(capacityDelay(attempt, retryAfter));
        continue;
      }
      const wait = retryAfter ?? UNKNOWN_RATE_LIMIT_PAUSE_MS;
      requestGate.pause(wait);
      cooldownCode = code;
      if (retryAfter === null || wait > MAX_AUTOMATIC_WAIT_MS || attempt >= MAX_RATE_LIMIT_RETRIES) {
        const limit = () => new RateLimitedError(retryAfter === null ? null : seconds(wait), requestId, code);
        // Queued requests would otherwise sit behind a long cooldown with a silent spinner.
        if (retryAfter === null || wait > MAX_AUTOMATIC_WAIT_MS) requestGate.failQueued(limit);
        throw limit();
      }
    } finally {
      release();
    }
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
