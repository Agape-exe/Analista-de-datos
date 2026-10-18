import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { StrictMode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../../app/App";
import { intakeFixture } from "../../test/fixture";
import { previewFixture } from "../../test/preview-fixture";
import type { DatasetPreview } from "../../lib/api-client";
import { DatasetPreviewPanel, DatasetPreviewTable } from "./DatasetPreview";

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const response = (page: DatasetPreview) => new Response(JSON.stringify(page), { status: 200 });

function mockPages(total = 45) {
  const fetchMock = vi.fn(async (url: string) => {
    const parsed = new URL(url, "http://localhost");
    return response(previewFixture(Number(parsed.searchParams.get("offset")), Number(parsed.searchParams.get("limit")), total));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function panel(id = "dataset-a") {
  return <MemoryRouter><DatasetPreviewPanel key={id} datasetId={id} /></MemoryRouter>;
}

describe("AUD-010 vista previa", () => {
  it("sin dataset conserva el estado vacío y no solicita preview", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<MemoryRouter initialEntries={["/dataset"]}><App /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "Aún no hay dataset" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Subir dataset" })).toHaveAttribute("href", "/");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("muestra primera página real, correspondencia de columnas, nulos, ceros y tipos", async () => {
    const fetchMock = mockPages();
    render(panel());
    expect(await screen.findByText("Filas 1–20 de 45 · 20 registros mostrados")).toBeInTheDocument();
    const region = screen.getByRole("region", { name: "Filas del dataset" });
    expect(within(region).getAllByRole("columnheader").map((item) => item.textContent)).toEqual(["codigostring", "importeFloat64", "activoboolean", "notastring"]);
    expect(within(region).getAllByRole("row")).toHaveLength(21);
    expect(within(within(region).getAllByRole("row")[1]).getAllByRole("cell").map((item) => item.textContent)).toEqual(["001", "1.5", "true", "Sin dato"]);
    expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Siguiente" })).toBeEnabled();
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock.mock.calls[0][0]).toBe("/api/datasets/dataset-a/preview?offset=0&limit=20");
  });

  it("navega por página intermedia, última y anterior usando metadatos", async () => {
    const user = userEvent.setup();
    const fetchMock = mockPages();
    render(panel());
    await screen.findByText("Filas 1–20 de 45 · 20 registros mostrados");
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await screen.findByText("Filas 21–40 de 45 · 20 registros mostrados");
    expect(screen.queryByRole("cell", { name: "001" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await screen.findByText("Filas 41–45 de 45 · 5 registros mostrados");
    expect(screen.getByRole("button", { name: "Siguiente" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Anterior" }));
    await screen.findByText("Filas 21–40 de 45 · 20 registros mostrados");
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/api/datasets/dataset-a/preview?offset=0&limit=20", "/api/datasets/dataset-a/preview?offset=20&limit=20",
      "/api/datasets/dataset-a/preview?offset=40&limit=20", "/api/datasets/dataset-a/preview?offset=20&limit=20",
    ]);
  });

  it("cambia el tamaño de página desde el inicio sin precargar otras páginas", async () => {
    const user = userEvent.setup();
    const fetchMock = mockPages();
    render(panel());
    await screen.findByText("Filas 1–20 de 45 · 20 registros mostrados");
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await screen.findByText("Filas 21–40 de 45 · 20 registros mostrados");
    await user.selectOptions(screen.getByLabelText("Filas por página"), "10");
    await screen.findByText("Filas 1–10 de 45 · 10 registros mostrados");
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[2][0]).toBe("/api/datasets/dataset-a/preview?offset=0&limit=10");
  });

  it("muestra carga y bloquea controles sin filas inventadas", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})));
    render(panel());
    expect(screen.getByRole("status")).toHaveTextContent("Cargando filas");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Siguiente" })).toBeDisabled();
    expect(screen.getByLabelText("Filas por página")).toBeDisabled();
  });

  it("informa dataset vacío sin construir filas", async () => {
    mockPages(0);
    render(panel());
    expect(await screen.findByText("Este dataset no contiene filas disponibles.")).toBeInTheDocument();
    expect(screen.getByText("0 registros mostrados de 0")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Siguiente" })).toBeDisabled();
  });

  it("distingue null de la cadena null y conserva ISO, texto vacío y HTML como texto", async () => {
    const page = previewFixture(0, 20, 2);
    page.rows[0] = ["001", 1.5, true, null];
    page.rows[1] = ["2026-10-17T12:00:00Z", "null", "", '<img src=x onerror="alert(1)">'];
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(page)));
    render(panel());
    expect(await screen.findByRole("cell", { name: "null" })).toBeInTheDocument();
    expect(screen.getByText("Sin dato")).toBeInTheDocument();
    expect(screen.getByText("Texto vacío")).toBeInTheDocument();
    expect(screen.getByText("2026-10-17T12:00:00Z")).toBeInTheDocument();
    expect(screen.getByText('<img src=x onerror="alert(1)">')).toBeInTheDocument();
    expect(document.querySelector(".preview-table img")).toBeNull();
  });

  it("no presenta como exacto un entero JSON que perdió precisión", async () => {
    const page = previewFixture(0, 20, 1);
    const raw = JSON.stringify(page).replace('"001"', "9007199254740993");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(raw)));
    render(panel());
    expect(await screen.findByText("Precisión no garantizada")).toBeInTheDocument();
    expect(screen.getByText(/Hay números fuera del rango seguro/)).toBeInTheDocument();
    expect(screen.queryByText("9007199254740992")).not.toBeInTheDocument();
    expect(screen.queryByText("9007199254740993")).not.toBeInTheDocument();
  });

  it("conserva un entero seguro y un identificador numérico textual grande", () => {
    const page = previewFixture(0, 20, 1);
    page.rows[0] = ["9007199254740993", Number.MAX_SAFE_INTEGER, true, null];
    render(<DatasetPreviewTable page={page} />);
    expect(screen.getByText("9007199254740993")).toBeInTheDocument();
    expect(screen.getByText("9007199254740991")).toBeInTheDocument();
    expect(screen.queryByText("Precisión no garantizada")).not.toBeInTheDocument();
  });

  it("muestra nombres de columna extensos en una región accesible", async () => {
    const page = previewFixture(0, 20, 1);
    const name = "nombre_extenso_".repeat(20);
    page.columns[0].name = name;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(page)));
    render(panel());
    expect(await screen.findByRole("columnheader", { name: `${name} string` })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Filas del dataset" })).toHaveAttribute("tabindex", "0");
  });

  it("explica un error de conexión y permite reintentar", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockRejectedValueOnce(new TypeError("private network detail")).mockResolvedValueOnce(response(previewFixture()));
    vi.stubGlobal("fetch", fetchMock);
    render(panel());
    expect(await screen.findByRole("alert")).toHaveTextContent("No se puede conectar con el servidor");
    expect(screen.queryByText("private network detail")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("Filas 1–20 de 45 · 20 registros mostrados")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("detecta DATASET_NOT_FOUND y ofrece volver a Nuevo análisis sin inventar TTL", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: { code: "DATASET_NOT_FOUND", message: "/private/server/path" } }), { status: 404 })));
    render(panel());
    expect(await screen.findByRole("alert")).toHaveTextContent("El dataset ya no está disponible");
    expect(screen.getByRole("link", { name: "Volver a Nuevo análisis" })).toHaveAttribute("href", "/");
    expect(screen.queryByText("/private/server/path")).not.toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("maneja PREVIEW_TOO_LARGE y permite reducir filas sin truncamiento", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ detail: { code: "PREVIEW_TOO_LARGE", message: "too big" } }), { status: 413 }))
      .mockResolvedValueOnce(response(previewFixture(0, 10)));
    vi.stubGlobal("fetch", fetchMock);
    render(panel());
    expect(await screen.findByRole("alert")).toHaveTextContent("La página es demasiado grande");
    expect(screen.getByRole("alert")).toHaveTextContent("reducir las filas puede no resolverlo");
    await user.selectOptions(screen.getByLabelText("Filas por página"), "10");
    await screen.findByText("Filas 1–10 de 45 · 10 registros mostrados");
    expect(fetchMock.mock.calls[1][0]).toBe("/api/datasets/dataset-a/preview?offset=0&limit=10");
  });

  it.each([
    [422, { detail: [{ msg: "private validation details" }] }, "rechazó los parámetros"],
    [422, { detail: { code: "PREVIEW_UNSUPPORTED", message: "secret" } }, "no puede representar"],
    [429, { detail: { code: "REQUEST_RATE_LIMITED" } }, "límite de solicitudes"],
    [500, { detail: "private stack trace" }, "No se pudo cargar la vista previa"],
    [200, { dataset_id: "wrong" }, "respuesta del servidor está incompleta"],
  ])("maneja error %s sin exponer detalles internos", async (status, body, expected) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status })));
    render(panel());
    expect(await screen.findByRole("alert")).toHaveTextContent(new RegExp(expected, "i"));
    expect(screen.getByRole("alert")).not.toHaveTextContent(/secret|private/);
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeEnabled();
  });

  it("aborta al desmontar y descarta respuestas tardías", async () => {
    let resolve!: (value: Response) => void;
    const fetchMock = vi.fn<(url: string, options: RequestInit) => Promise<Response>>()
      .mockImplementation(() => new Promise<Response>((done) => { resolve = done; }));
    vi.stubGlobal("fetch", fetchMock);
    const view = render(panel());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const signal = fetchMock.mock.calls[0][1].signal as AbortSignal;
    view.unmount();
    expect(signal.aborted).toBe(true);
    await act(async () => resolve(response(previewFixture())));
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("cambia de dataset con solicitud pendiente y evita que la antigua sobrescriba la nueva", async () => {
    let resolveOld!: (value: Response) => void;
    const fetchMock = vi.fn().mockImplementationOnce(() => new Promise<Response>((done) => { resolveOld = done; }))
      .mockResolvedValueOnce(response(previewFixture(0, 20, 1, "dataset-b")));
    vi.stubGlobal("fetch", fetchMock);
    const view = render(panel());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const oldSignal = fetchMock.mock.calls[0][1].signal as AbortSignal;
    view.rerender(panel("dataset-b"));
    await screen.findByText("Filas 1–1 de 1 · 1 registros mostrados");
    expect(oldSignal.aborted).toBe(true);
    await act(async () => resolveOld(response(previewFixture(0, 20, 45))));
    expect(screen.queryByText(/de 45/)).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("envía una sola consulta inicial también bajo StrictMode", async () => {
    const fetchMock = mockPages();
    render(<StrictMode>{panel()}</StrictMode>);
    await screen.findByText("Filas 1–20 de 45 · 20 registros mostrados");
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("oculta filas anteriores mientras carga otra página y evita solicitudes duplicadas", async () => {
    const user = userEvent.setup();
    let resolveNext!: (value: Response) => void;
    const fetchMock = vi.fn().mockResolvedValueOnce(response(previewFixture()))
      .mockImplementationOnce(() => new Promise<Response>((done) => { resolveNext = done; }));
    vi.stubGlobal("fetch", fetchMock);
    render(panel());
    await screen.findByText("Filas 1–20 de 45 · 20 registros mostrados");
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(fetchMock).toHaveBeenCalledTimes(2);
    await act(async () => resolveNext(response(previewFixture(20))));
    await screen.findByText("Filas 21–40 de 45 · 20 registros mostrados");
  });

  it("permite operar select y paginación mediante teclado", async () => {
    const user = userEvent.setup();
    mockPages();
    render(panel());
    await screen.findByText("Filas 1–20 de 45 · 20 registros mostrados");
    await user.tab();
    expect(screen.getByLabelText("Filas por página")).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("region", { name: "Filas del dataset" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: "Siguiente" })).toHaveFocus();
    await user.keyboard("{Enter}");
    await screen.findByText("Filas 21–40 de 45 · 20 registros mostrados");
  });

  it("conserva resumen, métricas, perfiles y diccionario; Nuevo análisis limpia las filas", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async (url: string) => url.endsWith("/intake")
      ? new Response(JSON.stringify(intakeFixture)) : response(previewFixture(0, 20, 2, "test-dataset")));
    vi.stubGlobal("fetch", fetchMock);
    render(<MemoryRouter><App /></MemoryRouter>);
    await user.upload(screen.getByLabelText("Archivo del dataset", { exact: true }), new File(["a\n1\n"], "sales.csv"));
    await user.click(screen.getByRole("button", { name: "Comprender dataset" }));
    await screen.findByText("Filas 1–2 de 2 · 2 registros mostrados");
    expect(screen.getByRole("heading", { name: "Comprensión de columnas" })).toBeInTheDocument();
    expect(screen.getByText("Total amount")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Calidad de datos de un vistazo" })).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Diccionario de datos" }));
    expect(screen.getByRole("heading", { name: "Metadatos por columna" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Filas del dataset" })).not.toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "Nuevo análisis" })[0]);
    await user.click(screen.getByRole("link", { name: "Dataset" }));
    expect(screen.getByRole("heading", { name: "Aún no hay dataset" })).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });
});
