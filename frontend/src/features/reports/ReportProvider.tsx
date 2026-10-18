import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { DatasetExpiredError, getReport, runStoredAnalysis, type AnalysisReport } from "../../lib/api-client";
import { useIntake } from "../data-intake/IntakeProvider";

export interface ReportError {
  message: string;
  expired?: boolean;
}

type Operation = "generate" | "recover";
export interface ReportIdentity {
  origin: "generated" | "recovered";
  datasetId: string | null;
  matchesActiveDataset: boolean | null;
  previous: boolean;
  previousReason: "generating" | "recovering" | "generation-failed" | "recovery-failed" | null;
}

interface StoredReport {
  key: string;
  report: AnalysisReport;
  identity: Omit<ReportIdentity, "matchesActiveDataset">;
}

interface ReportContextValue {
  report: AnalysisReport | null;
  reportIdentity: ReportIdentity | null;
  compatibleReport: AnalysisReport | null;
  loading: boolean;
  error: ReportError | null;
  generate: (question: string) => Promise<void>;
  recover: (runId: string) => Promise<void>;
}

const ReportContext = createContext<ReportContextValue | null>(null);

/** Report provenance is independent of the active dataset; compatibility is explicit. */
export function ReportProvider({ children }: { children: ReactNode }) {
  const { result, contextRevision } = useIntake();
  const datasetId = result?.profile.dataset_id;
  const key = JSON.stringify([datasetId ?? null, contextRevision]);
  const [stored, setStored] = useState<StoredReport | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [failure, setFailure] = useState<(ReportError & { key: string }) | null>(null);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => {
    controller.current?.abort();
    controller.current = null;
    setStored(null);
    setFailure(null);
    setPending(null);
    return () => { controller.current?.abort(); };
  }, [key]);

  async function load(
    operation: Operation,
    fetchReport: (signal: AbortSignal) => Promise<AnalysisReport>,
    expectedId?: string,
  ) {
    if (controller.current) return;
    const request = new AbortController();
    controller.current = request;
    setPending(key);
    setFailure(null);
    const markPrevious = (reason: ReportIdentity["previousReason"]) => {
      setStored((value) => value?.key === key
        ? { ...value, identity: { ...value.identity, previous: true, previousReason: reason } }
        : value);
    };
    markPrevious(operation === "generate" ? "generating" : "recovering");
    try {
      const value = await fetchReport(request.signal);
      if (request.signal.aborted || controller.current !== request) return;
      const reportedDatasetId = value.dataset_profile?.dataset_id ?? null;
      if (operation === "generate" && reportedDatasetId && reportedDatasetId !== expectedId) {
        throw new Error("El reporte recibido no corresponde al dataset solicitado. No se ha asociado al dataset activo.");
      }
      if (operation === "recover" && value.run_id !== expectedId) {
        throw new Error("El reporte recibido no corresponde al ID de ejecución solicitado.");
      }
      setStored({
        key, report: value,
        identity: {
          origin: operation === "generate" ? "generated" : "recovered",
          datasetId: reportedDatasetId ?? (operation === "generate" ? expectedId ?? null : null),
          previous: false, previousReason: null,
        },
      });
    } catch (cause) {
      if (!request.signal.aborted && controller.current === request) {
        markPrevious(operation === "generate" ? "generation-failed" : "recovery-failed");
        setFailure({
          key, message: cause instanceof Error ? cause.message : "Error de conexión.",
          expired: cause instanceof DatasetExpiredError,
        });
      }
    } finally {
      if (controller.current === request) {
        controller.current = null;
        setPending(null);
      }
    }
  }

  async function generate(question: string) {
    if (!datasetId) return;
    await load("generate", (signal) => runStoredAnalysis(datasetId, question, signal), datasetId);
  }

  async function recover(runId: string) {
    const id = runId.trim();
    if (!id) return;
    await load("recover", (signal) => getReport(id, signal), id);
  }

  // Hide a former context immediately, even before the cancellation effect runs.
  const current = stored?.key === key ? stored : null;
  const report = current?.report ?? null;
  const reportIdentity: ReportIdentity | null = current ? {
    ...current.identity,
    matchesActiveDataset: datasetId && current.identity.datasetId
      ? datasetId === current.identity.datasetId : null,
  } : null;
  const compatibleReport = reportIdentity?.matchesActiveDataset === true && !reportIdentity.previous
    ? report : null;

  return <ReportContext.Provider value={{ report, reportIdentity, compatibleReport,
    loading: pending === key, error: failure?.key === key ? failure : null, generate, recover }}>
    {children}
  </ReportContext.Provider>;
}

export function useReport() {
  const context = useContext(ReportContext);
  if (!context) throw new Error("useReport must be used within ReportProvider");
  return context;
}
