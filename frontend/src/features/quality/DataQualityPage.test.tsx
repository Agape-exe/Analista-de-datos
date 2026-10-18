import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "../../app/App";
import { intakeFixture } from "../../test/fixture";
import { qualityFixture, emptyQualityFixture } from "../../test/quality-fixture";
import { intakePreviewFixture } from "../../test/preview-fixture";
import { DataQualityPage, DatasetQualityPanel } from "./DataQualityPage";
import { IntakeProvider } from "../data-intake/IntakeProvider";

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const response = (payload: unknown, status = 200) => new Response(JSON.stringify(payload), { status });
const panel = (id = "dataset-a") => <MemoryRouter><DatasetQualityPanel datasetId={id} filename={`${id}.csv`} /></MemoryRouter>;
const success = async () => screen.findByText("Evaluación completada");

it("integra /quality, habilita el menú y no solicita datos sin dataset", () => {
  const fetchMock = vi.fn(); vi.stubGlobal("fetch", fetchMock);
  render(<MemoryRouter initialEntries={["/quality"]}><App /></MemoryRouter>);
  expect(screen.getByRole("link", { name: "Calidad de datos" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("heading", { name: "Aún no hay dataset" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Ir a Nuevo análisis" })).toHaveAttribute("href", "/");
  expect(fetchMock).not.toHaveBeenCalled();
});

it("sin dataset tampoco consulta desde el componente de página", () => {
  const fetchMock = vi.fn(); vi.stubGlobal("fetch", fetchMock);
  render(<MemoryRouter><IntakeProvider><DataQualityPage /></IntakeProvider></MemoryRouter>);
  expect(fetchMock).not.toHaveBeenCalled();
});

it("anuncia carga sin mostrar métricas o reglas inventadas", () => {
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})));
  render(panel());
  expect(screen.getByRole("status")).toHaveTextContent("Consultando calidad");
  expect(screen.queryByRole("region", { name: "Resumen de calidad" })).not.toBeInTheDocument();
});

it("presenta conteos exactos, porcentajes del servidor, orden de columnas y reglas FAIL", async () => {
  const data = qualityFixture();
  data.missing.missing_percentage = 22.25; // Presentation must use the server's value.
  const before = JSON.stringify(data);
  const fetchMock = vi.fn().mockResolvedValue(response(data)); vi.stubGlobal("fetch", fetchMock);
  render(panel()); await success();
  const summary = screen.getByRole("region", { name: "Resumen de calidad" });
  expect(within(summary).getByText("Total de filas").parentElement).toHaveTextContent("Total de filas3");
  expect(within(summary).getByText("Celdas faltantes").parentElement).toHaveTextContent("Celdas faltantes2");
  expect(within(summary).getByText("Porcentaje de celdas faltantes").parentElement).toHaveTextContent("22.25%");
  expect(within(summary).getByText("Filas completas").parentElement).toHaveTextContent("Filas completas1");
  expect(within(summary).getByText("Filas incompletas").parentElement).toHaveTextContent("Filas incompletas2");
  const table = screen.getByRole("table", { name: "Valores faltantes por columna" });
  expect(within(table).getAllByRole("rowheader").map((cell) => cell.textContent)).toEqual(["id", "nombre", "valor"]);
  expect(within(within(table).getAllByRole("row")[3]).getAllByRole("cell").map((cell) => cell.textContent)).toEqual(["Int64", "2", "66.67%"]);
  const duplicates = screen.getByRole("region", { name: "Filas completamente duplicadas" });
  expect(duplicates).toHaveTextContent("excluye la primera aparición");
  expect(duplicates).toHaveTextContent("33.33%");
  expect(screen.getAllByText("FAIL · Incumplida")).toHaveLength(2);
  expect(screen.getByText("Conteo observado: 2")).toBeInTheDocument();
  expect(screen.getByText("Se observaron valores faltantes.")).toBeInTheDocument();
  expect(screen.queryByText(/excelente|Puntaje de calidad/)).not.toBeInTheDocument();
  expect(JSON.stringify(data)).toBe(before);
  expect(fetchMock).toHaveBeenCalledOnce();
});

it("dataset limpio muestra PASS y 0% sin acreditar calidad general", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(qualityFixture("dataset-a", true))));
  render(panel()); await success();
  expect(screen.getAllByText("PASS · Cumplida")).toHaveLength(2);
  expect(screen.getAllByText("0%").length).toBeGreaterThan(2);
  expect(screen.getByText(/no acreditan la calidad general/)).toBeInTheDocument();
});

