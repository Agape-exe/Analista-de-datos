import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../../app/App";
import { associationsIntakeFixture, toolFixtures } from "../../test/fixture";
import type { AnalysisResult, OutlierSummary } from "../../types/exploration";
import { ColumnExplorer } from "./ColumnExplorer";
import { readOutliers } from "./tool-state";
import type { useTool } from "./useTool";

afterEach(() => vi.unstubAllGlobals());

const json = (payload: unknown, status = 200) => new Response(JSON.stringify(payload), { status });
const base = toolFixtures.outliers as AnalysisResult;

function outliers(summary: OutlierSummary, column = "amount"): AnalysisResult {
  return { ...base, method: "outliers", status: "SUCCESS", variables: [column], result: { [column]: summary } as never };
}
const evaluated = (iqr: Partial<NonNullable<OutlierSummary["iqr"]>>, mad: OutlierSummary["mad"]): OutlierSummary => ({
  count: 40,
  iqr: { count: 0, percentage: 0, lower_fence: -10, upper_fence: 10, examples: [], example_rows: [], ...iqr },
  mad,
});
const outcome = (status: "FAILED" | "SKIPPED"): AnalysisResult => ({
  ...base, status, result: null, warnings: ["internal note"],
});

function tool(data?: AnalysisResult, override: Partial<ReturnType<typeof useTool>> = {}): ReturnType<typeof useTool> {
  return { data, loading: false, stale: false, error: undefined, retry: vi.fn(), ...override };
}

describe("readOutliers", () => {
  it("separates small samples, constants, MAD = 0 and IQR = 0", () => {
    expect(readOutliers(tool(outliers({ skipped: "insufficient observations" })), "amount")).toEqual({ kind: "small-sample" });
    expect(readOutliers(tool(outliers(evaluated({ lower_fence: 5, upper_fence: 5 }, { count: null, percentage: null }))), "amount"))
      .toMatchObject({ kind: "evaluated", constant: true, iqrZero: true, madZero: true });
    expect(readOutliers(tool(outliers(evaluated({ count: 3 }, { count: null, percentage: null }))), "amount"))
      .toMatchObject({ kind: "evaluated", constant: false, iqrZero: false, madZero: true });
    expect(readOutliers(tool(outliers(evaluated({ count: 4, lower_fence: 5, upper_fence: 5 }, { count: 4, percentage: 10 }))), "amount"))
      .toMatchObject({ kind: "evaluated", constant: false, iqrZero: true, madZero: false });
  });

  it("rejects results for another column or with a malformed summary", () => {
    expect(readOutliers(tool(outliers(evaluated({}, { count: 1, percentage: 2.5 }), "other")), "amount")).toEqual({ kind: "invalid" });
    expect(readOutliers(tool(outliers({ count: 40 })), "amount")).toEqual({ kind: "invalid" });
    expect(readOutliers(tool(outliers(evaluated({ count: -1 }, undefined))), "amount")).toEqual({ kind: "invalid" });
  });

  it("distinguishes execution failures, skips, request errors and pending work", () => {
    expect(readOutliers(tool(outcome("FAILED")), "amount")).toMatchObject({ kind: "problem", problem: { kind: "failed", retryable: true } });
    expect(readOutliers(tool(outcome("SKIPPED")), "amount")).toMatchObject({ kind: "problem", problem: { kind: "skipped", retryable: false } });
    const error = { message: "Sin conexión", expired: false };
    expect(readOutliers(tool(undefined, { error }), "amount")).toMatchObject({ kind: "problem", problem: { kind: "error" } });
    expect(readOutliers(tool(outliers(evaluated({}, undefined)), { loading: true, stale: true }), "amount")).toEqual({ kind: "pending" });
  });
});

