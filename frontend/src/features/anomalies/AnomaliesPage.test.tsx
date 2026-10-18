import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../../app/App";
import { associationsIntakeFixture, toolFixtures } from "../../test/fixture";
import type { AnalysisResult, OutlierSummary } from "../../types/exploration";
import type { IntakeResponse } from "../../types/intake";
import { mergeExamples, readAnomalies } from "./anomalies-contract";

afterEach(() => vi.unstubAllGlobals());

const json = (payload: unknown, status = 200) => new Response(JSON.stringify(payload), { status });
const intake: IntakeResponse = {
  ...associationsIntakeFixture,
  profile: { ...associationsIntakeFixture.profile, row_count: 60 },
};
const datasetId = intake.profile.dataset_id;

const amount: OutlierSummary = {
  count: 58,
  iqr: { multiplier: 1.5, count: 2, percentage: 3.448276, lower_fence: -30, upper_fence: 30,
    examples: [500, 480], example_rows: [{ row_index: 3, value: 500 }, { row_index: 9, value: 480 }] },
  mad: { threshold: 3.5, count: 3, percentage: 5.172414, median: 1, mad: 6, lower_bound: -30.13, upper_bound: 32.13,
    examples: [500, 480, -45], example_rows: [
      { row_index: 3, value: 500, robust_z: 56.1 }, { row_index: 9, value: 480, robust_z: 53.8 }, { row_index: 12, value: -45, robust_z: -5.2 },
    ] },
};
const outliers = (columns: Record<string, OutlierSummary>): AnalysisResult => ({
  method: "outliers", status: "SUCCESS", completeness: "complete", variables: Object.keys(columns), result: columns as never, warnings: [], execution_time: 0,
});
const preview = (offset: number) => ({
  dataset_id: datasetId,
  columns: [{ name: "amount", data_type: "Float64", nullable: true }, { name: "category", data_type: "string", nullable: false }],
  rows: [[480, "norte"]], total_rows: 60, offset, limit: 1, returned_rows: 1, has_more: offset + 1 < 60, next_offset: offset + 1 < 60 ? offset + 1 : null,
});

it("reads audited partial outcomes without discarding measured anomaly columns", () => {
  const data: AnalysisResult = { ...outliers({ amount }), completeness: "partial",
    variables: ["amount", "price"], column_results: {
      amount: { status: "SUCCESS", result: amount as never },
      price: { status: "SKIPPED", warnings: ["insufficient observations"] },
    } };
  const reading = readAnomalies({ data, error: undefined, loading: false, stale: false, retry: vi.fn() });
  expect(reading.kind).toBe("ready");
  if (reading.kind === "ready") expect(reading.columns.map((item) => item.reading.kind)).toEqual(["evaluated", "small-sample"]);
  const skipped = { ...data, status: "SKIPPED" as const, completeness: "complete" as const,
    result: null, variables: ["price"], column_results: { price: data.column_results!.price } };
  expect(readAnomalies({ data: skipped, error: undefined, loading: false, stale: false, retry: vi.fn() }).kind).toBe("ready");
});