it("dataset vacío presenta NOT_EVALUATED sin confundirlo con FAIL ni atribuir conteos a reglas", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(emptyQualityFixture())));
  render(panel());
  await screen.findByText("NOT_EVALUATED · Evaluación no realizada");
  expect(screen.getAllByText("NOT_EVALUATED · No evaluada")).toHaveLength(2);
  expect(screen.getAllByText("Sin conteo observado")).toHaveLength(2);
  expect(screen.queryByText(/Conteo observado:/)).not.toBeInTheDocument();
  expect(screen.queryByText(/FAIL ·/)).not.toBeInTheDocument();
  expect(screen.getByText("No hay columnas disponibles.")).toBeInTheDocument();
});

it("renderiza futuras reglas y campos opcionales sin suponer dos elementos", async () => {
  const data = qualityFixture();
  data.rules.push({ rule_id: "ADDITIONAL", description: "Regla adicional", status: "NOT_EVALUATED", reason: "No hay información suficiente." });
  delete data.rules[0].observed_count; delete data.rules[0].reason;
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(data)));
  render(panel()); await success();
  expect(screen.getByText("Regla adicional")).toBeInTheDocument();
  expect(screen.getByText("Conteo no disponible")).toBeInTheDocument();
  expect(screen.getByText("No hay información suficiente.")).toBeInTheDocument();
});

it.each([
  [404, "DATASET_NOT_FOUND", "El dataset ya no está disponible", true],
  [413, "QUALITY_TOO_LARGE", "La evaluación excede los límites", true],
  [422, "QUALITY_UNSUPPORTED", "La evaluación no es compatible", false],
  [429, "REQUEST_RATE_LIMITED", "Límite de solicitudes alcanzado", false],
  [429, "ANALYSIS_CAPACITY_EXCEEDED", "El servidor está ocupado", false],
  [422, "VALIDATION_ERROR", "No se pudo evaluar el dataset", false],
  [500, "UNKNOWN", "No se pudo cargar la calidad", false],
])("maneja HTTP %s / %s sin presentar errores como reglas FAIL", async (status, code, title, reload) => {
  const failure = response({ detail: { code, message: "/private/path secret" } }, status);
  // A long Retry-After exhausts the client's automatic retries immediately.
  if (status === 429) failure.headers.set("Retry-After", "60");
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(failure));
  render(panel());
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent(String(title));
  expect(alert).not.toHaveTextContent(/secret|private|FAIL/);
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  if (reload) expect(screen.getByRole("link", { name: "Volver a Nuevo análisis" })).toHaveAttribute("href", "/");
  else expect(screen.getByRole("button", { name: "Reintentar" })).toBeEnabled();
});

it("reintenta después de fallo de red y sustituye el error por resultados reales", async () => {
  const fetchMock = vi.fn().mockRejectedValueOnce(new Error("private")).mockResolvedValueOnce(response(qualityFixture()));
  vi.stubGlobal("fetch", fetchMock); const user = userEvent.setup();
  render(panel()); await screen.findByRole("alert");
  expect(screen.getByRole("alert")).toHaveTextContent("No se puede conectar");
  await user.click(screen.getByRole("button", { name: "Reintentar" })); await success();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

it("rechaza respuesta HTTP 200 incompleta", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ dataset_id: "other" })));
  render(panel()); expect(await screen.findByRole("alert")).toHaveTextContent("La respuesta de calidad no es válida");
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

