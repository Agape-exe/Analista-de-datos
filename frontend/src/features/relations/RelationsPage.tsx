import { Link } from "react-router-dom";
import { Card } from "../../components/ui/card";
import { methodLabel } from "../associations/methods";
import { useReport } from "../reports/ReportProvider";

export function RelationsPage() {
  const { report, loading } = useReport();

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
          <Link to="/report">Ir a Hallazgos y evidencia</Link>
        </Card>
      </div>
    );
  }

  const assessments = report.relationship_assessments ?? [];
  const evidences = report.evidence ?? [];
  const results = report.analysis_results ?? [];

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

      {assessments.length === 0 && (
        <Card className="quality-card">
          <h2>Sin evaluaciones disponibles</h2>
          <p>
            No existen evaluaciones críticas para este reporte.
            Esto no significa que las relaciones sean robustas.
          </p>
        </Card>
      )}

      {assessments.map((assessment, index) => {
        const classification =
          assessment.potentially_spurious === true
            ? "Potencialmente espuria"
            : assessment.potentially_spurious === false
              ? "No marcada como espuria"
              : "Indeterminada";

        return (
          <Card className="quality-card" key={index}>
            <h2>
              {assessment.variables.join(" ↔ ") ||
                "Relación sin variables identificadas"}
            </h2>

            <p>
              <strong>Clasificación:</strong> {classification}
            </p>

            <p>
              <strong>Justificación:</strong>{" "}
              {assessment.rationale || "No se proporcionó una justificación."}
            </p>

            <h3>Evidencias vinculadas</h3>

            {!assessment.evidence_ids?.length && (
              <p>No se registraron referencias de evidencia.</p>
            )}

            <ul>
              {(assessment.evidence_ids ?? []).map((evidenceId) => {
                const evidence = evidences.find(
                  (item) => item.evidence_id === evidenceId,
                );

                const original = evidence
                  ? results.find(
                      (item) => item.analysis_id === evidence.analysis_id,
                    )
                  : undefined;

                if (!evidence) {
                  return (
                    <li key={evidenceId}>
                      Referencia no disponible: {evidenceId}
                    </li>
                  );
                }

                const rawControls =
                  original?.metadata?.control_variables ??
                  original?.metadata?.control_variable;

                const controls =
                  typeof rawControls === "string"
                    ? rawControls
                    : Array.isArray(rawControls)
                      ? rawControls.filter(
                          (value): value is string =>
                            typeof value === "string",
                        ).join(", ")
                      : null;

                return (
                  <li key={evidenceId}>
                    <p>{evidence.description}</p>

                    {original ? (
                      <>
                        <p>
                          Método: {methodLabel(original.method)}
                          {" · "}
                          Muestra: {original.sample_size ?? "No informada"}
                        </p>

                        {controls && (
                          <p>Variables de control: {controls}</p>
                        )}

                        <a href={`#analysis-${original.analysis_id}`}>
                          Ver resultado original
                        </a>
                      </>
                    ) : (
                      <p>Resultado original no disponible.</p>
                    )}

                    {!!evidence.limitations?.length && (
                      <details>
                        <summary>Limitaciones de la evidencia</summary>
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

            {!!assessment.limitations?.length && (
              <details>
                <summary>Limitaciones de la evaluación</summary>
                <ul>
                  {assessment.limitations.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              </details>
            )}
          </Card>
        );
      })}

      <Card className="quality-card">
        <h2>Resultados estadísticos originales</h2>

        {results.length === 0 && <p>No hay resultados disponibles.</p>}

        {results.map((result) => (
          <article
            key={result.analysis_id}
            id={`analysis-${result.analysis_id}`}
          >
            <h3>
              {methodLabel(result.method)} · {result.status}
            </h3>
            <p>Variables: {result.variables?.join(" / ")}</p>
            <p>ID de análisis: {result.analysis_id}</p>

            <details>
              <summary>Ver cálculo registrado</summary>
              <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
                {JSON.stringify(result.result, null, 2)}
              </pre>
            </details>
          </article>
        ))}
      </Card>
    </div>
  );
}
