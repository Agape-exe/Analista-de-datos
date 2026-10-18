import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "./App";
import { intakeFixture } from "../test/fixture";

const json = (value: unknown) => new Response(JSON.stringify(value), { status: 200 });
const result = { run_id: "run-1", status: "SUCCESS", dataset_profile: intakeFixture.profile,
  metrics: {}, stage_statuses: {}, insights: [], evidence: [], analysis_results: [], errors: [], warnings: [] };
function deferred() {
  let resolve!: (value: Response) => void;
  const promise = new Promise<Response>((done) => { resolve = done; });
  return { promise, resolve };
}
function setup() {
  render(<MemoryRouter><App /></MemoryRouter>);
  return userEvent.setup();
}
async function upload(user: ReturnType<typeof userEvent.setup>) {
  await user.upload(screen.getByLabelText("Archivo del dataset", { exact: true }), new File(["x,y\n1,2"], "sales.csv"));
}
async function load(user: ReturnType<typeof userEvent.setup>) {
  await upload(user);
  await user.click(screen.getByRole("button", { name: "Comprender dataset" }));
  await screen.findByRole("heading", { name: "Resumen del dataset" });
  await user.click(screen.getByRole("link", { name: "Hallazgos" }));
}
afterEach(() => vi.unstubAllGlobals());

test("draft files and reading options survive navigation and the home logo", async () => {
  const user = setup();
  await upload(user);
  await user.upload(screen.getByLabelText("Archivo del diccionario de datos"), new File(['{"entries":[]}'], "dictionary.json"));
  await user.selectOptions(screen.getByLabelText("Separador CSV"), ";");
  await user.selectOptions(screen.getByLabelText("Codificación del archivo"), "cp1252");
  await user.click(screen.getByRole("link", { name: "Hallazgos" }));
  await user.click(screen.getByRole("link", { name: "Inicio de Analista de Datos IA" }));
  expect(screen.getByLabelText("Separador CSV")).toHaveValue(";");
  expect(screen.getByLabelText("Codificación del archivo")).toHaveValue("cp1252");
  expect(screen.getByRole("heading", { name: "sales.csv" })).toBeInTheDocument();
  expect(screen.getByText("dictionary.json")).toBeInTheDocument();
});

test("report question and an unsubmitted recovery ID survive tab changes and reset clears both", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(intakeFixture)));
  const user = setup();
  await load(user);
  await user.type(screen.getByLabelText("Pregunta del análisis"), "What varies?");
  await user.type(screen.getByLabelText("ID de ejecución"), "saved-id");
  await user.click(screen.getByRole("link", { name: "Dataset" }));
  await user.click(screen.getByRole("link", { name: "Hallazgos" }));
  expect(screen.getByLabelText("Pregunta del análisis")).toHaveValue("What varies?");
  expect(screen.getByLabelText("ID de ejecución")).toHaveValue("saved-id");
  await user.click(screen.getAllByRole("button", { name: "Nuevo análisis" })[0]);
  await user.click(screen.getByRole("link", { name: "Hallazgos" }));
  expect(screen.getByLabelText("ID de ejecución")).toHaveValue("");
  expect(screen.queryByLabelText("Pregunta del análisis")).not.toBeInTheDocument();
});

