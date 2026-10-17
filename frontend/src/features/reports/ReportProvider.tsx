import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { DatasetExpiredError, getReport, runStoredAnalysis, type AnalysisReport } from "../../lib/api-client";
import { useIntake } from "../data-intake/IntakeProvider";

export interface ReportError {
  message: string;
  expired?: boolean;
}

interface ReportContextValue {
  report: AnalysisReport | null;
  loading: boolean;
  error: ReportError | null;
  generate: (question: string) => Promise<void>;
  recover: (runId: string) => Promise<void>;
}

const ReportContext = createContext<ReportContextValue | null>(null);

/** Keeps the latest report across tab changes; it belongs to the dataset analyzed in intake. */
export function ReportProvider({ children }: { children: ReactNode }) {
  const { result } = useIntake();
  const datasetId = result?.profile.dataset_id;
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ReportError | null>(null);
  const controller = useRef<AbortController | null>(null);

  // A different (or cleared) dataset invalidates the report and any request in flight.
  useEffect(() => {
    controller.current?.abort();
    controller.current = null;
    setReport(null);
    setError(null);
    setLoading(false);
  }, [datasetId]);
  useEffect(() => () => controller.current?.abort(), []);

  async function load(fetchReport: (signal: AbortSignal) => Promise<AnalysisReport>) {
    if (controller.current) return;
    const request = new AbortController();
    controller.current = request;
    setLoading(true);
    setError(null);
    try {
      const value = await fetchReport(request.signal);
      if (!request.signal.aborted) setReport(value);
    } catch (cause) {
      if (!request.signal.aborted) setError({
        message: cause instanceof Error ? cause.message : "Error de conexión.",
        expired: cause instanceof DatasetExpiredError,
      });
    } finally {
      if (controller.current === request) {
        controller.current = null;
        setLoading(false);
      }
    }
  }

  async function generate(question: string) {
    if (!datasetId) return;
    await load((signal) => runStoredAnalysis(datasetId, question, signal));
  }

  async function recover(runId: string) {
    await load((signal) => getReport(runId, signal));
  }

  return <ReportContext.Provider value={{ report, loading, error, generate, recover }}>
    {children}
  </ReportContext.Provider>;
}

export function useReport() {
  const context = useContext(ReportContext);
  if (!context) throw new Error("useReport must be used within ReportProvider");
  return context;
}
