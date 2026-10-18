import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import type { AnalysisResult } from "../../types/exploration";
import { toolFixtures } from "../../test/fixture";
import { ColumnExplorer } from "./ColumnExplorer";
import { OutlierExamples } from "./OutlierExamples";
import type { useTool } from "./useTool";

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const legacyOutliers = toolFixtures.outliers as AnalysisResult;

function result(column = "amount", rows = [{ row_index: 3, value: 500 }, { row_index: 9, value: 500 }, { row_index: 0, value: -400 }]): AnalysisResult {
  return { ...legacyOutliers, variables: [column], result: {
    [column]: { count: 40, iqr: { count: rows.length, percentage: 7.5, lower_fence: -30, upper_fence: 30,
      examples: rows.map((row) => row.value), example_rows: rows }, mad: { count: 3, percentage: 7.5 } },
  } };
}
function panel(override: Partial<ReturnType<typeof useTool>> = {}, data = result()) {
  return <MemoryRouter><OutlierExamples column="amount" totalRows={60}
    tool={{ data, loading: false, stale: false, error: undefined, retry: vi.fn(), ...override }} /></MemoryRouter>;
}
const response = (payload: unknown, status = 200) => new Response(JSON.stringify(payload), { status });

it("muestra número de registro basado en cero más uno, valor y método sin deduplicar", () => {
  const data = result(), before = JSON.stringify(data); render(panel({}, data));
  expect(screen.getAllByRole("rowheader").map((cell) => cell.textContent)).toEqual(["Registro 4", "Registro 10", "Registro 1"]);
  expect(screen.getAllByRole("cell", { name: "500" })).toHaveLength(2);
  expect(screen.getByRole("cell", { name: "-400" })).toBeInTheDocument();
  expect(screen.getByText(/puede ser una observación válida/)).toBeInTheDocument();
  expect(screen.getByText(/No es un identificador de negocio/)).toBeInTheDocument();
  expect(JSON.stringify(data)).toBe(before);
});

