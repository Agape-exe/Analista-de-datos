import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { ApiError, submitIntake } from "../../lib/api-client";
import type { IntakeDraft, IntakeError, IntakeResponse } from "../../types/intake";

const emptyDraft = (): IntakeDraft => ({ file: null, dictionary: null, delimiter: ",", encoding: "utf-8" });

interface IntakeContextValue {
  draft: IntakeDraft;
  result: IntakeResponse | null;
  loading: boolean;
  error: IntakeError | null;
  updateDraft: (update: Partial<IntakeDraft>) => void;
  reset: () => void;
  analyze: () => Promise<IntakeResponse | undefined>;
}

const IntakeContext = createContext<IntakeContextValue | null>(null);

export function IntakeProvider({ children }: { children: ReactNode }) {
  const [draft, setDraft] = useState<IntakeDraft>(emptyDraft);
  const [result, setResult] = useState<IntakeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<IntakeError | null>(null);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);

  function updateDraft(update: Partial<IntakeDraft>) {
    setDraft((previous) => ({ ...previous, ...update }));
    setError(null);
  }

  function reset() {
    controller.current?.abort();
    controller.current = null;
    setDraft(emptyDraft());
    setResult(null);
    setError(null);
    setLoading(false);
  }

  async function analyze() {
    if (controller.current) return;
    const request = new AbortController();
    controller.current = request;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await submitIntake(draft, request.signal);
      if (request.signal.aborted) return;
      setResult(response);
      return response;
    } catch (error) {
      if (!request.signal.aborted) {
        setError({
          message: error instanceof Error ? error.message : "An unexpected error occurred.",
          requestId: error instanceof ApiError ? error.requestId : undefined,
        });
      }
    } finally {
      if (controller.current === request) {
        controller.current = null;
        setLoading(false);
      }
    }
  }

  return <IntakeContext.Provider value={{ draft, result, loading, error, updateDraft, reset, analyze }}>
    {children}
  </IntakeContext.Provider>;
}

export function useIntake() {
  const context = useContext(IntakeContext);
  if (!context) throw new Error("useIntake must be used within IntakeProvider");
  return context;
}
