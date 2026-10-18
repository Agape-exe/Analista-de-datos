import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../../app/App";
import { intakeFixture } from "../../test/fixture";
import { IntakeProvider, useIntake } from "../data-intake/IntakeProvider";
import { ReportProvider, useReport } from "../reports/ReportProvider";
import { SummaryPage } from "./SummaryPage";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const report = (datasetId: string | null = "test-dataset", status = "SUCCESS") => ({
  run_id: "summary-run", status, insights: [], evidence: [], metrics: { total_response_time: null, tool_calls: 0 },
  ...(datasetId ? { dataset_profile: { ...intakeFixture.profile, dataset_id: datasetId } } : {}),
});
function Controls() {
  const intake = useIntake(), reports = useReport();
  return <>
    <input aria-label="Fixture file" type="file" onChange={(event) => intake.updateDraft({ file: event.target.files?.[0] ?? null })} />
    <button onClick={() => void intake.analyze()}>load fixture</button>
    <button onClick={intake.reset}>reset fixture</button>
    <button onClick={() => void reports.recover("summary-run")}>recover fixture</button>
    <button onClick={reports.cancel}>cancel fixture</button>
    <button onClick={intake.cancel}>cancel intake</button>
  </>;
}
function setup() {
  render(<MemoryRouter><IntakeProvider><ReportProvider><Controls /><SummaryPage /></ReportProvider></IntakeProvider></MemoryRouter>);
  return userEvent.setup();
}
async function action(user: ReturnType<typeof userEvent.setup>, name: string) {
  if (name === "load fixture") await user.upload(screen.getByLabelText("Fixture file"), new File(["x\n1"], "fixture.csv"));
  await user.click(screen.getByRole("button", { name }));
}
const analysis = () => within(screen.getByRole("region", { name: "Indicadores del análisis compatible" }));
afterEach(() => vi.unstubAllGlobals());

test("empty summary makes no requests; dataset indicators use intake without additional tools", async () => {
  const fetch = vi.fn(async () => json(intakeFixture));
  vi.stubGlobal("fetch", fetch);
  const user = setup();
  expect(screen.getByRole("heading", { name: "Sin dataset activo" })).toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
  await action(user, "load fixture");
  expect(screen.getByRole("heading", { name: "Dataset activo" })).toBeInTheDocument();
  expect(screen.getByText("Puntaje de calidad")).toBeInTheDocument();
  expect(analysis().getAllByText("Sin medición disponible")).toHaveLength(4);
  expect(fetch).toHaveBeenCalledOnce();
});

test("completed compatible reports distinguish measured zero from missing metrics", async () => {
  const fetch = vi.fn(async (url: string) => json(url.endsWith("/intake") ? intakeFixture : report()));
  vi.stubGlobal("fetch", fetch);
  const user = setup();
  await action(user, "load fixture");
  await action(user, "recover fixture");
  expect(screen.getByRole("heading", { name: "Reporte compatible disponible" })).toBeInTheDocument();
  expect(analysis().getAllByText("0", { exact: true })).toHaveLength(3);
  expect(analysis().getAllByText("Sin medición disponible")).toHaveLength(1);
  expect(fetch).toHaveBeenCalledTimes(2);
  await action(user, "reset fixture");
  expect(screen.getByRole("heading", { name: "Sin dataset activo" })).toBeInTheDocument();
  expect(screen.queryByText(/summary-run/)).not.toBeInTheDocument();
});

test.each(["other-dataset", null])("recovered report %s never contributes active indicators", async (id) => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => json(url.endsWith("/intake") ? intakeFixture : report(id))));
  const user = setup();
  await action(user, "load fixture");
  await action(user, "recover fixture");
  expect(screen.getByRole("heading", { name: "Reporte recuperado" })).toBeInTheDocument();
  expect(screen.getByText(id ? /Pertenece a otro dataset/ : /No se puede verificar/)).toBeInTheDocument();
  expect(analysis().getAllByText("Sin medición disponible")).toHaveLength(4);
});