function mockBackend(columns: Record<string, OutlierSummary> = { amount, price: { skipped: "insufficient observations" } }) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith("/intake")) return json(intake);
    if (url.includes("/preview?")) return json(preview(Number(new URL(url, "http://x").searchParams.get("offset"))));
    const tool = url.split("/tools/")[1];
    if (tool === "outliers") return json(outliers(columns));
    if (tool === "chart_boxplot") {
      const payload = toolFixtures.chart_boxplot as { result: Record<string, unknown> };
      const grouped = JSON.parse(String(init?.body)).variables.length === 2;
      return json({ ...payload, result: { ...payload.result, column: "amount", group_by: grouped ? "category" : null } });
    }
    return json({ method: tool, status: "SKIPPED", warnings: [], execution_time: 0 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function openAnomalies() {
  const user = userEvent.setup();
  render(<MemoryRouter><App /></MemoryRouter>);
  await user.upload(screen.getByLabelText("Archivo del dataset"), new File(["a\n1\n"], "sales.csv"));
  await user.click(screen.getByRole("button", { name: "Comprender dataset" }));
  await screen.findByRole("link", { name: "Explorar asociaciones" }, { timeout: 5000 });
  await user.click(screen.getByRole("link", { name: "Anomalías" }));
  return user;
}

describe("anomalies page", () => {
  it("summarises every numeric column with one request and explains non-evaluable ones", async () => {
    const fetchMock = mockBackend();
    await openAnomalies();
    const table = await screen.findByRole("region", { name: "Atípicos por columna" });
    const rows = within(table).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("amount58");
    expect(rows[1]).toHaveTextContent("2 (3.4%)");
    expect(rows[1]).toHaveTextContent("3 (5.2%)");
    expect(rows[2]).toHaveTextContent("Muestra pequeña");
    expect(screen.getByText("Un valor atípico no es necesariamente un error.")).toBeInTheDocument();
    const outlierCalls = fetchMock.mock.calls.filter(([url]) => url.endsWith("/tools/outliers"));
    expect(outlierCalls).toHaveLength(1);
    expect(JSON.parse(String(outlierCalls[0][1]?.body))).toEqual({ variables: [], parameters: {} });
  });

  it("shows both thresholds, the boxplot and the examples merged by original record", async () => {
    mockBackend();
    await openAnomalies();
    const iqr = await screen.findByRole("region", { name: "Criterio IQR" });
    expect(iqr).toHaveTextContent("Límite inferior-30");
    expect(iqr).toHaveTextContent("Límite superior30");
    const mad = screen.getByRole("region", { name: "Criterio MAD" });
    expect(mad).toHaveTextContent("|z robusto| > 3.5");
    expect(mad).toHaveTextContent("-30.13 a 32.13");
    expect(await screen.findByRole("figure", { name: "Diagrama de caja de amount" })).toBeInTheDocument();
    const examples = screen.getByRole("region", { name: "Registros de ejemplos atípicos" });
    expect(within(examples).getAllByRole("rowheader").map((cell) => cell.textContent)).toEqual(["Registro 4", "Registro 10", "Registro 13"]);
    const last = within(examples).getAllByRole("row")[3];
    expect(last).toHaveTextContent("-45");
    expect(last).toHaveTextContent("-5.2");
    expect(within(last).queryByText("Fuera de límites")).not.toBeInTheDocument();
  });

  it("loads the exact record on demand from the dataset preview", async () => {
    const fetchMock = mockBackend();
    const user = await openAnomalies();
    const examples = await screen.findByRole("region", { name: "Registros de ejemplos atípicos" });
    const recordRequests = () => fetchMock.mock.calls.map(([url]) => url).filter((url) => url.includes("/preview?") && url.endsWith("limit=1"));
    expect(recordRequests()).toEqual([]);
    await user.click(within(examples).getByRole("button", { name: "Ver registro 10" }));
    const values = await screen.findByLabelText("Valores de Registro 10");
    expect(values).toHaveTextContent("amount · columna analizada480");
    expect(values).toHaveTextContent("categorynorte");
    const previews = recordRequests();
    expect(previews).toEqual([`/api/datasets/${datasetId}/preview?offset=9&limit=1`]);
    await user.click(within(examples).getByRole("button", { name: "Ocultar registro 10" }));
    expect(screen.queryByLabelText("Valores de Registro 10")).not.toBeInTheDocument();
  });

  it("explains small samples in the detail and shows no examples", async () => {
    mockBackend();
    const user = await openAnomalies();
    await screen.findByRole("region", { name: "Atípicos por columna" });
    await user.click(screen.getByRole("button", { name: "Inspeccionar price" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Detalle de price" })).toBeInTheDocument());
    expect(screen.getByRole("note")).toHaveTextContent("Muestra pequeña");
    expect(screen.queryByRole("region", { name: "Registros de ejemplos atípicos" })).not.toBeInTheDocument();
  });

  it("does not present a constant column as having zero anomalies", async () => {
    mockBackend({ amount: { count: 40, iqr: { count: 0, percentage: 0, lower_fence: 7, upper_fence: 7, examples: [], example_rows: [] },
      mad: { count: null, percentage: null, median: 7, mad: 0, lower_bound: null, upper_bound: null, examples: [], example_rows: [] } } });
    await openAnomalies();
    expect(await screen.findByRole("note")).toHaveTextContent("Columna constante");
    expect(screen.queryByText("Ningún criterio marcó valores atípicos en esta columna.")).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Criterio IQR" })).not.toBeInTheDocument();
  });
});

describe("mergeExamples", () => {
  it("never infers records without positions and rejects inconsistent references", () => {
    expect(mergeExamples({ iqr: { count: 1, percentage: 1, lower_fence: 0, upper_fence: 1, examples: [5] } }, 10)).toEqual({ kind: "no-positions" });
    const conflicting: OutlierSummary = { ...amount, mad: { ...amount.mad!, example_rows: [{ row_index: 3, value: 499, robust_z: 9 }] } };
    expect(mergeExamples(conflicting, 60)).toEqual({ kind: "invalid" });
    expect(mergeExamples(amount, 5)).toEqual({ kind: "invalid" });
  });

  it("keeps working with responses that predate the MAD detail", () => {
    const legacy: OutlierSummary = { ...amount, mad: { count: 3, percentage: 5 } };
    const merged = mergeExamples(legacy, 60);
    expect(merged).toMatchObject({ kind: "ready", madDetail: false });
    if (merged.kind === "ready") expect(merged.examples.map((item) => item.rowIndex)).toEqual([3, 9]);
  });
});
