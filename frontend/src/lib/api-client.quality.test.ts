import { afterEach, expect, it, vi } from "vitest";
import { DatasetExpiredError, getDatasetQuality } from "./api-client";
import { validQuality, type DatasetQuality } from "./quality-response";
import { emptyQualityFixture, qualityFixture } from "../test/quality-fixture";

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });

it("consulta GET tipado con dataset_id codificado y AbortSignal sin modificar la respuesta", async () => {
  const data = qualityFixture("id /?ñ");
  const before = JSON.stringify(data);
  const fetchMock = vi.fn().mockResolvedValue(response(data));
  vi.stubGlobal("fetch", fetchMock);
  const controller = new AbortController();
  expect(await getDatasetQuality(data.dataset_id, controller.signal)).toEqual(data);
  expect(fetchMock).toHaveBeenCalledWith("/api/datasets/id%20%2F%3F%C3%B1/quality", { method: "GET", signal: controller.signal });
  expect(JSON.stringify(data)).toBe(before);
});

it("rechaza identificador vacío sin peticiones", async () => {
  const fetchMock = vi.fn(); vi.stubGlobal("fetch", fetchMock);
  await expect(getDatasetQuality("")).rejects.toMatchObject({ code: "VALIDATION_ERROR" });
  expect(fetchMock).not.toHaveBeenCalled();
});

const invalid: ((q: DatasetQuality) => unknown)[] = [
  () => null, () => ({}), (q) => ({ ...q, dataset_id: "other" }),
  (q) => ({ ...q, total_rows: -1 }), (q) => ({ ...q, total_columns: 1.5 }),
  (q) => ({ ...q, total_cells: 8 }), (q) => ({ ...q, total_rows: Number.MAX_SAFE_INTEGER + 1 }),
  (q) => ({ ...q, status: "PASS" }), (q) => ({ ...q, status: "NOT_EVALUATED" }),
  (q) => ({ ...q, missing: null }), (q) => ({ ...q, missing: { ...q.missing, columns: null } }),
  (q) => ({ ...q, missing: { ...q.missing, columns: [] } }),
  (q) => ({ ...q, missing: { ...q.missing, missing_percentage: 101 } }),
  (q) => ({ ...q, missing: { ...q.missing, incomplete_rows: 4 } }),
  (q) => ({ ...q, missing: { ...q.missing, complete_rows: 0 } }),
  (q) => ({ ...q, missing: { ...q.missing, missing_cells: 3 } }),
  (q) => ({ ...q, missing: { ...q.missing, columns: q.missing.columns.map((c) => ({ ...c, column_name: "same" })) } }),
  (q) => ({ ...q, missing: { ...q.missing, columns: q.missing.columns.map((c) => ({ ...c, missing_percentage: -1 })) } }),
  (q) => ({ ...q, duplicates: null }),
  (q) => ({ ...q, duplicates: { ...q.duplicates, duplicate_rows: 3 } }),
  (q) => ({ ...q, duplicates: { ...q.duplicates, duplicate_groups: 0 } }),
  (q) => ({ ...q, duplicates: { ...q.duplicates, duplicate_percentage: Infinity } }),
  (q) => ({ ...q, rules: {} }), (q) => ({ ...q, rules: [null] }),
  (q) => ({ ...q, rules: [{ ...q.rules[0], status: "UNKNOWN" }] }),
  (q) => ({ ...q, rules: [{ ...q.rules[0], observed_count: -1 }] }),
  (q) => ({ ...q, rules: [{ ...q.rules[0], reason: 4 }] }),
  (q) => ({ ...q, rules: [{ ...q.rules[0], status: "NOT_EVALUATED" }] }),
  (q) => ({ ...q, rules: [q.rules[0], q.rules[0]] }),
];
it.each(invalid.map((change, index) => ({ change, index })))("rechaza respuesta inválida $index sin renderizarla", async ({ change }) => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(change(qualityFixture()))));
  await expect(getDatasetQuality("dataset-a")).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
});

it("acepta tabla vacía y campos opcionales ausentes, y valida valores no finitos", () => {
  expect(validQuality(emptyQualityFixture(), "dataset-a")).toBe(true);
  const data = qualityFixture();
  delete data.rules[0].reason; delete data.rules[0].observed_count;
  const frozen = Object.freeze(data);
  expect(validQuality(frozen, "dataset-a")).toBe(true);
  expect(validQuality({ ...data, missing: { ...data.missing, missing_percentage: NaN } }, "dataset-a")).toBe(false);
});

it("mantiene DatasetExpiredError y los códigos de evaluación del helper existente", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ detail: { code: "DATASET_NOT_FOUND" } }, 404)));
  await expect(getDatasetQuality("dataset-a")).rejects.toBeInstanceOf(DatasetExpiredError);
});
