import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../../app/App";
import { intakeFixture } from "../../test/fixture";
import { intakePreviewFixture } from "../../test/preview-fixture";
import { IntakeProvider } from "../data-intake/IntakeProvider";
import { ReportPage } from "./ReportPage";
import { ReportProvider } from "./ReportProvider";

afterEach(() => vi.unstubAllGlobals());

const json = (payload: unknown, status = 200) => new Response(JSON.stringify(payload), { status });

const successReport = {
  run_id: "run-1", status: "SUCCESS", metrics: {}, insights: [], evidence: [], analysis_results: [],
  stage_statuses: { DataUnderstanding: "SUCCESS", Association: "SUCCESS", Planner: "SUCCESS",
    Analysis: "SUCCESS", Critic: "SUCCESS", Insight: "SUCCESS" }, stage_durations: {}, warnings: [], errors: [],
};

function renderReport() {
  render(<MemoryRouter><IntakeProvider><ReportProvider><ReportPage /></ReportProvider></IntakeProvider></MemoryRouter>);
}

async function openInsightsAfterIntake() {
  const user = userEvent.setup();
  render(<MemoryRouter><App /></MemoryRouter>);
  await user.upload(screen.getByLabelText("Archivo del dataset"), new File(["a\n1\n"], "sales.csv"));
  await user.click(screen.getByRole("button", { name: "Comprender dataset" }));
  await screen.findByRole("link", { name: "Explorar asociaciones" });
  await user.click(screen.getByRole("link", { name: "Hallazgos" }));
  return user;
}

test("null metrics stay unmeasured and no insights are invented", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({
    run_id: "fixture", status: "SKIPPED", metrics: { precision: null, llm_calls: 0 },
    insights: [], evidence: [], analysis_results: [], stage_statuses: {}, warnings: [], errors: [],
  })));
  renderReport();
  await userEvent.type(screen.getByLabelText("ID de ejecución"), "fixture");
  await userEvent.click(screen.getByRole("button", { name: "Consultar" }));
  await screen.findByText("Estado: Pendiente");
  expect(screen.getByText("Sin medición")).toBeInTheDocument();
  expect(screen.getByText("0", { exact: true })).toBeInTheDocument();
  expect(screen.getByText("No hay hallazgos respaldados por evidencia disponibles.")).toBeInTheDocument();
});

test("missing report shows server error and enables retry", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ detail: { message: "Unknown run ID" } }, 404)));
  renderReport();
  await userEvent.type(screen.getByLabelText("ID de ejecución"), "missing");
  await userEvent.click(screen.getByRole("button", { name: "Consultar" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Unknown run ID");
  await waitFor(() => expect(screen.getByRole("button", { name: "Consultar" })).toBeEnabled());
});

test("without an intake dataset it points to New Analysis instead of asking for a file", () => {
  renderReport();
  expect(screen.queryByLabelText("Dataset del reporte")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Generar reporte" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Ir a Nuevo análisis" })).toHaveAttribute("href", "/");
});

test("analyzes the intake dataset once and keeps the report across tabs", async () => {
  const fetchMock = vi.fn(async (url: string) =>
    url.endsWith("/intake") ? json(intakeFixture)
      : url.includes("/preview?") ? json(intakePreviewFixture) : json(successReport));
  vi.stubGlobal("fetch", fetchMock);
  const user = await openInsightsAfterIntake();
  expect(screen.getByText(/Dataset: sales\.csv · 2 filas · 3 columnas/)).toBeInTheDocument();
  await user.type(screen.getByLabelText("Pregunta del análisis"), "¿Qué varía?");
  await user.click(screen.getByRole("button", { name: "Generar reporte" }));
  await screen.findByText("Estado: Completado");
  for (const stage of ["Comprensión de datos", "Asociaciones", "Planificación", "Análisis", "Revisión crítica", "Hallazgos"]) {
    expect(screen.getByRole("cell", { name: stage })).toBeInTheDocument();
  }
  const analyses = fetchMock.mock.calls.filter(([url]) => url.includes("/analysis"));
  expect(analyses).toHaveLength(1);
  const [url, init] = analyses[0] as unknown as [string, RequestInit];
  expect(url).toMatch(/\/analysis\/datasets\/test-dataset$/);
  expect(JSON.parse(String(init.body))).toEqual({ user_question: "¿Qué varía?" });

  await user.click(screen.getByRole("link", { name: "Dataset" }));
  await user.click(screen.getByRole("link", { name: "Hallazgos" }));
  expect(screen.getByText("Estado: Completado")).toBeInTheDocument();
  expect(screen.getByLabelText("ID de ejecución")).toHaveValue("run-1");
  expect(screen.getByRole("button", { name: "Volver a generar" })).toBeEnabled();
  expect(fetchMock.mock.calls.filter(([url]) => url.includes("/analysis"))).toHaveLength(1);
});

