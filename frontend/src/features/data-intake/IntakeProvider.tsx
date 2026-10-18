import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { ApiError, submitIntake } from "../../lib/api-client";
import type { IntakeDraft, IntakeError, IntakeResponse } from "../../types/intake";

const emptyDraft = (): IntakeDraft => ({ file: null, dictionary: null, delimiter: ",", encoding: "utf-8" });

interface IntakeContextValue {
  contextRevision: number;
  draft: IntakeDraft;
  result: IntakeResponse | null;
  loading: boolean;
  cancelled: boolean;
  cancel: () => void;
  error: IntakeError | null;
  updateDraft: (update: Partial<IntakeDraft>) => void;
  reset: () => void;
  analyze: () => Promise<IntakeResponse | undefined>;
}

const IntakeContext = createContext<IntakeContextValue | null>(null);

export function IntakeProvider({ children }: { children: ReactNode }) {
  const [contextRevision, setContextRevision] = useState(0);
  const [draft, setDraft] = useState<IntakeDraft>(emptyDraft);
  const [result, setResult] = useState<IntakeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [cancelled, setCancelled] = useState(false);
  const [error, setError] = useState<IntakeError | null>(null);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);

  function updateDraft(update: Partial<IntakeDraft>) {
    setDraft((previous) => ({ ...previous, ...update }));
    setError(null);
  }

  function cancel() {
    if (!controller.current) return;
    controller.current.abort();
    controller.current = null;
    setLoading(false);
    setCancelled(true);
  }

  function reset() {
    setContextRevision((value) => value + 1);
    setCancelled(false);
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
    setCancelled(false);
    setError(null);
    setResult(null);
    try {
      const response = await submitIntake(draft, request.signal);
      if (request.signal.aborted || controller.current !== request) return;
      setResult(response);
      return response;
    } catch (error) {
      if (!request.signal.aborted && controller.current === request) {
        setError({
          message: error instanceof Error ? error.message : "Ocurrió un error inesperado.",
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

  return <IntakeContext.Provider value={{ contextRevision, draft, result, loading, cancelled, cancel, error, updateDraft, reset, analyze }}>
    {children}
  </IntakeContext.Provider>;
}

export function useIntake() {
  const context = useContext(IntakeContext);
  if (!context) throw new Error("useIntake must be used within IntakeProvider");
  return context;
}
