
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test, vi } from "vitest";

import type { AnalysisReport } from "../../lib/api-client";
import { IntakeProvider } from "../data-intake/IntakeProvider";
import { useReport } from "../reports/ReportProvider";
import { RelationsPage } from "./RelationsPage";

// ==========================================================
// 1. SIMULAR EL PROVEEDOR DE REPORTES
// ==========================================================

vi.mock("../reports/ReportProvider", () => ({
  useReport: vi.fn(),
}));

// ==========================================================
// 2. PREPARAR EL REPORTE PARA LAS PRUEBAS
// ==========================================================

function prepareReport(report: AnalysisReport | null) {
  vi.mocked(useReport).mockReturnValue({
    report,
    reportIdentity: report ? {
      origin: "recovered", datasetId: report.dataset_profile?.dataset_id ?? null,
      matchesActiveDataset: null, previous: false, previousReason: null,
    } : null,
    compatibleReport: null,
    question: "",
    runId: report?.run_id ?? "",
    setQuestion: () => {},
    setRunId: () => {},
    cancel: () => {},
    notice: null,
    loading: false,
    error: null,
    generate: async () => {},
    recover: async () => {},
  });
}

// ==========================================================
// 3. RENDERIZAR LA PANTALLA CON LOS CONTEXTOS NECESARIOS
// ==========================================================

function renderPage() {
  render(
    <MemoryRouter>
      <IntakeProvider>
        <RelationsPage />
      </IntakeProvider>
    </MemoryRouter>,
  );
}

// ==========================================================
// 4. REPORTE SINTÉTICO PARA LAS PRUEBAS
// ==========================================================

const exampleReport: AnalysisReport = {
  run_id: "run-critic-001",
  status: "SUCCESS",

  analysis_results: [
    {
      analysis_id: "partial-001",
      method: "partial_correlation",
      variables: ["publicidad", "ventas"],
      status: "SUCCESS",
      completeness: "complete",
      result: {
        correlation: 0.16,
      },
      effect_size: 0.16,
      sample_size: 100,
      execution_time: 0,
      metadata: {
        control_variables: ["campaña"],
      },
    },
  ],

  evidence: [
    {
      evidence_id: "evidence-001",
      analysis_id: "partial-001",
      description:
        "La correlación disminuyó al controlar campaña.",
      limitations: [
        "No demuestra causalidad.",
      ],
    },
  ],

  relationship_assessments: [
    {
      variables: ["publicidad", "ventas"],
      evidence_ids: ["evidence-001"],
      potentially_spurious: true,
      rationale:
        "Debilitamiento relevante de la correlación.",
      limitations: [
        "Evaluación estadística preliminar.",
      ],
    },
  ],
};

// ==========================================================
// PRUEBA 1: MOSTRAR EL ESTADO SIN REPORTE
// ==========================================================

test("AUD-032: muestra el estado sin reporte", () => {
  prepareReport(null);

  renderPage();

  expect(
    screen.getByText("Sin reporte disponible"),
  ).toBeInTheDocument();
});

// ==========================================================
// PRUEBA 2: MOSTRAR RELACIONES, EVIDENCIAS Y CONTROLES
// ==========================================================

test("AUD-032: muestra relaciones, evidencias y controles", () => {
  prepareReport(exampleReport);

  renderPage();

  // Verificar las variables de la relación
  expect(
    screen.getByText("publicidad ↔ ventas"),
  ).toBeInTheDocument();

  // Verificar la clasificación de Critic
  expect(
    screen.getByText(/Potencialmente espuria/),
  ).toBeInTheDocument();

  // Verificar la justificación estadística
  expect(
    screen.getByText(/Debilitamiento relevante/),
  ).toBeInTheDocument();

  // Verificar la variable de control registrada
  expect(
    screen.getByText("Variables de control: campaña"),
  ).toBeInTheDocument();

  // Verificar el enlace hacia el resultado original
  expect(
    screen.getByRole("link", {
      name: "Ver resultado original",
    }),
  ).toHaveAttribute(
    "href",
    "#analysis-partial-001",
  );
});

// ==========================================================
// PRUEBA 3: CONSERVAR LA CLASIFICACIÓN INDETERMINADA
// ==========================================================

test("AUD-032: conserva la clasificación indeterminada", () => {
  prepareReport({
    ...exampleReport,

    relationship_assessments: [
      {
        ...exampleReport.relationship_assessments![0],
        potentially_spurious: null,
      },
    ],
  });

  renderPage();

  expect(
    screen.getByText(/Indeterminada/),
  ).toBeInTheDocument();
})
