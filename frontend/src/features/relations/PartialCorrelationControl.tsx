
import { useEffect, useRef, useState, type FormEvent } from "react";

import { Button } from "../../components/ui/button";
import { runTool } from "../../lib/api-client";
import type { AnalysisResult } from "../../types/exploration";
import {
  eligibleControls,
  validateControlSelection,
} from "./controlSelection";

interface Props {
  datasetId: string;
  numericColumns: string[];
  variables: string[];
}

export function PartialCorrelationControl({
  datasetId,
  numericColumns,
  variables,
}: Props) {
  const [control, setControl] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const controllerRef = useRef<AbortController | null>(null);

  const options = eligibleControls(numericColumns, variables);

  useEffect(() => {
    return () => controllerRef.current?.abort();
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (controllerRef.current) return;

    const validation = validateControlSelection(
      numericColumns,
      variables,
      control,
    );

    if (validation) {
      setError(validation);
      return;
    }

    const controller = new AbortController();
    controllerRef.current = controller;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await runTool(
        datasetId,
        "partial_correlation",
        {
          variables,
          parameters: {
            control_variable: control,
          },
        },
        controller.signal,
      );

      if (!controller.signal.aborted) {
        setResult(response);
      }
    } catch (cause) {
      if (!controller.signal.aborted) {
        setError(
          cause instanceof Error
            ? cause.message
            : "No se pudo realizar el análisis.",
        );
      }
    } finally {
      if (controllerRef.current === controller) {
        controllerRef.current = null;
        setLoading(false);
      }
    }
  }

  return (
    <section aria-label="Análisis con variable de control">
      <h3>Correlación parcial</h3>

      <p>
        Selecciona una variable numérica adicional para evaluar
        cómo cambia la asociación al controlar su efecto lineal.
      </p>

      {options.length === 0 ? (
        <p>
          No existen variables numéricas adicionales que puedan
          utilizarse como control para esta relación.
        </p>
      ) : (
        <form onSubmit={handleSubmit}>
          <label htmlFor="partial-control">
            Variable de control
          </label>

          <select
            id="partial-control"
            aria-label="Variable de control"
            value={control}
            disabled={loading}
            onChange={(event) => {
              setControl(event.target.value);
              setResult(null);
              setError(null);
            }}
          >
            <option value="">Seleccionar control</option>

            {options.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>

          <Button
            type="submit"
            disabled={loading || !control}
          >
            {loading
              ? "Calculando..."
              : "Solicitar correlación parcial"}
          </Button>
        </form>
      )}

      {error && <p role="alert">{error}</p>}

      {result && result.status === "SUCCESS" && (
        <div role="status">
          <h4>Resultado de la correlación parcial</h4>

          <p>
            Coeficiente: {result.effect_size ?? "No disponible"}
          </p>

          <p>
            Valor p: {result.p_value ?? "No disponible"}
          </p>

          <p>
            Muestra: {result.sample_size ?? "No disponible"}
          </p>

          {!!result.warnings?.length && (
            <ul>
              {result.warnings.map((warning, index) => (
                <li key={index}>{warning}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {result && result.status !== "SUCCESS" && (
        <div role="alert">
          <p>El análisis no pudo completarse.</p>
          <ul>
            {(result.warnings ?? []).map((warning, index) => (
              <li key={index}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      <p>
        Esta consulta es exploratoria e independiente del reporte.
        No actualiza automáticamente la clasificación de Critic
        ni demuestra causalidad.
      </p>
    </section>
  );
}
