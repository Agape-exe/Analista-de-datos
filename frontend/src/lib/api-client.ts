import type { IntakeDraft, IntakeResponse } from "../types/intake";

export class ApiError extends Error {
  constructor(message: string, public readonly requestId?: string) {
    super(message);
    this.name = "ApiError";
  }
}

function errorMessage(payload: unknown): string {
  if (typeof payload !== "object" || payload === null || !("detail" in payload)) {
    return "The request could not be completed. Please try again.";
  }
  const detail = payload.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item: { msg?: string }) => item.msg || "Invalid input").join("; ");
  }
  if (typeof detail === "object" && detail !== null && "message" in detail) {
    return String(detail.message);
  }
  return "The dataset could not be processed.";
}

export async function submitIntake(draft: IntakeDraft, signal?: AbortSignal): Promise<IntakeResponse> {
  if (!draft.file) throw new ApiError("Select a CSV or TSV dataset first.");
  const body = new FormData();
  body.append("file", draft.file);
  body.append("delimiter", draft.delimiter);
  body.append("encoding", draft.encoding);
  if (draft.dictionary) body.append("data_dictionary", draft.dictionary);
  const base = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");
  let response: Response;
  try {
    response = await fetch(`${base}/intake`, { method: "POST", body, signal });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError("Cannot reach the backend. Check that FastAPI is running and try again.");
  }
  const requestId = response.headers.get("X-Request-ID") || undefined;
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiError("The server returned an unreadable response. Check the API connection.", requestId);
  }
  if (!response.ok) throw new ApiError(errorMessage(payload), requestId);
  return payload as IntakeResponse;
}
