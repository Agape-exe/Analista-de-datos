import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../../app/App";
import { associationsIntakeFixture } from "../../test/fixture";
import { groupedSummaryFixture, groupSummary } from "../../test/patterns-fixture";
import type { AnalysisResult } from "../../types/exploration";
import { limitations, readGroupedSummary } from "./patterns-contract";

afterEach(() => vi.unstubAllGlobals());

const json = (payload: unknown, status = 200) => new Response(JSON.stringify(payload), { status });

function mockBackend(summary: (body: { variables: string[]; parameters: Record<string, unknown> }) => Response) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith("/intake")) return json(associationsIntakeFixture);
    if (url.endsWith("/tools/grouped_summary")) return summary(JSON.parse(String(init?.body)));
    return json({ method: "unused", status: "SKIPPED", warnings: [], execution_time: 0 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function openPatterns() {
  const user = userEvent.setup();
  render(<MemoryRouter><App /></MemoryRouter>);
  await user.upload(screen.getByLabelText("Archivo del dataset"), new File(["a\n1\n"], "sales.csv"));
  await user.click(screen.getByRole("button", { name: "Comprender dataset" }));
  await screen.findByRole("link", { name: "Explorar asociaciones" }, { timeout: 5000 });
  await user.click(screen.getByRole("link", { name: "Patrones" }));
  return user;
}

const tool = (data?: AnalysisResult) => ({ data, loading: false, stale: false, error: undefined, retry: vi.fn() });

describe("patterns contract", () => {
  it("states omitted groups, unlabelled rows, small samples and empty groups", () => {
    const fixture = groupedSummaryFixture({
      groups: [groupSummary("norte", 120, 4, 100), groupSummary("este", 12, 1, 180, true), groupSummary("vacío", 3, 3, 0, true)],
    });
    const reading = readGroupedSummary(tool(fixture), "amount", "category");
    expect(reading.kind).toBe("ready");
    if (reading.kind !== "ready") return;
    expect(limitations(reading.view)).toEqual([
      "Se muestran los 3 grupos con más filas de 5. Se omitieron 2 grupos con 8 filas (7 valores observados); no aparecen en la tabla ni en el gráfico.",
      "5 filas no tienen categoría en «category» y no se asignan a ningún grupo (5 tienen valor en «amount»).",
      "2 grupos tienen menos de 20 observaciones: sus estadísticas son orientativas y no conviene compararlas.",
      "1 grupo no tiene valores observados en «amount»; solo se cuentan sus filas.",
    ]);
  });

  it("rejects responses for another selection or with inconsistent counts", () => {
    expect(readGroupedSummary(tool(groupedSummaryFixture({}, "price")), "amount", "category")).toEqual({ kind: "invalid" });
    expect(readGroupedSummary(tool(groupedSummaryFixture({ total_groups: 99 })), "amount", "category")).toEqual({ kind: "invalid" });
    const broken = groupSummary("norte", 10, 0, 1);
    expect(readGroupedSummary(tool(groupedSummaryFixture({ groups: [{ ...broken, count: 3 }], total_groups: 3 })), "amount", "category"))
      .toEqual({ kind: "invalid" });
  });
});

describe("patterns page", () => {
  it("shows the group table, chart and every limitation without calling groups clusters", async () => {
    const fetchMock = mockBackend(() => json(groupedSummaryFixture()));
    await openPatterns();
    const table = await screen.findByRole("region", { name: "Tabla de grupos" });
    expect(within(table).getAllByRole("rowheader").map((cell) => cell.textContent)).toEqual(["norte", "sur", "este"]);
    expect(within(table).getByText("Muestra pequeña")).toBeInTheDocument();
    expect(screen.getByRole("figure", { name: "Distribución de amount por cada categoría de category" })).toBeInTheDocument();
    const notes = screen.getByRole("note", { name: "Limitaciones del resumen" });
    expect(notes).toHaveTextContent("Se omitieron 2 grupos con 8 filas");
    expect(notes).toHaveTextContent("5 filas no tienen categoría");
    expect(screen.getByText("Los grupos son categorías existentes, no clusters.")).toBeInTheDocument();
    expect(screen.queryByText(/clusters? (descubiertos|encontrados)/i)).not.toBeInTheDocument();
    const request = fetchMock.mock.calls.find(([url]) => url.endsWith("/grouped_summary"));
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({ variables: ["amount", "category"], parameters: { max_groups: 10 } });
  });

  it("requests the selected variable and group limit", async () => {
    const fetchMock = mockBackend(({ variables }) => json(groupedSummaryFixture({}, variables[0], variables[1])));
    const user = await openPatterns();
    await screen.findByRole("region", { name: "Tabla de grupos" });
    await user.selectOptions(screen.getByLabelText("Variable"), "price");
    await user.selectOptions(screen.getByLabelText("Grupos mostrados"), "5");
    await waitFor(() => {
      const bodies = fetchMock.mock.calls.filter(([url]) => url.endsWith("/grouped_summary")).map(([, init]) => JSON.parse(String(init?.body)));
      expect(bodies.at(-1)).toEqual({ variables: ["price", "category"], parameters: { max_groups: 5 } });
    });
    expect(await screen.findByRole("figure", { name: /Distribución de price/ })).toBeInTheDocument();
  });

  it("explains failures and lets the user retry", async () => {
    let calls = 0;
    mockBackend(() => (calls++ === 0
      ? json({ method: "grouped_summary", status: "FAILED", warnings: ["boom"], execution_time: 0 })
      : json(groupedSummaryFixture())));
    const user = await openPatterns();
    expect(await screen.findByRole("alert")).toHaveTextContent("falló en el servidor");
    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByRole("region", { name: "Tabla de grupos" })).toBeInTheDocument();
  });

  it("does not show groups from a response for another selection", async () => {
    mockBackend(() => json(groupedSummaryFixture({}, "price")));
    await openPatterns();
    expect(await screen.findByRole("alert")).toHaveTextContent("no corresponde a la selección actual");
    expect(screen.queryByRole("region", { name: "Tabla de grupos" })).not.toBeInTheDocument();
  });
});
