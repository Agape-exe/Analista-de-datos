import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../../app/App";
import { intakeFixture } from "../../test/fixture";
import { intakePreviewFixture } from "../../test/preview-fixture";
import { reportFixture } from "../../test/report-fixture";
import type { AnalysisReport } from "../../lib/api-client";

const json = (value: unknown) => new Response(JSON.stringify(value), { status: 200 });
afterEach(() => vi.unstubAllGlobals());
function setup(path = "/metrics") {
  render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
  return userEvent.setup();
}
async function recover(user: ReturnType<typeof userEvent.setup>, id = reportFixture.run_id) {
  await user.click(screen.getByRole("link", { name: "Hallazgos" }));
  await user.clear(screen.getByLabelText("ID de ejecución"));
  await user.type(screen.getByLabelText("ID de ejecución"), id);
  await user.click(screen.getByRole("button", { name: "Consultar" }));
}
async function metrics(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("link", { name: "Métricas" }));
}
function metricRow(name: string) {
  return within(screen.getByRole("region", { name: "Métricas del reporte" })).getByRole("row", { name });
}

test("direct route and menu show the empty state without fetching or inventing metrics", async () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  const user = setup();
  expect(screen.getByRole("heading", { name: "Métricas del integrante 5" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Sin reporte disponible" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Métricas" })).toHaveAttribute("aria-current", "page");
  await user.click(screen.getByRole("link", { name: "Resumen" }));
  await metrics(user);
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
});

test.each(["SUCCESS", "SKIPPED", "FAILED"] as const)("%s preserves partial measurements, causes and provenance", async (status) => {
  const report: AnalysisReport = { ...reportFixture, status,
    stage_statuses: { Insight: status }, warnings: ["No upstream timing supplied",
      ...(status === "SKIPPED" ? ["No validated evidence available for insights"] : [])],
    errors: status === "FAILED" ? ["Insight failed"] : [],
  };
  const fetch = vi.fn(async () => json(report));
  vi.stubGlobal("fetch", fetch);
  const user = setup();
  await recover(user);
  await metrics(user);
  expect(screen.getByRole("heading", { name: new RegExp(`Estado: ${status}`) })).toBeInTheDocument();
  expect(metricRow("Llamadas al LLM 0 llamadas")).toBeInTheDocument();
  expect(metricRow("Precisión No disponible 0–1")).toBeInTheDocument();
  expect(metricRow("Exhaustividad (recall) No disponible 0–1")).toBeInTheDocument();
  expect(metricRow("Tiempo total de respuesta (s) 0.125 s")).toBeInTheDocument();
  expect(screen.getByText("Alcance de ejecución: finalization_only")).toBeInTheDocument();
  expect(screen.getByText("No upstream timing supplied")).toBeInTheDocument();
  expect(screen.getByText("Dataset del reporte: test-dataset")).toBeInTheDocument();
  expect(screen.getByText("Consulta histórica: no hay un dataset activo asociado.")).toBeInTheDocument();
  if (status === "FAILED") expect(screen.getByRole("alert")).toHaveTextContent("Insight failed");
  if (status === "SKIPPED") expect(screen.getByText("No validated evidence available for insights")).toBeInTheDocument();
  await user.click(screen.getByRole("link", { name: "Resumen" }));
  await metrics(user);
  expect(metricRow("Llamadas al LLM 0 llamadas")).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(1);
});

test("historical unknown identity and absent metrics never borrow active dataset identity", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json({ ...reportFixture, dataset_profile: null, metrics: undefined, configuration: {} })));
  const user = setup();
  await recover(user);
  await metrics(user);
  expect(screen.getByText(/Dataset del reporte: Identidad no disponible/)).toBeInTheDocument();
  expect(metricRow("Llamadas al LLM No disponible llamadas")).toBeInTheDocument();
  expect(screen.getByText("Alcance de ejecución: No disponible")).toBeInTheDocument();
});

test("partial stage maps preserve duration-only stages and absent states", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json({ ...reportFixture,
    stage_statuses: { Planner: "SKIPPED" },
    stage_durations: { Insight: 0, Analysis: 0.25 },
  })));
  const user = setup();
  await recover(user);
  await metrics(user);
  expect(screen.getByRole("row", { name: "Planificación SKIPPED · Omitido No disponible" })).toBeInTheDocument();
  expect(screen.getByRole("row", { name: "Hallazgos No disponible 0" })).toBeInTheDocument();
  expect(screen.getByRole("row", { name: "Análisis No disponible 0.25" })).toBeInTheDocument();
});