test("historical recovery without an active dataset remains separate and resets", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(report())));
  const user = setup();
  await action(user, "recover fixture");
  expect(screen.getByText("Consulta histórica sin dataset activo.")).toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "Indicadores del análisis compatible" })).not.toBeInTheDocument();
  await action(user, "reset fixture");
  expect(screen.queryByText(/summary-run/)).not.toBeInTheDocument();
});

test.each(["FAILED", "SKIPPED"])("%s reports cannot supply completed analysis indicators", async (status) => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => json(url.endsWith("/intake") ? intakeFixture : report("test-dataset", status))));
  const user = setup();
  await action(user, "load fixture");
  await action(user, "recover fixture");
  expect(analysis().getAllByText("Sin medición disponible")).toHaveLength(4);
  expect(screen.getByText(status === "FAILED" ? /El análisis falló/ : /El análisis tiene etapas pendientes/)).toBeInTheDocument();
});

test.each(["error", "cancel"])("pending and %s requests remove old indicators and retain explicit previous context", async (outcome) => {
  let finish!: (response: Response) => void;
  let calls = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url.endsWith("/intake") ? json(intakeFixture)
    : ++calls === 1 ? json(report()) : new Promise<Response>((resolve) => { finish = resolve; })));
  const user = setup();
  await action(user, "load fixture");
  await action(user, "recover fixture");
  await action(user, "recover fixture");
  expect(screen.getByText(/Solicitud de reporte pendiente/)).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Reporte anterior" })).toBeInTheDocument();
  expect(analysis().getAllByText("Sin medición disponible")).toHaveLength(4);
  if (outcome === "error") {
    await act(async () => finish(json({ detail: "Service unavailable" }, 503)));
    expect(screen.getByRole("alert")).toHaveTextContent("Service unavailable");
  } else {
    await action(user, "cancel fixture");
    expect(screen.getByRole("status")).toHaveTextContent("Se canceló la espera");
    await act(async () => finish(json(report())));
  }
  expect(analysis().getAllByText("Sin medición disponible")).toHaveLength(4);
});

test("summary reflects pending, cancelled and failed intake without fabricated metrics", async () => {
  let finish!: (response: Response) => void;
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((resolve) => { finish = resolve; })));
  const user = setup();
  await action(user, "load fixture");
  expect(screen.getByRole("status")).toHaveTextContent("Carga del dataset pendiente");
  await action(user, "cancel intake");
  expect(screen.getByRole("status")).toHaveTextContent("Se canceló la espera de carga");
  await act(async () => finish(json(intakeFixture)));
  expect(screen.getByRole("heading", { name: "Sin dataset activo" })).toBeInTheDocument();
  await action(user, "load fixture");
  await act(async () => finish(json({ detail: "Invalid file" }, 400)));
  expect(screen.getByRole("alert")).toHaveTextContent("Invalid file");
});

test("sidebar summary navigation preserves intake and Nuevo análisis resets at root", async () => {
  const fetch = vi.fn(async () => json(intakeFixture));
  vi.stubGlobal("fetch", fetch);
  const user = userEvent.setup();
  render(<MemoryRouter><App /></MemoryRouter>);
  await user.upload(screen.getByLabelText("Archivo del dataset"), new File(["x\n1"], "sales.csv"));
  await action(user, "Comprender dataset");
  await user.click(screen.getByRole("link", { name: "Resumen" }));
  expect(screen.getByRole("link", { name: "Resumen" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("heading", { name: "Dataset activo" })).toBeInTheDocument();
  await user.click(screen.getByRole("link", { name: "Ver diccionario" }));
  await user.click(screen.getByRole("link", { name: "Resumen" }));
  expect(fetch).toHaveBeenCalledOnce();
  await user.click(screen.getAllByRole("button", { name: "Nuevo análisis" })[0]);
  expect(screen.getByRole("button", { name: "Comprender dataset" })).toBeDisabled();
  await user.click(screen.getByRole("link", { name: "Resumen" }));
  expect(screen.getByRole("heading", { name: "Sin dataset activo" })).toBeInTheDocument();
});
