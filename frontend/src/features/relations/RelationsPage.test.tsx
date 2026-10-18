
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test, vi } from "vitest";

import type { AnalysisReport } from "../../lib/api-client";
import { useReport } from "../reports/ReportProvider";
import { RelationsPage } from "./RelationsPage";

vi.mock("../reports/ReportProvider", () => ({
  useReport: vi.fn(),
}));

function prepareReport(report: AnalysisReport | null) {
  vi.mocked(useReport).mockReturnValue({
    report,
    loading: false,
    error: null,
    generate: async () => {},
    recover: async () => {},
  });
}

function renderPage() {
  render(
    <MemoryRouter>
      <RelationsPage />
    </MemoryRouter>,
  );
}

const exampleReport: AnalysisReport = {
  run_id: "run-critic-001",
  status: "SUCCESS",
  analysis_results: [
    {
      analysis_id: "partial-001",
      method: "partial_correlation",
      variables: ["publicidad", "ventas"],
      status: "SUCCESS",
      result: { correlation: 0.16 },
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
      description: "La correlación disminuyó al controlar campaña.",
      limitations: ["No demuestra causalidad."],
    },
  ],
  relationship_assessments: [
    {
      variables: ["publicidad", "ventas"],
      evidence_ids: ["evidence-001"],
      potentially_spurious: true,
      rationale: "Debilitamiento relevante de la correlación.",
      limitations: ["Evaluación estadística preliminar."],
    },
  ],
};

test("AUD-032: muestra el estado sin reporte", () => {
  prepareReport(null);
  renderPage();

  expect(
    screen.getByText("Sin reporte disponible"),
  ).toBeInTheDocument();
});

test("AUD-032: muestra relaciones, evidencias y controles", () => {
  prepareReport(exampleReport);
  renderPage();

  expect(
    screen.getByText("publicidad ↔ ventas"),
  ).toBeInTheDocument();

  expect(
    screen.getByText(/Potencialmente espuria/),
  ).toBeInTheDocument();

  expect(
    screen.getByText(/Debilitamiento relevante/),
  ).toBeInTheDocument();

  expect(
    screen.getByText("Variables de control: campaña"),
  ).toBeInTheDocument();

  expect(
    screen.getByRole("link", { name: "Ver resultado original" }),
  ).toHaveAttribute("href", "#analysis-partial-001");
});

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
});
