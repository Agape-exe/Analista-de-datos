import { useEffect, useState } from "react";
import { ApiError, DatasetExpiredError, PRIORITY, runTool } from "../../lib/api-client";
import type { AnalysisResult } from "../../types/exploration";
import type { IntakeError } from "../../types/intake";

export interface ToolError extends IntakeError {
  expired: boolean;
}

interface ToolState {
  key: string | null;
  data?: AnalysisResult;
  error?: ToolError;
}

/** Results are deterministic for an in-memory dataset; only these outcomes are reused. */
const CACHEABLE = new Set<AnalysisResult["status"]>(["SUCCESS", "SKIPPED"]);
const MAX_CACHED_RESULTS = 200;
const results = new Map<string, AnalysisResult>();
const inflight = new Map<string, { promise: Promise<AnalysisResult>; controller: AbortController; users: number }>();

function remember(key: string, result: AnalysisResult) {
  if (!CACHEABLE.has(result.status)) return;
  results.delete(key);
  results.set(key, result);
  if (results.size > MAX_CACHED_RESULTS) results.delete(results.keys().next().value as string);
}

/** One request per identical tool call; it is only cancelled when every caller has left. */
function shared(key: string, signal: AbortSignal, start: (signal: AbortSignal) => Promise<AnalysisResult>): Promise<AnalysisResult> {
  let entry = inflight.get(key);
  if (!entry) {
    const controller = new AbortController();
    const promise = start(controller.signal).then((result) => { remember(key, result); return result; });
    const created = { promise, controller, users: 0 };
    promise.catch(() => undefined).finally(() => { if (inflight.get(key) === created) inflight.delete(key); });
    inflight.set(key, created);
    entry = created;
  }
  const current = entry;
  current.users += 1;
  return new Promise((resolve, reject) => {
    const leave = () => {
      current.users -= 1;
      if (current.users === 0) {
        if (inflight.get(key) === current) inflight.delete(key);
        current.controller.abort();
      }
      reject(signal.reason);
    };
    signal.addEventListener("abort", leave, { once: true });
    current.promise.then(resolve, reject).finally(() => signal.removeEventListener("abort", leave));
  });
}

export function clearToolCache() {
  results.clear();
  inflight.clear();
}

/**
 * Runs one backend tool when its inputs change. While a new request is in flight the
 * previous result stays available (stale) so charts keep their frame instead of flashing.
 * Successful results are reused across mounts, and identical calls share one request.
 * Pass variables = null to skip the request.
 */
export function useTool(
  datasetId: string | undefined, tool: string, variables: string[] | null,
  parameters: Record<string, string | number> = {},
  { priority = PRIORITY.normal }: { priority?: number } = {},
) {
  const [attempt, setAttempt] = useState(0);
  const request = datasetId && variables ? JSON.stringify([datasetId, tool, variables, parameters]) : null;
  const key = request ? JSON.stringify([request, attempt, priority]) : null;
  const [state, setState] = useState<ToolState>({ key: null });
  const cached = request ? results.get(request) : undefined;

  useEffect(() => {
    if (!key || !request || results.has(request)) return;
    const [id, name, names, params] = JSON.parse(request) as [string, string, string[], Record<string, string | number>];
    const [, , order] = JSON.parse(key) as [string, number, number];
    const controller = new AbortController();
    shared(request, controller.signal, (signal) => runTool(id, name, { variables: names, parameters: params }, signal, { priority: order }))
      .then((data) => { if (!controller.signal.aborted) setState({ key, data }); })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setState({ key, error: {
          message: error instanceof Error ? error.message : "Ocurrió un error inesperado.",
          requestId: error instanceof ApiError ? error.requestId : undefined,
          expired: error instanceof DatasetExpiredError,
        } });
      });
    return () => controller.abort();
  }, [key, request]);

  const retry = () => setAttempt((value) => value + 1);
  if (cached) return { data: cached, error: undefined, loading: false, stale: false, retry };
  const current = state.key === key;
  return {
    data: key ? state.data : undefined,
    error: current ? state.error : undefined,
    loading: key !== null && !current,
    stale: key !== null && !current && state.data !== undefined,
    retry,
  };
}
