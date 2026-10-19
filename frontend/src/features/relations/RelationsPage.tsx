import { Link } from "react-router-dom";

import { Card } from "../../components/ui/card";
import { methodLabel } from "../associations/methods";
import { useIntake } from "../data-intake/IntakeProvider";
import { useReport } from "../reports/ReportProvider";
import { PartialCorrelationControl } from "./PartialCorrelationControl";

export function RelationsPage() {
  const { report, loading, generate, error } = useReport();
  const { result: activeDataset } = useIntake();

  // ==========================================================
  // 1. ESTADO INICIAL: SIN REPORTE DISPONIBLE
  // ==========================================================

  if (!report) {
    return (
      <div className="dataset-page">
        <div className="page-heading">
          <p className="eyebrow">Análisis / Relaciones</p>
          <h1>Revisión crítica de relaciones</h1>
        </div>

        <Card className="quality-card">
          <h2>Sin reporte disponible</h2>

          <p>
            {loading
              ? "El análisis está en proceso."
              : "Genera o recupera un reporte para consultar las relaciones."}
          </p>

          <Link to="/report">
            Ir a Hallazgos y evidencia
          </Link>
        </Card>
      </div>
    );
  }

  // ==========================================================
  // 2. OBTENER EVALUACIONES Y RESULTADOS DEL REPORTE
  // ==========================================================

  const assessments = report.relationship_assessments ?? [];
  const evidences = report.evidence ?? [];
  const results = report.analysis_results ?? [];

  // ==========================================================
  // 3. AUD-038: VALIDAR IDENTIDAD DEL DATASET
  // ==========================================================

  const datasetId = activeDataset?.profile.dataset_id;

  const matchingDataset = Boolean(
    datasetId &&
    report.dataset_profile?.dataset_id === datasetId
  );

  const numericColumns =
    activeDataset?.summary.numeric_columns ?? [];

  // ==========================================================
  // 4. PANTALLA PRINCIPAL DE RELACIONES
  // ==========================================================

  return (
    <div className="dataset-page">
      <div className="page-heading">
        <p className="eyebrow">Análisis / Relaciones</p>

        <h1>Revisión crítica de relaciones</h1>

        <p>
          Consulta las evaluaciones estadísticas, sus evidencias,
          controles y limitaciones.
        </p>

        <p>Reporte: {report.run_id}</p>
      </div>

      {/* =====================================================
          5. ESTADO SIN EVALUACIONES
      ===================================================== */}

      {assessments.length === 0 && (
        <Card className="quality-card">
          <h2>Sin evaluaciones disponibles</h2>

          <p>
            No existen evaluaciones críticas para este reporte.
            Esto no significa que las relaciones sean robustas.
          </p>
        </Card>
      )}

      {/* =====================================================
          6. MOSTRAR EVALUACIONES DE RELACIONES
      ===================================================== */}

      {assessments.map((assessment, index) => {
        const classification =
          assessment.potentially_spurious === true
            ? "Potencialmente espuria"
            : assessment.potentially_spurious === false
              ? "No marcada como espuria"
              : "Indeterminada";

        // AUD-038: permitir controles solamente cuando
        // las dos variables sean numéricas y el dataset coincida.
        const validNumericPair =
          assessment.variables.length === 2 &&
          assessment.variables[0] !== assessment.variables[1] &&
          assessment.variables.every((variable) =>
            numericColumns.includes(variable)
          );

        return (
          <Card className="quality-card" key={index}>

            {/* IDENTIFICACIÓN DE LA RELACIÓN */}

            <h2>
              {assessment.variables.join(" ↔ ") ||
                "Relación sin variables identificadas"}
            </h2>

            {/* CLASIFICACIÓN */}

            <p>
              <strong>Clasificación:</strong>{" "}
              {classification}
            </p>

            {/* JUSTIFICACIÓN */}

            <p>
              <strong>Justificación:</strong>{" "}
              {assessment.rationale ||
                "No se proporcionó una justificación."}
            </p>

            {/* ==============================================
                7. EVIDENCIAS VINCULADAS
            ============================================== */}

            <h3>Evidencias vinculadas</h3>

            {!assessment.evidence_ids?.length && (
              <p>No se registraron referencias de evidencia.</p>
            )}

            <ul>
              {(assessment.evidence_ids ?? []).map((evidenceId) => {
                const evidence = evidences.find(
                  (item) => item.evidence_id === evidenceId
                );

                const original = evidence
                  ? results.find(
                      (item) =>
                        item.analysis_id === evidence.analysis_id
                    )
                  : undefined;

                if (!evidence) {
                  return (
                    <li key={evidenceId}>
                      Referencia no disponible: {evidenceId}
                    </li>
                  );
                }

                // Identificar controles utilizados en resultados previos.
                const rawControls =
                  original?.metadata?.control_variables ??
                  original?.metadata?.control_variable;

                const controls =
                  typeof rawControls === "string"
                    ? rawControls
                    : Array.isArray(rawControls)
                      ? rawControls
                          .filter(
                            (value): value is string =>
                              typeof value === "string"
                          )
                          .join(", ")
                      : null;

                return (
                  <li key={evidenceId}>
                    <p>{evidence.description}</p>

                    {original ? (
                      <>
                        <p>
                          Método: {methodLabel(original.method)}
                          {" · "}
                          Muestra:{" "}
                          {original.sample_size ?? "No informada"}
                        </p>

                        {controls && (
                          <p>
                            Variables de control: {controls}
                          </p>
                        )}

                        <a
                          href={`#analysis-${original.analysis_id}`}
                        >
                          Ver resultado original
                        </a>
                      </>
                    ) : (
                      <p>
                        Resultado original no disponible.
                      </p>
                    )}

                    {!!evidence.limitations?.length && (
                      <details>
                        <summary>
                          Limitaciones de la evidencia
                        </summary>

                        <ul>
                          {evidence.limitations.map((item, i) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      </details>
                    )}
                  </li>
                );
              })}
            </ul>

            {/* ==============================================
                8. LIMITACIONES DE LA EVALUACIÓN
            ============================================== */}

            {!!assessment.limitations?.length && (
              <details>
                <summary>
                  Limitaciones de la evaluación
                </summary>

                <ul>
                  {assessment.limitations.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              </details>
            )}

            {/* ==============================================
                9. AUD-038: SELECCIÓN DE CONTROLES
            ============================================== */}

            {assessment.variables.length === 2 && (
              matchingDataset &&
              datasetId &&
              validNumericPair ? (
                <PartialCorrelationControl
                  key={`${report.run_id}-${index}-${datasetId}`}
                  datasetId={datasetId}
                  numericColumns={numericColumns}
                  variables={assessment.variables}
                  reportLoading={loading}
                  reportError={error?.message}
                  onGenerateReport={(selection) => generate(
                    `Evaluar ${selection.variables.join(" y ")} controlando por ${selection.control_variable}.`,
                    undefined, selection,
                  )}
                />
              ) : (
                <p>
                  Para solicitar una correlación parcial, se
                  necesita el dataset activo correspondiente
                  a este reporte y dos variables numéricas
                  distintas.
                </p>
              )
            )}
          </Card>
        );
      })}

      {/* =====================================================
          10. RESULTADOS ESTADÍSTICOS ORIGINALES
      ===================================================== */}

      <Card className="quality-card">
        <h2>Resultados estadísticos originales</h2>

        {results.length === 0 && (
          <p>No hay resultados disponibles.</p>
        )}

        {results.map((result) => (
          <article
            key={result.analysis_id}
            id={`analysis-${result.analysis_id}`}
          >
            <h3>
              {methodLabel(result.method)} · {result.status}
            </h3>

            <p>
              Variables: {result.variables?.join(" / ")}
            </p>

            <p>
              ID de análisis: {result.analysis_id}
            </p>

            <details>
              <summary>Ver cálculo registrado</summary>

              <pre
                style={{
                  whiteSpace: "pre-wrap",
                  overflowWrap: "anywhere",
                }}
              >
                {JSON.stringify(result.result, null, 2)}
              </pre>
            </details>
          </article>
        ))}
      </Card>
    </div>
  );
}
