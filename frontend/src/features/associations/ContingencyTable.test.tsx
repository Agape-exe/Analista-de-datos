import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { contingencyResult, contingencyTable } from "../../test/contingency-fixture";
import type { AnalysisResult } from "../../types/exploration";
import { contingencyWarnings, readContingency } from "./contingency-contract";
import { ContingencyTable } from "./ContingencyTable";
import { RelationshipDetail } from "./RelationshipDetail";

afterEach(() => vi.unstubAllGlobals());

const tool = (data?: AnalysisResult) => ({ data, loading: false, stale: false, error: undefined, retry: vi.fn() });

describe("contingency contract", () => {
  it("accepts a consistent table for the requested pair only", () => {
    expect(readContingency(tool(contingencyResult()), "region", "canal").kind).toBe("ready");
    expect(readContingency(tool(contingencyResult()), "canal", "region")).toEqual({ kind: "invalid" });
    expect(readContingency(tool(contingencyResult({ row_totals: [1, 2, 3] })), "region", "canal")).toEqual({ kind: "invalid" });
    expect(readContingency(tool(contingencyResult({ counts: [[1, 2], [3, 4]] })), "region", "canal")).toEqual({ kind: "invalid" });
    // AUD-022: a pair table has no per-column outcomes, so a partial envelope is not accepted.
    const partial = { ...contingencyResult(), completeness: "partial" as const, column_results: {
      region: { status: "SUCCESS" as const, result: null, warnings: [] }, canal: { status: "SKIPPED" as const, result: null, warnings: [] } } };
    expect(readContingency(tool(partial), "region", "canal")).toEqual({ kind: "invalid" });
  });

  it("states every statistical warning and never implies causation", () => {
    expect(contingencyWarnings(contingencyTable({ empty_cells: 2, folded_columns: 4 }))).toEqual([
      "El 56 % de las frecuencias esperadas es menor que 5 (5 de 9 celdas): la aproximación χ² puede no ser fiable; interpreta su valor p con cautela.",
      "1 celda tiene una frecuencia esperada menor que 1.",
      "2 combinaciones de categorías no aparecen en los datos (conteo 0).",
      "3 filas no se incluyen porque le falta el valor de «region» o de «canal».",
      "Por legibilidad, las 4 categorías menos frecuentes de «canal» se agrupan en «Otras»; las frecuencias esperadas y las advertencias usan la tabla completa.",
      "Los conteos describen cuántas veces coinciden las categorías; una asociación no implica que una cause la otra.",
    ]);
    expect(contingencyWarnings(contingencyTable({ expected_below_5: 0, expected_below_1: 0, excluded_rows: 0 }))).toHaveLength(1);
  });
});

describe("ContingencyTable", () => {
  it("shows counts with row and column totals and marks sparse expected cells", () => {
    render(<ContingencyTable table={contingencyTable()} />);
    const table = screen.getByRole("region", { name: "Tabla de contingencia de region y canal" });
    expect(within(table).getAllByRole("rowheader").map((cell) => cell.textContent)).toEqual(["norte", "sur", "este", "Total"]);
    const norte = within(table).getAllByRole("row")[1];
    expect(within(norte).getAllByRole("cell").map((cell) => cell.textContent)).toEqual(["40", "6", "4†", "50"]);
    const total = within(table).getAllByRole("row").at(-1)!;
    expect(within(total).getAllByRole("cell").map((cell) => cell.textContent)).toEqual(["47", "40", "8", "95"]);
    expect(screen.getByText(/† Frecuencia esperada menor que 5/)).toBeInTheDocument();
  });

  it("switches between counts and row, column and total percentages", async () => {
    const user = userEvent.setup();
    render(<ContingencyTable table={contingencyTable()} />);
    const table = screen.getByRole("region", { name: "Tabla de contingencia de region y canal" });
    const cells = (row: number) => within(within(table).getAllByRole("row").at(row)!).getAllByRole("cell").map((cell) => cell.textContent);
    await user.click(screen.getByRole("button", { name: "% de fila" }));
    expect(cells(1)).toEqual(["80 %", "12 %", "8 %†", "100 %"]);
    // The other margin shows the overall distribution of the columns.
    expect(cells(-1)).toEqual(["49.5 %", "42.1 %", "8.4 %", "100 %"]);
    expect(screen.getByRole("button", { name: "% de fila" })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "% de columna" }));
    expect(cells(1)).toEqual(["85.1 %", "15 %", "50 %†", "52.6 %"]);
    expect(cells(-1)).toEqual(["100 %", "100 %", "100 %", "100 %"]);
    await user.click(screen.getByRole("button", { name: "% del total" }));
    expect(cells(1)[0]).toBe("42.1 %");
    expect(cells(-1).at(-1)).toBe("100 %");
  });

  it("labels folded categories instead of showing the largest folded one", () => {
    render(<ContingencyTable table={contingencyTable({ folded_rows: 3, folded_columns: 2 })} />);
    const table = screen.getByRole("region", { name: "Tabla de contingencia de region y canal" });
    expect(within(table).getByRole("rowheader", { name: "Otras (3 categorías)" })).toBeInTheDocument();
    expect(within(table).getByRole("columnheader", { name: "Otras (2 categorías)" })).toBeInTheDocument();
  });
});

describe("RelationshipDetail for two categorical columns", () => {
  it("replaces the placeholder with the contingency table of the selected pair", async () => {
    const fetchMock = vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith("/chart_contingency")
      ? contingencyResult() : { method: "cramers_v", status: "SUCCESS", variables: ["region", "canal"], effect_size: 0.4, p_value: 0.001, sample_size: 95, execution_time: 0 }),
    { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<RelationshipDetail datasetId="ds" x="region" y="canal" numeric={[]} />);
    expect(await screen.findByRole("region", { name: "Tabla de contingencia de region y canal" })).toBeInTheDocument();
    expect(screen.queryByText(/aún no está disponible/)).not.toBeInTheDocument();
    const call = fetchMock.mock.calls.find(([url]) => url.endsWith("/chart_contingency"));
    expect(JSON.parse(String((call as unknown as [string, RequestInit])[1].body))).toEqual({ variables: ["region", "canal"], parameters: {} });
  });

  it("explains a table that is not applicable", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith("/chart_contingency")
      ? { method: "chart_contingency", status: "SKIPPED", warnings: ["region: 80 categories exceed the configured limit of 50."], execution_time: 0 }
      : { method: "cramers_v", status: "SKIPPED", warnings: [], execution_time: 0 }), { status: 200 })));
    render(<RelationshipDetail datasetId="ds" x="region" y="canal" numeric={[]} />);
    await waitFor(() => expect(screen.getAllByText("Este cálculo no es aplicable a la selección actual.").length).toBeGreaterThan(0));
    expect(screen.getByText(/80 categories exceed/)).toBeInTheDocument();
  });
});
