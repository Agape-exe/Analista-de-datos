import { useEffect, useState } from "react";
import { ApiError, DatasetExpiredError, runTool } from "../../lib/api-client";
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

/**
 * Runs one backend tool when its inputs change. While a new request is in flight the
 * previous result stays available (stale) so charts keep their frame instead of flashing.
 * Pass variables = null to skip the request.
 */
export function useTool(
  datasetId: string | undefined, tool: string, variables: string[] | null,
  parameters: Record<string, string | number> = {},
) {
  const key = datasetId && variables ? JSON.stringify([datasetId, tool, variables, parameters]) : null;
  const [state, setState] = useState<ToolState>({ key: null });

  useEffect(() => {
    if (!key) return;
    const [id, name, names, params] = JSON.parse(key) as [string, string, string[], Record<string, string | number>];
    const controller = new AbortController();
    runTool(id, name, { variables: names, parameters: params }, controller.signal)
      .then((data) => setState({ key, data }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setState({ key, error: {
          message: error instanceof Error ? error.message : "An unexpected error occurred.",
          requestId: error instanceof ApiError ? error.requestId : undefined,
          expired: error instanceof DatasetExpiredError,
        } });
      });
    return () => controller.abort();
  }, [key]);

  const current = state.key === key;
  return {
    data: key ? state.data : undefined,
    error: current ? state.error : undefined,
    loading: key !== null && !current,
    stale: key !== null && !current && state.data !== undefined,
  };
}