test("completing intake after leaving its page does not redirect the user", async () => {
  const pending = deferred();
  vi.stubGlobal("fetch", vi.fn(() => pending.promise));
  const user = setup();
  await upload(user);
  await user.click(screen.getByRole("button", { name: "Comprender dataset" }));
  await user.click(screen.getByRole("link", { name: "Hallazgos" }));
  await act(async () => pending.resolve(json(intakeFixture)));
  expect(screen.getByRole("heading", { name: "Hallazgos y evidencia" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Generar reporte" })).toBeEnabled();
});

test("cancelled intake preserves the draft and its late response cannot replace a retry", async () => {
  const old = deferred(), next = deferred();
  let calls = 0;
  let signal: AbortSignal | undefined;
  const fetchMock = vi.fn((_url: string, init: RequestInit) => {
    if (++calls === 1) { signal = init.signal as AbortSignal; return old.promise; }
    return next.promise;
  });
  vi.stubGlobal("fetch", fetchMock);
  const user = setup();
  await upload(user);
  await user.selectOptions(screen.getByLabelText("Separador CSV"), "|");
  await user.click(screen.getByRole("button", { name: "Comprender dataset" }));
  await user.click(screen.getByRole("button", { name: "Cancelar espera de carga" }));
  expect(signal?.aborted).toBe(true);
  expect(screen.getByRole("status")).toHaveTextContent("Los archivos y opciones se conservan");
  expect(screen.getByLabelText("Separador CSV")).toHaveValue("|");
  await user.click(screen.getByRole("button", { name: "Comprender dataset" }));
  expect(fetchMock).toHaveBeenCalledTimes(2);
  await act(async () => old.resolve(json(intakeFixture)));
  expect(screen.getByRole("button", { name: "Procesando…" })).toBeDisabled();
  await act(async () => next.resolve(json({ ...intakeFixture, filename: "retry.csv" })));
  await screen.findByRole("heading", { name: "Resumen del dataset" });
  expect(screen.getByRole("link", { name: "Explorar asociaciones" })).toBeInTheDocument();
});

test("new analysis stays available during intake and clears native file inputs too", async () => {
  const pending = deferred();
  let signal: AbortSignal | undefined;
  vi.stubGlobal("fetch", vi.fn((_url: string, init: RequestInit) => { signal = init.signal as AbortSignal; return pending.promise; }));
  const user = setup();
  await upload(user);
  await user.click(screen.getByRole("button", { name: "Comprender dataset" }));
  const reset = screen.getAllByRole("button", { name: "Nuevo análisis" })[0];
  expect(reset).toBeEnabled();
  await user.click(reset);
  expect(signal?.aborted).toBe(true);
  expect((screen.getByLabelText("Archivo del dataset") as HTMLInputElement).files).toHaveLength(0);
  await act(async () => pending.resolve(json(intakeFixture)));
  expect(screen.getByRole("button", { name: "Comprender dataset" })).toBeDisabled();
  expect(screen.getByRole("heading", { name: "Analiza tus datos" })).toBeInTheDocument();
});

test("report cancellation marks the retained result and ignores its later response", async () => {
  const pending = deferred();
  let analyses = 0;
  let signal: AbortSignal | undefined;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init: RequestInit) => {
    if (url.endsWith("/intake")) return json(intakeFixture);
    if (++analyses === 1) return json(result);
    signal = init.signal as AbortSignal;
    return pending.promise;
  }));
  const user = setup();
  await load(user);
  await user.type(screen.getByLabelText("Pregunta del análisis"), "Keep question");
  await user.click(screen.getByRole("button", { name: "Generar reporte" }));
  await screen.findByText("Ejecución: run-1");
  await user.click(screen.getByRole("button", { name: "Volver a generar" }));
  await user.click(screen.getByRole("button", { name: "Cancelar espera del reporte" }));
  expect(signal?.aborted).toBe(true);
  expect(screen.getByRole("status")).toHaveTextContent("Se muestra el reporte anterior");
  await act(async () => pending.resolve(json({ ...result, run_id: "late" })));
  expect(screen.getByText("Ejecución: run-1")).toBeInTheDocument();
  await user.click(screen.getByRole("link", { name: "Dataset" }));
  await user.click(screen.getByRole("link", { name: "Hallazgos" }));
  expect(screen.getByLabelText("Pregunta del análisis")).toHaveValue("Keep question");
  expect(screen.getByRole("status")).toHaveTextContent("Se canceló la espera");
});

test("a cancelled recovery preserves its query but cannot show the late report", async () => {
  const pending = deferred();
  vi.stubGlobal("fetch", vi.fn(() => pending.promise));
  const user = setup();
  await user.click(screen.getByRole("link", { name: "Hallazgos" }));
  await user.type(screen.getByLabelText("ID de ejecución"), "run-1");
  await user.click(screen.getByRole("button", { name: "Consultar" }));
  await user.click(screen.getByRole("button", { name: "Cancelar espera del reporte" }));
  await act(async () => pending.resolve(json(result)));
  expect(screen.getByRole("status")).toHaveTextContent("La ejecución en el servidor puede continuar");
  expect(screen.queryByText("Ejecución: run-1")).not.toBeInTheDocument();
  expect(screen.getByLabelText("ID de ejecución")).toHaveValue("run-1");
});
