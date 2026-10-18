import { useEffect, useState } from "react";
import { ApiError, DatasetExpiredError, getDatasetPreview, PreviewTooLargeError, type DatasetPreview } from "../../lib/api-client";

interface PreviewError {
  kind: "unavailable" | "too-large" | "request";
  message: string;
}

interface PreviewState {
  key: string;
  page?: DatasetPreview;
  error?: PreviewError;
}

function explain(error: unknown): PreviewError {
  if (error instanceof DatasetExpiredError) return { kind: "unavailable", message: "El dataset ya no está disponible en memoria. Puede haber sido retirado del almacén o el servidor puede haberse reiniciado. Carga nuevamente el archivo." };
  if (error instanceof PreviewTooLargeError) return { kind: "too-large", message: "La página solicitada supera los límites de la vista previa. Prueba con menos filas. Si una celda o el esquema son demasiado grandes, reducir las filas puede no resolverlo. No se han truncado valores." };
  const messages: Record<string, string> = {
    NETWORK_ERROR: "No se puede conectar con el servidor. Comprueba la conexión y vuelve a intentarlo.",
    INVALID_RESPONSE: "La respuesta del servidor está incompleta o no es válida para esta página. Vuelve a intentarlo.",
    VALIDATION_ERROR: "El servidor rechazó los parámetros de esta página. Revisa el tamaño de página y reintenta.",
    PREVIEW_UNSUPPORTED: "Esta página contiene un valor que el servidor no puede representar de forma segura. No se han cambiado los datos.",
    REQUEST_RATE_LIMITED: "Se alcanzó el límite de solicitudes. Espera un momento y vuelve a intentarlo.",
    ANALYSIS_CAPACITY_EXCEEDED: "El servidor está ocupado. Espera un momento y vuelve a intentarlo.",
  };
  const code = error instanceof ApiError ? error.code : undefined;
  return { kind: "request", message: code && Object.hasOwn(messages, code) ? messages[code] : "No se pudo cargar la vista previa. Vuelve a intentarlo." };
}

export function useDatasetPreview(datasetId: string, offset: number, limit: number) {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<PreviewState>();
  const key = JSON.stringify([datasetId, offset, limit, attempt]);
  useEffect(() => {
    if (!datasetId) return;
    const controller = new AbortController();
    // React StrictMode immediately cleans up its first development effect. Defer
    // dispatch one microtask so that cancelled setup never sends a duplicate GET.
    queueMicrotask(() => {
      if (controller.signal.aborted) return;
      getDatasetPreview(datasetId, { offset, limit }, controller.signal)
        .then((page) => { if (!controller.signal.aborted) setState({ key, page }); })
        .catch((error: unknown) => { if (!controller.signal.aborted) setState({ key, error: explain(error) }); });
    });
    return () => controller.abort();
  }, [datasetId, offset, limit, key]);
  const current = state?.key === key;
  return {
    page: current ? state.page : undefined,
    error: current ? state.error : undefined,
    loading: Boolean(datasetId) && !current,
    retry: () => setAttempt((value) => value + 1),
  };
}