test("dataset replacement, navigation and New Analysis never attribute old metrics to the new dataset", async () => {
  let intakeCalls = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url.endsWith("/intake")) return json({ ...intakeFixture, filename: `${++intakeCalls}.csv`,
      profile: { ...intakeFixture.profile, dataset_id: `dataset-${intakeCalls}` } });
    if (url.includes("/preview?")) return json(intakePreviewFixture);
    return json({ ...reportFixture, run_id: `run-${intakeCalls}`,
      dataset_profile: { ...intakeFixture.profile, dataset_id: `dataset-${intakeCalls}` },
      metrics: { tool_calls: intakeCalls } });
  }));
  const user = setup("/");
  for (const id of [1, 2]) {
    await user.upload(screen.getByLabelText("Archivo del dataset", { exact: true }), new File(["x\n1"], `${id}.csv`));
    await user.click(screen.getByRole("button", { name: "Comprender dataset" }));
    await screen.findByRole("heading", { name: "Resumen del dataset" });
    await metrics(user);
    expect(screen.getByRole("heading", { name: "Sin reporte disponible" })).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Hallazgos" }));
    await user.click(screen.getByRole("button", { name: "Generar reporte" }));
    await screen.findByText(`Ejecución: run-${id}`);
    await metrics(user);
    expect(screen.getByText(`Dataset del reporte: dataset-${id}`)).toBeInTheDocument();
    expect(screen.getByText("Este reporte corresponde al dataset activo.")).toBeInTheDocument();
    expect(metricRow(`Llamadas a herramientas ${id} llamadas`)).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Resumen" }));
    await metrics(user);
    expect(metricRow(`Llamadas a herramientas ${id} llamadas`)).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "Nuevo análisis" })[0]);
    await metrics(user);
    expect(screen.queryByText(`Ejecución: run-${id}`)).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Sin reporte disponible" })).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Inicio de Analista de Datos IA" }));
  }
});

test("pending recovery survives navigation; reset rejects a late response even if fetch ignores abort", async () => {
  let resolve!: (value: Response) => void;
  const pending = new Promise<Response>((done) => { resolve = done; });
  let signal: AbortSignal | undefined;
  vi.stubGlobal("fetch", vi.fn((_url: string, init: RequestInit) => { signal = init.signal as AbortSignal; return pending; }));
  const user = setup();
  await recover(user);
  await metrics(user);
  expect(screen.getByRole("status")).toHaveTextContent("Solicitud de reporte pendiente");
  await user.click(screen.getAllByRole("button", { name: "Nuevo análisis" })[0]);
  await metrics(user);
  expect(signal?.aborted).toBe(true);
  await act(async () => resolve(json(reportFixture)));
  expect(screen.getByRole("heading", { name: "Sin reporte disponible" })).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

test("a later failed request labels preserved metrics as previous", async () => {
  let calls = 0;
  vi.stubGlobal("fetch", vi.fn(async () => ++calls === 1 ? json(reportFixture)
    : new Response(JSON.stringify({ detail: "Service unavailable" }), { status: 503 })));
  const user = setup();
  await recover(user);
  await recover(user, "missing");
  await metrics(user);
  expect(screen.getByRole("alert")).toHaveTextContent("Service unavailable");
  expect(screen.getByRole("status")).toHaveTextContent("reporte anterior, no el solicitado");
  expect(screen.getByText(`Ejecución: ${reportFixture.run_id}`)).toBeInTheDocument();
});

test("recovering another dataset replaces displayed metrics and explicitly separates its identity", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url.endsWith("/intake")) return json(intakeFixture);
    if (url.includes("/preview?")) return json(intakePreviewFixture);
    return json(url.endsWith("other-run") ? { ...reportFixture, run_id: "other-run",
      dataset_profile: { ...intakeFixture.profile, dataset_id: "other-dataset" }, metrics: { llm_calls: 7 } } : reportFixture);
  }));
  const user = setup("/");
  await user.upload(screen.getByLabelText("Archivo del dataset", { exact: true }), new File(["x\n1"], "active.csv"));
  await user.click(screen.getByRole("button", { name: "Comprender dataset" }));
  await screen.findByRole("heading", { name: "Resumen del dataset" });
  await recover(user);
  await metrics(user);
  expect(metricRow("Llamadas al LLM 0 llamadas")).toBeInTheDocument();
  await recover(user, "other-run");
  await metrics(user);
  expect(metricRow("Llamadas al LLM 7 llamadas")).toBeInTheDocument();
  expect(screen.getByText("Este reporte pertenece a otro dataset. No describe el dataset activo.")).toBeInTheDocument();
  expect(screen.getByText("Dataset del reporte: other-dataset")).toBeInTheDocument();
  expect(screen.getByText("sales.csv · ID: test-dataset")).toBeInTheDocument();
  expect(screen.queryByText(`Ejecución: ${reportFixture.run_id}`)).not.toBeInTheDocument();
});

test("recovery finishing on Metrics updates the shared report without route changes", async () => {
  let resolve!: (value: Response) => void;
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((done) => { resolve = done; })));
  const user = setup();
  await recover(user);
  await metrics(user);
  expect(screen.getByRole("status")).toHaveTextContent("Solicitud de reporte pendiente");
  await act(async () => resolve(json(reportFixture)));
  expect(metricRow("Llamadas al LLM 0 llamadas")).toBeInTheDocument();
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  await user.click(screen.getByRole("link", { name: "Hallazgos" }));
  expect(screen.getByLabelText("ID de ejecución")).toHaveValue(reportFixture.run_id);
});
