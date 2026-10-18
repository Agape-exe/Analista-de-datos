import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../../app/App";
import { intakeFixture } from "../../test/fixture";
import { intakePreviewFixture } from "../../test/preview-fixture";
import { traceFixture } from "../../test/trace-fixture";

const json = (value: unknown) => new Response(JSON.stringify(value), { status: 200 });
afterEach(() => vi.unstubAllGlobals());
function setup(path = "/trace") {
  render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
  return userEvent.setup();
}
async function recover(user: ReturnType<typeof userEvent.setup>, id = traceFixture.run_id) {
  await user.click(screen.getByRole("link", { name: "Hallazgos" }));
  await user.clear(screen.getByLabelText("ID de ejecución"));
  await user.type(screen.getByLabelText("ID de ejecución"), id);
  await user.click(screen.getByRole("button", { name: "Consultar" }));
  await user.click(screen.getByRole("link", { name: "Traza" }));
}
const events = () => within(screen.getByRole("region", { name: "Entradas de la traza" }));
const stages = () => within(screen.getByRole("region", { name: "Información de etapas" }));

test("direct route and menu show no report and do not fetch", async () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  const user = setup();
  expect(screen.getByRole("heading", { name: "Traza de ejecución" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Sin reporte disponible" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Traza" })).toHaveAttribute("aria-current", "page");
  await user.click(screen.getByRole("link", { name: "Métricas" }));
  await user.click(screen.getByRole("link", { name: "Traza" }));
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
});

test("real call shapes keep received order, raw seconds, zero and stage results separate", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(traceFixture)));
  const user = setup();
  await recover(user);
  const rows = events().getAllByRole("row");
  expect(rows).toHaveLength(4);
  expect(rows[1]).toHaveTextContent("1llmNo disponibleSUCCESS · Completado0 s");
  expect(rows[2]).toHaveTextContent("2toolfixture_toolSKIPPED · Omitido0.125 s");
  expect(rows[3]).toHaveTextContent("3toolfixture_toolFAILED · Fallido0.000001 s");
  expect(stages().getByRole("row", { name: "Comprensión de datos (DataUnderstanding) SUCCESS · Completado 0 s" })).toBeInTheDocument();
  expect(stages().getByRole("row", { name: "Planificación (Planner) SKIPPED · Omitido 0.25 s" })).toBeInTheDocument();
  expect(stages().getByRole("row", { name: "Análisis (Analysis) FAILED · Fallido 1.5 s" })).toBeInTheDocument();
  expect(screen.getByText("Fixture failure")).toBeInTheDocument();
  expect(screen.getByText("Fixture warning")).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(screen.getByText(/el reporte se cargó correctamente/)).toBeInTheDocument();
});

test.each([
  { label: "missing", trace: undefined }, { label: "empty", trace: [] },
])("historical $label trace does not manufacture stage events", async ({ trace }) => {
  vi.stubGlobal("fetch", vi.fn(async () => json({ run_id: traceFixture.run_id, status: "SUCCESS", execution_trace: trace })));
  const user = setup();
  await recover(user);
  expect(events().getByText(trace ? /Traza vacía/ : /no proporciona execution_trace/)).toBeInTheDocument();
  expect(stages().getByText("Sin información de etapas disponible.")).toBeInTheDocument();
  expect(screen.getByText(/Dataset del reporte: Identidad no disponible/)).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

test("partial maps use their union; omitted and null durations never become zero", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json({ ...traceFixture, execution_trace: [],
    stage_statuses: { Analysis: "FAILED", Planner: "SKIPPED", Insight: "SUCCESS" },
    stage_durations: { Analysis: null, Insight: 0, FutureStage: 0.4 } })));
  const user = setup();
  await recover(user);
  expect(events().queryByRole("table")).not.toBeInTheDocument();
  expect(stages().getByRole("row", { name: "Análisis (Analysis) FAILED · Fallido No disponible" })).toBeInTheDocument();
  expect(stages().getByRole("row", { name: "Planificación (Planner) SKIPPED · Omitido No disponible" })).toBeInTheDocument();
  expect(stages().getByRole("row", { name: "Hallazgos (Insight) SUCCESS · Completado 0 s" })).toBeInTheDocument();
  expect(stages().getByRole("row", { name: "FutureStage (FutureStage) No disponible 0.4 s" })).toBeInTheDocument();
});

test("open JSON trace details and unknown states render literally without assuming stage linkage", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json({ ...traceFixture,
    stage_statuses: { Future: "NEW_STATE" }, stage_durations: {},
    execution_trace: [{ kind: "future", status: "NEW_STATE", duration_seconds: null,
      reason: "Provided reason", extra: { measured: false } }, { kind: "llm" }] })));
  const user = setup();
  await recover(user);
  expect(events().getByText("Provided reason")).toBeInTheDocument();
  expect(events().getByText('{"measured":false}')).toBeInTheDocument();
  expect(events().getByRole("row", { name: /1 future No disponible NEW_STATE No disponible/ })).toBeInTheDocument();
  expect(events().getByRole("row", { name: /2 llm No disponible No disponible No disponible/ })).toBeInTheDocument();
  expect(stages().getByText("NEW_STATE")).toBeInTheDocument();
});