it("una respuesta anterior sin example_rows no produce referencias inferidas", () => {
  render(panel({}, { ...legacyOutliers, variables: ["amount"] }));
  expect(screen.getByText(/no incluye posiciones originales/)).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

it("distingue cero atípicos de ejemplos desactivados", () => {
  const view = render(panel({}, result("amount", [])));
  expect(screen.getByText("No se detectaron valores atípicos IQR.")).toBeInTheDocument();
  view.rerender(panel({}, { ...result(), result: { amount: { iqr: { count: 5, examples: [], example_rows: [] } } } }));
  expect(screen.getByText(/No se devolvieron ejemplos con posición/)).toBeInTheDocument();
});

it.each(["SKIPPED", "FAILED"] as const)("no muestra ejemplos de un resultado %s", (status) => {
  render(panel({}, { ...result(), status }));
  expect(screen.getByRole("status")).toHaveTextContent(status === "SKIPPED" ? "no pudo evaluar" : "falló");
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

it("maneja columna sin suficientes observaciones sin acceder a iqr inexistente", () => {
  render(panel({}, { ...result(), result: { amount: { skipped: "insufficient observations" } } }));
  expect(screen.getByRole("status")).toHaveTextContent("No hay observaciones suficientes");
});

it.each([
  [{ row_index: -1, value: 500 }], [{ row_index: 60, value: 500 }], [{ row_index: 1.5, value: 500 }],
  [{ row_index: 3, value: 500 }, { row_index: 3, value: 500 }],
].map((rows) => ({ rows })))("rechaza posiciones inválidas o duplicadas $rows", ({ rows }) => {
  render(panel({}, result("amount", rows)));
  expect(screen.getByRole("alert")).toHaveTextContent("referencias recibidas no son válidas");
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

it("rechaza referencias inconsistentes con los valores antiguos y otra columna", () => {
  const view = render(panel({}, { ...result(), result: { amount: { iqr: { count: 1, examples: [500], example_rows: [{ row_index: 3, value: 600 }] } } } }));
  expect(screen.getByRole("alert")).toBeInTheDocument();
  view.rerender(panel({}, result("other")));
  expect(screen.getByText(/para la columna actual/)).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

it("no muestra ejemplos obsoletos durante carga y admite ausencia de datos", () => {
  const view = render(panel({ loading: true, stale: true }));
  expect(screen.getByRole("status")).toHaveTextContent("Consultando ejemplos");
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  view.rerender(panel({ data: undefined }));
  expect(screen.getByText(/No hay datos disponibles/)).toBeInTheDocument();
});

it("explica expiración sin mostrar mensajes internos", () => {
  render(panel({ error: { expired: true, message: "/private/file.csv" } }));
  expect(screen.getByRole("alert")).toHaveTextContent("dataset ya no está disponible");
  expect(screen.getByRole("link", { name: "Volver a cargar" })).toHaveAttribute("href", "/");
  expect(screen.queryByText("/private/file.csv")).not.toBeInTheDocument();
});

it("permite reintentar errores de conexión mediante teclado", async () => {
  const retry = vi.fn(), user = userEvent.setup();
  render(panel({ error: { expired: false, message: "secret" }, retry }));
  await user.tab(); expect(screen.getByRole("button", { name: "Reintentar ejemplos" })).toHaveFocus();
  await user.keyboard("{Enter}"); expect(retry).toHaveBeenCalledOnce();
});

it("la región de referencias es accesible por teclado", async () => {
  const user = userEvent.setup(); render(panel()); await user.tab();
  expect(screen.getByRole("region", { name: "Registros de ejemplos IQR" })).toHaveFocus();
});

function explorer(id = "dataset-a") {
  return <MemoryRouter><ColumnExplorer key={id} datasetId={id} totalRows={60} numeric={["amount", "other"]} categorical={[]} /></MemoryRouter>;
}
function mockTools(outlier: (url: string, init: RequestInit) => Promise<Response>) {
  const fetchMock = vi.fn(async (url: string, init: RequestInit) => {
    const tool = url.split("/tools/")[1];
    if (tool === "outliers") return outlier(url, init);
    return response(toolFixtures[tool]);
  });
  vi.stubGlobal("fetch", fetchMock); return fetchMock;
}

it("ColumnExplorer descarta respuesta tardía tras cambiar columna y no pierde la actual", async () => {
  let resolve!: (value: Response) => void;
  const requests: RequestInit[] = [];
  mockTools(async (_url, init) => {
    requests.push(init);
    const column = JSON.parse(String(init.body)).variables[0];
    return column === "amount" ? new Promise<Response>((done) => { resolve = done; }) : response(result("other", [{ row_index: 15, value: 900 }]));
  });
  const user = userEvent.setup(); render(explorer());
  await screen.findByText("Consultando ejemplos IQR…");
  await act(async () => {});
  await user.selectOptions(screen.getByLabelText("Columna"), "other");
  expect(await screen.findByRole("rowheader", { name: "Registro 16" })).toBeInTheDocument();
  expect(requests[0].signal?.aborted).toBe(true);
  await act(async () => resolve(response(result())));
  expect(screen.getByRole("rowheader", { name: "Registro 16" })).toBeInTheDocument();
  expect(screen.queryByRole("rowheader", { name: "Registro 4" })).not.toBeInTheDocument();
});

it("cambio de dataset reinicia columna y oculta ejemplos anteriores", async () => {
  mockTools(async (url) => response(url.includes("dataset-b") ? result("amount", [{ row_index: 25, value: 800 }]) : result()));
  const view = render(explorer()); await screen.findByRole("rowheader", { name: "Registro 4" });
  view.rerender(explorer("dataset-b"));
  expect(screen.queryByRole("rowheader", { name: "Registro 4" })).not.toBeInTheDocument();
  await screen.findByRole("rowheader", { name: "Registro 26" });
});

it("un error de red del endpoint outliers puede reintentarse sin alterar parámetros", async () => {
  let calls = 0;
  const fetchMock = mockTools(async () => { if (++calls === 1) throw new TypeError("network"); return response(result()); });
  const user = userEvent.setup(); render(explorer());
  const alert = await screen.findByRole("alert"); expect(alert).toHaveTextContent("Revisa la conexión");
  await user.click(screen.getByRole("button", { name: "Reintentar ejemplos" }));
  await screen.findByRole("rowheader", { name: "Registro 4" });
  const requests = fetchMock.mock.calls.filter(([url]) => url.endsWith("/outliers"));
  expect(requests).toHaveLength(2);
  expect(requests.map(([, init]) => JSON.parse(String(init.body)))).toEqual([
    { variables: ["amount"], parameters: {} }, { variables: ["amount"], parameters: {} },
  ]);
});

it("la herramienta se consulta después de finalizar las solicitudes dependientes de la columna", async () => {
  const pending: ((value: Response) => void)[] = [];
  const fetchMock = vi.fn(async (url: string) => url.endsWith("/outliers") ? response(result())
    : new Promise<Response>((done) => pending.push(() => done(response(toolFixtures[url.split("/tools/")[1]])))));
  vi.stubGlobal("fetch", fetchMock); render(explorer());
  expect(fetchMock).toHaveBeenCalledTimes(3);
  await act(async () => pending.forEach((done) => done(response({}))));
  await screen.findByRole("rowheader", { name: "Registro 4" });
  expect(fetchMock).toHaveBeenCalledTimes(4);
  const section = screen.getByRole("region", { name: "Ejemplos de valores atípicos" });
  expect(within(section).getByRole("table")).toBeInTheDocument();
});

it("agrupar solo el boxplot no vuelve a ejecutar outliers", async () => {
  const fetchMock = mockTools(async () => response(result()));
  const user = userEvent.setup();
  render(<MemoryRouter><ColumnExplorer datasetId="dataset-a" totalRows={60} numeric={["amount"]} categorical={["category"]} /></MemoryRouter>);
  await screen.findByRole("rowheader", { name: "Registro 4" });
  await user.selectOptions(screen.getByLabelText("Agrupar diagrama de caja por"), "category");
  await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/chart_boxplot"))).toHaveLength(2));
  expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/outliers"))).toHaveLength(1);
  expect(screen.getByRole("rowheader", { name: "Registro 4" })).toBeInTheDocument();
});
