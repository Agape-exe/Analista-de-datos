import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { askGroundedQuestion, getQuestionCatalog, type GroundedAnswer } from "../../lib/api-client";
import { useReport } from "../reports/ReportProvider";

export interface ChatExchange extends GroundedAnswer {
  id: number;
}

interface ChatContextValue {
  catalog: Record<string, string>;
  catalogLoading: boolean;
  catalogError: string | null;
  loadCatalog: () => Promise<void>;
  question: string;
  setQuestion: (value: string) => void;
  history: ChatExchange[];
  loading: boolean;
  error: string | null;
  notice: string | null;
  ask: () => Promise<void>;
  cancel: () => void;
}

const ChatContext = createContext<ChatContextValue | null>(null);

export function ChatProvider({ children }: { children: ReactNode }) {
  const { report } = useReport();
  const reportKey = report?.run_id ?? "none";
  const reportKeyRef = useRef(reportKey);
  reportKeyRef.current = reportKey;
  const requestId = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const catalogController = useRef<AbortController | null>(null);
  const [catalog, setCatalog] = useState<Record<string, string>>({});
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<ChatExchange[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    requestId.current += 1;
    controller.current?.abort();
    controller.current = null;
    setQuestion("");
    setHistory([]);
    setLoading(false);
    setError(null);
    setNotice(null);
  }, [reportKey]);

  useEffect(() => () => {
    controller.current?.abort();
    catalogController.current?.abort();
  }, []);

  const loadCatalog = useCallback(async () => {
    if (Object.keys(catalog).length > 0 || catalogController.current) return;
    const current = new AbortController();
    catalogController.current = current;
    setCatalogLoading(true);
    setCatalogError(null);
    try {
      const value = await getQuestionCatalog(current.signal);
      if (!current.signal.aborted && catalogController.current === current) setCatalog(value.questions);
    } catch (cause) {
      if (!current.signal.aborted && catalogController.current === current) {
        setCatalogError(cause instanceof Error ? cause.message : "No se pudo cargar el catálogo de preguntas.");
      }
    } finally {
      if (catalogController.current === current) {
        catalogController.current = null;
        setCatalogLoading(false);
      }
    }
  }, [catalog]);

  async function ask() {
    const text = question.trim();
    if (!report || !text || controller.current) return;
    const current = new AbortController();
    const expectedKey = reportKey;
    const currentId = ++requestId.current;
    controller.current = current;
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      const answer = await askGroundedQuestion(report.run_id, text, current.signal);
      if (current.signal.aborted || controller.current !== current
        || reportKeyRef.current !== expectedKey || requestId.current !== currentId) return;
      setHistory((items) => [...items, { ...answer, id: currentId }]);
      setQuestion("");
    } catch (cause) {
      if (!current.signal.aborted && controller.current === current
        && reportKeyRef.current === expectedKey && requestId.current === currentId) {
        setError(cause instanceof Error ? cause.message : "No se pudo consultar el reporte.");
      }
    } finally {
      if (controller.current === current) {
        controller.current = null;
        setLoading(false);
      }
    }
  }

  function cancel() {
    if (!controller.current) return;
    requestId.current += 1;
    controller.current.abort();
    controller.current = null;
    setLoading(false);
    setNotice("Se canceló la espera de esta respuesta. El historial existente se conserva.");
  }

  return <ChatContext.Provider value={{ catalog, catalogLoading, catalogError, loadCatalog,
    question, setQuestion, history, loading, error, notice, ask, cancel }}>
    {children}
  </ChatContext.Provider>;
}

export function useChat() {
  const value = useContext(ChatContext);
  if (!value) throw new Error("useChat must be used within ChatProvider");
  return value;
}