test("a failed run shows its cause and an expired dataset asks for a new upload", async () => {
  const failed = { ...successReport, status: "FAILED", stage_statuses: {}, errors: ["Workflow timeout exceeded"] };
  const responses = [json(failed), json({ detail: { code: "DATASET_NOT_FOUND", message: "gone" } }, 404)];
  vi.stubGlobal("fetch", vi.fn(async (url: string) =>
    url.endsWith("/intake") ? json(intakeFixture)
      : url.includes("/preview?") ? json(intakePreviewFixture) : responses.shift()!));
  const user = await openInsightsAfterIntake();
  await user.click(screen.getByRole("button", { name: "Generar reporte" }));
  await screen.findByText("Estado: Fallido");
  expect(screen.getByRole("alert")).toHaveTextContent("Workflow timeout exceeded");
  await user.click(screen.getByRole("button", { name: "Volver a generar" }));
  expect(await screen.findByText(/ya no está en memoria/)).toBeInTheDocument();
});


test("a recovered report from another dataset is visibly separated from the active dataset", async () => {
  const historical = { ...successReport, run_id: "historical", dataset_profile: {
    ...intakeFixture.profile, dataset_id: "other-dataset",
  } };
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url.endsWith("/intake") ? json(intakeFixture)
    : url.includes("/preview?") ? json(intakePreviewFixture) : json(historical)));
  const user = await openInsightsAfterIntake();
  await user.type(screen.getByLabelText("ID de ejecución"), "historical");
  await user.click(screen.getByRole("button", { name: "Consultar" }));
  expect(await screen.findByRole("heading", { name: "Reporte recuperado" })).toBeInTheDocument();
  expect(screen.getByText("Este reporte pertenece a otro dataset. No describe el dataset activo.")).toBeInTheDocument();
  expect(screen.getByText("Dataset del reporte: other-dataset")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Generar reporte" })).toBeEnabled();
  expect(screen.queryByRole("button", { name: "Volver a generar" })).not.toBeInTheDocument();
});

test("a failed regeneration labels the retained report as previous", async () => {
  let count = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url.endsWith("/intake") ? json(intakeFixture)
    : url.includes("/preview?") ? json(intakePreviewFixture)
      : ++count === 1 ? json(successReport) : json({ detail: "Service unavailable" }, 503)));
  const user = await openInsightsAfterIntake();
  await user.click(screen.getByRole("button", { name: "Generar reporte" }));
  await screen.findByText("Estado: Completado");
  await user.click(screen.getByRole("button", { name: "Volver a generar" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Service unavailable");
  expect(screen.getByRole("status")).toHaveTextContent("La regeneración falló. Se muestra el reporte anterior, no un resultado nuevo.");
  expect(screen.getByText("Ejecución: run-1")).toBeInTheDocument();
});

test("a recovered legacy report explains that dataset identity is unavailable", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(successReport)));
  renderReport();
  await userEvent.type(screen.getByLabelText("ID de ejecución"), "run-1");
  await userEvent.click(screen.getByRole("button", { name: "Consultar" }));
  expect(await screen.findByText("Consulta histórica: no hay un dataset activo asociado.")).toBeInTheDocument();
  expect(screen.getByText("Dataset del reporte: Identidad no disponible en este reporte histórico")).toBeInTheDocument();
});
