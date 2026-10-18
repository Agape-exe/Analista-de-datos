import { useEffect, useState } from "react";
import { ApiError, DatasetExpiredError, getDatasetQuality, type DatasetQuality } from "../../lib/api-client";

interface QualityError { reload: boolean; title: string; message: string }
interface QualityState { key: string; data?: DatasetQuality; error?: QualityError }

function explain(error: unknown): QualityError {
  if (error instanceof DatasetExpiredError) return {
    reload: true, title: "El dataset ya no está disponible",
    message: "El dataset ya no está registrado en memoria. Puede haber sido retirado del almacén o el servidor puede haberse reiniciado. Carga nuevamente el archivo.",
  };
  const messages: Record<string, [string, string]> = {
    QUALITY_TOO_LARGE: ["La evaluación excede los límites", "El dataset supera los presupuestos de evaluación de calidad. No se muestran resultados parciales. Vuelve a la carga para seleccionar un dataset más pequeño."],
    QUALITY_UNSUPPORTED: ["La evaluación no es compatible", "El servidor no puede evaluar esta estructura o sus tipos de datos. Esto no significa que las reglas de calidad hayan fallado."],
    NETWORK_ERROR: ["No se puede conectar con el servidor", "Comprueba la conexión y vuelve a intentarlo."],
    INVALID_RESPONSE: ["La respuesta de calidad no es válida", "El servidor devolvió una respuesta incompleta o inconsistente. No se muestran métricas. Vuelve a intentarlo."],
    REQUEST_RATE_LIMITED: ["Límite de solicitudes alcanzado", "Espera un momento y vuelve a intentarlo."],
    ANALYSIS_CAPACITY_EXCEEDED: ["El servidor está ocupado", "La capacidad de evaluación está ocupada. Espera un momento y vuelve a intentarlo."],
    VALIDATION_ERROR: ["No se pudo evaluar el dataset", "El servidor rechazó la solicitud de calidad. Vuelve a intentarlo o revisa la carga."],
  };
  const code = error instanceof ApiError ? error.code : undefined;
  const [title, message] = code && Object.hasOwn(messages, code) ? messages[code]
    : ["No se pudo cargar la calidad", "Ocurrió un error al consultar la evaluación. Vuelve a intentarlo."];
  return { reload: code === "QUALITY_TOO_LARGE", title, message };
}

export function useDatasetQuality(datasetId: string) {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<QualityState>();
  const key = JSON.stringify([datasetId, attempt]);
  useEffect(() => {
    if (!datasetId) return;
    const controller = new AbortController();
    // Skip the cancelled first development effect under React StrictMode.
    queueMicrotask(() => {
      if (controller.signal.aborted) return;
      getDatasetQuality(datasetId, controller.signal)
        .then((data) => { if (!controller.signal.aborted) setState({ key, data }); })
        .catch((error: unknown) => { if (!controller.signal.aborted) setState({ key, error: explain(error) }); });
    });
    return () => controller.abort();
  }, [datasetId, key]);
  const current = state?.key === key;
  return {
    data: current ? state.data : undefined,
    error: current ? state.error : undefined,
    loading: Boolean(datasetId) && !current,
    retry: () => setAttempt((value) => value + 1),
  };
}
