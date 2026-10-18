import { afterEach, describe, expect, it, vi } from "vitest";
import { previewFixture } from "../test/preview-fixture";
import { ApiError, DatasetExpiredError, getDatasetPreview, PreviewTooLargeError, type DatasetPreview } from "./api-client";

afterEach(() => vi.unstubAllGlobals());

describe("AUD-010 cliente de preview", () => {
  it("usa GET, el dataset codificado, offset/limit predeterminados y AbortSignal", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(previewFixture(0, 20, 2, "id/a b"))));
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();
    const page = await getDatasetPreview("id/a b", {}, controller.signal);
    expect(fetchMock).toHaveBeenCalledExactlyOnceWith("/api/datasets/id%2Fa%20b/preview?offset=0&limit=20", { method: "GET", signal: controller.signal });
    expect(page.rows[0]).toEqual(["001", 1.5, true, null]);
  });

  it("envía los parámetros solicitados sin pedir otras páginas", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(previewFixture(20, 10))));
    vi.stubGlobal("fetch", fetchMock);
    await getDatasetPreview("dataset-a", { offset: 20, limit: 10 });
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock.mock.calls[0][0]).toBe("/api/datasets/dataset-a/preview?offset=20&limit=10");
  });

  it.each([{ offset: -1 }, { limit: 0 }, { limit: 101 }, { offset: 0.5 }, { offset: Number.MAX_SAFE_INTEGER + 1 }])("rechaza parámetros locales inválidos %j", async (query) => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    await expect(getDatasetPreview("dataset-a", query)).rejects.toMatchObject({ code: "VALIDATION_ERROR" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("no consulta sin identificador", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    await expect(getDatasetPreview("")).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  const malformed: [string, (page: DatasetPreview) => unknown][] = [
    ["dataset diferente", (page) => ({ ...page, dataset_id: "otro" })],
    ["offset diferente", (page) => ({ ...page, offset: 20 })],
    ["limit diferente", (page) => ({ ...page, limit: 100 })],
    ["filas ausentes", (page) => ({ ...page, rows: undefined })],
    ["ancho inconsistente", (page) => ({ ...page, rows: [["001"]] })],
    ["conteo inconsistente", (page) => ({ ...page, returned_rows: 0 })],
    ["metadatos incompletos", (page) => ({ ...page, total_rows: undefined })],
    ["siguiente incorrecto", (page) => ({ ...page, next_offset: 900 })],
    ["has_more incorrecto", (page) => ({ ...page, has_more: !page.has_more })],
    ["tipo de celda inválido", (page) => ({ ...page, rows: [[{ private: "value" }, 1, true, null]] })],
    ["columnas repetidas", (page) => ({ ...page, columns: page.columns.map(() => page.columns[0]) })],
    ["respuesta nula", () => null],
  ];
  it.each(malformed)("rechaza respuesta inválida: %s", async (_label, change) => {
    const payload = change(previewFixture(0, 20, 1));
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(payload))));
    await expect(getDatasetPreview("dataset-a")).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  });

  it.each([
    [404, "DATASET_NOT_FOUND", DatasetExpiredError],
    [413, "PREVIEW_TOO_LARGE", PreviewTooLargeError],
  ])("conserva el error tipado %s %s", async (status, code, ErrorType) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: { code, message: "detalle" } }), { status, headers: { "X-Request-ID": "request-preview" } })));
    await expect(getDatasetPreview("dataset-a")).rejects.toBeInstanceOf(ErrorType);
  });

  it("mantiene el rechazo por cancelación", async () => {
    const controller = new AbortController();
    const failure = new DOMException("Aborted", "AbortError");
    vi.stubGlobal("fetch", vi.fn(() => {
      controller.abort();
      return Promise.reject(failure);
    }));
    await expect(getDatasetPreview("dataset-a", {}, controller.signal)).rejects.toBe(failure);
  });

  it("permite una página vacía válida al final", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(previewFixture(99, 20, 2)))));
    expect((await getDatasetPreview("dataset-a", { offset: 99 })).rows).toEqual([]);
  });
});