test("trace-only report has no invented stages", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json({ ...traceFixture, stage_statuses: undefined, stage_durations: undefined })));
  const user = setup();
  await recover(user);
  expect(events().getAllByRole("row")).toHaveLength(4);
  expect(stages().queryByRole("table")).not.toBeInTheDocument();
});

test("fetch failure without a report is distinct from a FAILED stage", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "Unavailable" }), { status: 503 })));
  const user = setup();
  await recover(user);
  expect(screen.getByRole("alert")).toHaveTextContent("La solicitud de reporte falló: Unavailable");
  expect(screen.getByRole("heading", { name: "Sin reporte disponible" })).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

test("pending recovery updates Trace after navigation; replacing the report replaces all three fields", async () => {
  let resolve!: (value: Response) => void;
  let calls = 0;
  vi.stubGlobal("fetch", vi.fn(() => ++calls === 1 ? new Promise<Response>((done) => { resolve = done; })
    : Promise.resolve(json({ run_id: "next-run", status: "SUCCESS", stage_durations: { New: 9 } }))));
  const user = setup();
  await recover(user);
  expect(screen.getByRole("status")).toHaveTextContent("Solicitud de reporte pendiente");
  await act(async () => resolve(json(traceFixture)));
  expect(events().getAllByRole("row")).toHaveLength(4);
  for (const page of ["Métricas", "Hallazgos", "Traza"]) {
    await user.click(screen.getByRole("link", { name: page }));
    expect(screen.getByText(`Ejecución: ${traceFixture.run_id}`)).toBeInTheDocument();
    expect(screen.getByText("Dataset del reporte: test-dataset")).toBeInTheDocument();
  }
  await recover(user, "next-run");
  expect(screen.queryByText(`Ejecución: ${traceFixture.run_id}`)).not.toBeInTheDocument();
  expect(events().queryByRole("table")).not.toBeInTheDocument();
  expect(stages().getByRole("row", { name: "New (New) No disponible 9 s" })).toBeInTheDocument();
  expect(stages().queryByText(/Analysis/)).not.toBeInTheDocument();
  expect(screen.getByText(/Dataset del reporte: Identidad no disponible/)).toBeInTheDocument();
});

test("failed replacement labels the retained report and keeps its trace coherent", async () => {
  let calls = 0;
  vi.stubGlobal("fetch", vi.fn(async () => ++calls === 1 ? json(traceFixture)
    : new Response(JSON.stringify({ detail: "Missing report" }), { status: 404 })));
  const user = setup();
  await recover(user);
  await recover(user, "missing");
  expect(screen.getByRole("alert")).toHaveTextContent("Missing report");
  expect(screen.getByRole("status")).toHaveTextContent("reporte anterior, no el solicitado");
  expect(events().getAllByRole("row")).toHaveLength(4);
  expect(screen.getByText(`Ejecución: ${traceFixture.run_id}`)).toBeInTheDocument();
});

test("New Analysis clears a loaded trace and rejects a late response even if fetch ignores abort", async () => {
  let resolve!: (value: Response) => void;
  let signal: AbortSignal | undefined;
  let calls = 0;
  vi.stubGlobal("fetch", vi.fn((_url: string, init: RequestInit) => {
    if (++calls === 1) return Promise.resolve(json(traceFixture));
    signal = init.signal as AbortSignal;
    return new Promise<Response>((done) => { resolve = done; });
  }));
  const user = setup();
  await recover(user);
  await recover(user, "late-run");
  expect(events().getAllByRole("row")).toHaveLength(4);
  await user.click(screen.getAllByRole("button", { name: "Nuevo análisis" })[0]);
  await user.click(screen.getByRole("link", { name: "Traza" }));
  expect(signal?.aborted).toBe(true);
  await act(async () => resolve(json({ ...traceFixture, run_id: "late-run" })));
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Sin reporte disponible" })).toBeInTheDocument();
});

test("active dataset identity survives all three routes and is separated from another report's dataset", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url.endsWith("/intake")) return json(intakeFixture);
    if (url.includes("/preview?")) return json(intakePreviewFixture);
    return json(url.endsWith("other-run") ? { ...traceFixture, run_id: "other-run",
      dataset_profile: { ...intakeFixture.profile, dataset_id: "other-dataset" }, execution_trace: [] } : traceFixture);
  }));
  const user = setup("/");
  await user.upload(screen.getByLabelText("Archivo del dataset", { exact: true }), new File(["x\n1"], "active.csv"));
  await user.click(screen.getByRole("button", { name: "Comprender dataset" }));
  await screen.findByRole("heading", { name: "Resumen del dataset" });
  await recover(user);
  for (const page of ["Métricas", "Hallazgos", "Traza"]) {
    await user.click(screen.getByRole("link", { name: page }));
    expect(screen.getByText("Este reporte corresponde al dataset activo.")).toBeInTheDocument();
  }
  await recover(user, "other-run");
  expect(screen.getByText("Dataset del reporte: other-dataset")).toBeInTheDocument();
  expect(screen.getByText("sales.csv · ID: test-dataset")).toBeInTheDocument();
  expect(screen.getByText("Este reporte pertenece a otro dataset. No describe el dataset activo.")).toBeInTheDocument();
  expect(events().queryByRole("table")).not.toBeInTheDocument();
});
