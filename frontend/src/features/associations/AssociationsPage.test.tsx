import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../../app/App";
import { associationsIntakeFixture, toolFixtures } from "../../test/fixture";

afterEach(() => vi.unstubAllGlobals());

function mockBackend(overrides: Record<string, () => Response> = {}) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith("/intake")) return new Response(JSON.stringify(associationsIntakeFixture), { status: 200 });
    const tool = url.split("/tools/")[1];
    let payload = toolFixtures[tool] as { result: Record<string, unknown> };
    if (tool === "chart_boxplot" && JSON.parse(String(init?.body)).variables.length === 1) {
      payload = { ...payload, result: { ...payload.result, group_by: null } };
    }
    return overrides[tool]?.() ?? new Response(JSON.stringify(payload), { status: 200 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function openAssociations() {
  const user = userEvent.setup();
  render(<MemoryRouter><App /></MemoryRouter>);
  await user.upload(screen.getByLabelText("Archivo del dataset"), new File(["a\n1\n"], "sales.csv"));
  await user.click(screen.getByRole("button", { name: "Comprender dataset" }));
  await user.click(await screen.findByRole("link", { name: "Explorar asociaciones" }));
  return user;
}

function requestedTools(fetchMock: ReturnType<typeof mockBackend>) {
  return fetchMock.mock.calls.filter(([url]) => url.includes("/tools/")).map(([url, init]) => ({
    tool: url.split("/tools/")[1],
    url,
    variables: JSON.parse(String(init?.body)).variables as string[],
  }));
}

describe("associations page", () => {
  it("ranks candidates, draws the matrix and inspects a selected pair", async () => {
    const fetchMock = mockBackend();
    const user = await openAssociations();
    expect(await screen.findByRole("heading", { name: "Asociaciones" })).toBeInTheDocument();
    const table = await screen.findByRole("region", { name: "Relaciones ordenadas" });
    expect(within(table).getByText("r de Pearson")).toBeInTheDocument();
    expect(within(table).getByText("Kruskal-Wallis ε²")).toBeInTheDocument();
    expect(screen.getByText("Candidatas significativas")).toBeInTheDocument();
    expect(await screen.findByRole("figure", { name: /Diagrama de dispersión de price frente a amount/ })).toBeInTheDocument();
    expect(await screen.findByRole("figure", { name: /de 2 columnas numéricas/ })).toBeInTheDocument();
    expect(await screen.findByRole("figure", { name: /Histograma de amount/ })).toBeInTheDocument();
    expect(screen.getByText("ρ de Spearman:", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("id_like")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Ver amount y category" }));
    expect(await screen.findByRole("figure", { name: "Diagrama de caja de amount por category" })).toBeInTheDocument();
    expect(screen.getByText("2 group(s) with fewer than 2 observations were excluded.")).toBeInTheDocument();

    const calls = requestedTools(fetchMock);
    expect(calls.map((call) => call.url)).toContain("/api/datasets/test-dataset/tools/relationship_ranking");
    expect(calls.find((call) => call.tool === "chart_scatter")?.variables).toEqual(["amount", "price"]);
    expect(calls.some((call) => call.tool === "chart_boxplot"
      && call.variables.join() === "amount,category")).toBe(true);
  });

  it("asks for the primary results first, one request at a time, and outliers last", async () => {
    let active = 0, peak = 0;
    const fetchMock = mockBackend();
    const respond = fetchMock.getMockImplementation()!;
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      peak = Math.max(peak, ++active);
      try { return await respond(url, init); } finally { active -= 1; }
    });
    await openAssociations();
    await waitFor(() => expect(requestedTools(fetchMock).some((call) => call.tool === "outliers")).toBe(true), { timeout: 3000 });
    const tools = requestedTools(fetchMock).map((call) => call.tool);
    expect(tools.slice(0, 2)).toEqual(["relationship_ranking", "chart_correlation_heatmap"]);
    expect(tools.indexOf("outliers")).toBeGreaterThan(tools.indexOf("descriptive_statistics"));
    expect(new Set(tools).size).toBe(tools.length);
    expect(peak).toBe(1);
  });

  it("lets the user retry the ranking after the analysis service stayed busy", async () => {
    let calls = 0;
    mockBackend({
      relationship_ranking: () => (calls++ === 0
        ? new Response(JSON.stringify({ detail: { code: "ANALYSIS_CAPACITY_EXCEEDED", message: "busy" } }),
          { status: 429, headers: { "Retry-After": "60" } })
        : new Response(JSON.stringify(toolFixtures.relationship_ranking), { status: 200 })),
    });
    const user = await openAssociations();
    const alert = await screen.findByText(/El servicio de análisis está ocupado/);
    await user.click(within(alert.closest("[role=alert]") as HTMLElement).getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("Candidatas significativas")).toBeInTheDocument();
  });

  it("explains when the dataset is no longer in server memory", async () => {
    mockBackend({ relationship_ranking: () => new Response(JSON.stringify({
      detail: { code: "DATASET_NOT_FOUND", message: "The dataset is no longer in memory." },
    }), { status: 404 }) });
    await openAssociations();
    expect(await screen.findByRole("heading", { name: "El dataset ya no está disponible" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Volver a subir" })).toHaveAttribute("href", "/");
  });

  it("asks for a dataset when nothing has been uploaded", async () => {
    const fetchMock = mockBackend();
    render(<MemoryRouter initialEntries={["/associations"]}><App /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "Aún no hay dataset" })).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).not.toHaveBeenCalled());
  });
});