it("cambia dataset, aborta la solicitud anterior y descarta su respuesta tardía", async () => {
  let resolve!: (value: Response) => void;
  const fetchMock = vi.fn().mockImplementationOnce(() => new Promise<Response>((done) => { resolve = done; }))
    .mockResolvedValueOnce(response(qualityFixture("dataset-b", true)));
  vi.stubGlobal("fetch", fetchMock);
  const view = render(panel());
  await act(async () => {});
  const signal = fetchMock.mock.calls[0][1].signal as AbortSignal;
  view.rerender(panel("dataset-b")); await success();
  expect(signal.aborted).toBe(true);
  await act(async () => resolve(response(qualityFixture())));
  expect(screen.getAllByText("PASS · Cumplida")).toHaveLength(2);
  expect(screen.queryByText("FAIL · Incumplida")).not.toBeInTheDocument();
});

it("oculta resultados anteriores inmediatamente mientras cambia el dataset", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(response(qualityFixture())).mockImplementationOnce(() => new Promise<Response>(() => {})));
  const view = render(panel()); await success();
  view.rerender(panel("dataset-b"));
  expect(screen.getByRole("status")).toHaveTextContent("Consultando calidad");
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

it("cancela al desmontar y descarta respuestas posteriores", async () => {
  let resolve!: (value: Response) => void;
  const fetchMock = vi.fn().mockImplementation(() => new Promise<Response>((done) => { resolve = done; }));
  vi.stubGlobal("fetch", fetchMock);
  const view = render(panel()); await act(async () => {});
  const signal = fetchMock.mock.calls[0][1].signal as AbortSignal;
  view.unmount(); expect(signal.aborted).toBe(true);
  await act(async () => resolve(response(qualityFixture())));
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

it("StrictMode hace una sola solicitud y no vuelve a consultar por rerender", async () => {
  const fetchMock = vi.fn().mockResolvedValue(response(qualityFixture())); vi.stubGlobal("fetch", fetchMock);
  const view = render(<StrictMode>{panel()}</StrictMode>); await success();
  view.rerender(<StrictMode>{panel()}</StrictMode>);
  expect(fetchMock).toHaveBeenCalledOnce();
});

it("conserva texto no confiable, nombres extensos y navegación por teclado", async () => {
  const data = qualityFixture(); data.missing.columns[0].column_name = '<img src=x onerror="alert(1)">' + "largo".repeat(30);
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(data)));
  const user = userEvent.setup(); render(panel()); await success();
  expect(screen.getByRole("rowheader", { name: data.missing.columns[0].column_name })).toBeInTheDocument();
  expect(document.querySelector(".quality-table img")).toBeNull();
  await user.tab(); expect(screen.getByRole("link", { name: "Ver Dataset" })).toHaveFocus();
  await user.tab(); expect(screen.getByRole("region", { name: "Detalle de valores faltantes" })).toHaveFocus();
});

it("integra IntakeProvider, conserva Dataset/Diccionario y limpia la evaluación al reiniciar", async () => {
  const fetchMock = vi.fn(async (url: string) => url.endsWith("/intake") ? response(intakeFixture)
    : url.includes("/preview?") ? response(intakePreviewFixture) : response(qualityFixture("test-dataset")));
  vi.stubGlobal("fetch", fetchMock); const user = userEvent.setup();
  render(<MemoryRouter><App /></MemoryRouter>);
  await user.upload(screen.getByLabelText("Archivo del dataset", { exact: true }), new File(["a\n1\n"], "sales.csv"));
  await user.click(screen.getByRole("button", { name: "Comprender dataset" }));
  await screen.findByRole("region", { name: "Filas del dataset" });
  expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/quality"))).toHaveLength(0);
  expect(screen.queryByText("Puntaje de calidad")).not.toBeInTheDocument();
  await user.click(screen.getByRole("link", { name: "Ver calidad de datos" })); await success();
  expect(fetchMock.mock.calls.filter(([url]) => url === "/api/datasets/test-dataset/quality")).toHaveLength(1);
  await user.click(screen.getByRole("link", { name: "Diccionario de datos" }));
  expect(screen.getByRole("heading", { name: "Metadatos por columna" })).toBeInTheDocument();
  expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/quality"))).toHaveLength(1);
  await user.click(screen.getAllByRole("button", { name: "Nuevo análisis" })[0]);
  await user.click(screen.getByRole("link", { name: "Calidad de datos" }));
  expect(screen.getByRole("heading", { name: "Aún no hay dataset" })).toBeInTheDocument();
  expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/quality"))).toHaveLength(1);
});