function explorer(outlierResponse: () => Response, summaryResponse?: () => Response) {
  const fetchMock = vi.fn(async (url: string) => {
    const name = url.split("/tools/")[1];
    if (name === "outliers") return outlierResponse();
    if (name === "descriptive_statistics" && summaryResponse) return summaryResponse();
    return json(toolFixtures[name]);
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<MemoryRouter><ColumnExplorer datasetId="dataset-a" totalRows={60} numeric={["amount"]} categorical={[]} /></MemoryRouter>);
  return fetchMock;
}
const cell = (label: string) => screen.getByText(label, { selector: "dt" }).nextElementSibling;

describe("ColumnExplorer outlier states", () => {
  it("marks MAD as not evaluable instead of zero when MAD = 0", async () => {
    explorer(() => json(outliers(evaluated({ count: 3, percentage: 7.5 }, { count: null, percentage: null }))));
    expect(await screen.findByRole("note")).toHaveTextContent("MAD = 0");
    expect(cell("Atípicos robustos (MAD)")).toHaveTextContent("No evaluable");
    expect(cell("Atípicos (IQR)")).toHaveTextContent("3 (7.5%)");
  });

  it("explains constant columns without reporting zero outliers", async () => {
    explorer(() => json(outliers(evaluated({ lower_fence: 5, upper_fence: 5 }, { count: null, percentage: null }))));
    expect(await screen.findByRole("note")).toHaveTextContent("Columna constante");
    expect(cell("Atípicos (IQR)")).toHaveTextContent("No aplica");
    expect(screen.getByRole("region", { name: "Ejemplos de valores atípicos" })).toHaveTextContent("La columna es constante");
    expect(screen.queryByText("No se detectaron valores atípicos IQR.")).not.toBeInTheDocument();
  });

  it("explains small samples", async () => {
    explorer(() => json(outliers({ skipped: "insufficient observations" })));
    expect(await screen.findByRole("note")).toHaveTextContent("Muestra pequeña");
    expect(cell("Atípicos (IQR)")).toHaveTextContent("No evaluable");
  });

  it("offers a retry when the outlier computation fails on the server", async () => {
    const fetchMock = explorer(() => json(outcome("FAILED")));
    const section = screen.getByRole("region", { name: "Ejemplos de valores atípicos" });
    await within(section).findByText(/La herramienta falló/);
    expect(cell("Atípicos (IQR)")).toHaveTextContent("No disponible");
    await userEvent.setup().click(within(section).getByRole("button", { name: "Reintentar ejemplos" }));
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/outliers"))).toHaveLength(2));
  });

  it("shows descriptive statistics errors instead of silent dashes", async () => {
    explorer(() => json(outliers(evaluated({}, { count: 0, percentage: 0 }))),
      () => json({ detail: { code: "UNKNOWN", message: "Error interno" } }, 500));
    const alert = await screen.findByText("Error interno");
    expect(alert.closest("[role=alert]")).toBeInTheDocument();
    expect(within(alert.closest("[role=alert]") as HTMLElement).getByRole("button", { name: "Reintentar" })).toBeEnabled();
  });
});

function mockBackend(heatmap: () => Response) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith("/intake")) return json(associationsIntakeFixture);
    const name = url.split("/tools/")[1];
    if (name === "chart_correlation_heatmap") return heatmap();
    let payload = toolFixtures[name] as { result: Record<string, unknown> };
    if (name === "chart_boxplot" && JSON.parse(String(init?.body)).variables.length === 1) {
      payload = { ...payload, result: { ...payload.result, group_by: null } };
    }
    return json(payload);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function openAssociations() {
  const user = userEvent.setup();
  render(<MemoryRouter><App /></MemoryRouter>);
  await user.upload(screen.getByLabelText("Archivo del dataset"), new File(["a\n1\n"], "sales.csv"));
  await user.click(screen.getByRole("button", { name: "Comprender dataset" }));
  await user.click(await screen.findByRole("link", { name: "Explorar asociaciones" }, { timeout: 5000 }));
  return user;
}
const heatmapCard = () => screen.getByRole("heading", { name: "Matriz de correlación" }).closest(".heatmap-card") as HTMLElement;

describe("correlation heatmap states", () => {
  it("stops loading and explains a skipped matrix", async () => {
    mockBackend(() => json({ ...outcome("SKIPPED"), method: "chart_correlation_heatmap" }));
    await openAssociations();
    await waitFor(() => expect(heatmapCard()).toHaveTextContent("no es aplicable"));
    expect(heatmapCard()).not.toHaveTextContent("Calculando matriz");
  });

  it("lets the user retry a failed matrix", async () => {
    let calls = 0;
    mockBackend(() => (calls++ === 0
      ? json({ ...outcome("FAILED"), method: "chart_correlation_heatmap" })
      : json(toolFixtures.chart_correlation_heatmap)));
    const user = await openAssociations();
    await waitFor(() => expect(heatmapCard()).toHaveTextContent("falló en el servidor"));
    await user.click(within(heatmapCard()).getByRole("button", { name: "Reintentar" }));
    await waitFor(() => expect(heatmapCard().querySelector("svg.chart-svg")).toBeInTheDocument());
  });

  it("does not draw a malformed matrix", async () => {
    mockBackend(() => json({ ...(toolFixtures.chart_correlation_heatmap as object), result: { kind: "heatmap", columns: ["a", "b"], values: [[1]] } }));
    await openAssociations();
    await waitFor(() => expect(heatmapCard()).toHaveTextContent("no es válida"));
    expect(heatmapCard().querySelector("svg.chart-svg")).not.toBeInTheDocument();
  });
});
