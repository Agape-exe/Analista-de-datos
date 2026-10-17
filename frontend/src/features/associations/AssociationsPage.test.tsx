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
  await user.upload(screen.getByLabelText("Dataset file"), new File(["a\n1\n"], "sales.csv"));
  await user.click(screen.getByRole("button", { name: "Understand Dataset" }));
  await user.click(await screen.findByRole("link", { name: "Explore Associations" }));
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
    expect(await screen.findByRole("heading", { name: "Associations" })).toBeInTheDocument();
    const table = await screen.findByRole("region", { name: "Ranked relationships" });
    expect(within(table).getByText("Pearson r")).toBeInTheDocument();
    expect(within(table).getByText("Kruskal-Wallis ε²")).toBeInTheDocument();
    expect(screen.getByText("Significant candidates")).toBeInTheDocument();
    expect(await screen.findByRole("figure", { name: /Scatter plot of price against amount/ })).toBeInTheDocument();
    expect(await screen.findByRole("figure", { name: /correlation matrix of 2 numeric columns/ })).toBeInTheDocument();
    expect(await screen.findByRole("figure", { name: /Histogram of amount/ })).toBeInTheDocument();
    expect(screen.getByText("Spearman ρ:", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("id_like")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "View amount and category" }));
    expect(await screen.findByRole("figure", { name: "Box plot of amount by category" })).toBeInTheDocument();
    expect(screen.getByText("2 group(s) with fewer than 2 observations were excluded.")).toBeInTheDocument();

    const calls = requestedTools(fetchMock);
    expect(calls.map((call) => call.url)).toContain("/api/datasets/test-dataset/tools/relationship_ranking");
    expect(calls.find((call) => call.tool === "chart_scatter")?.variables).toEqual(["amount", "price"]);
    expect(calls.some((call) => call.tool === "chart_boxplot"
      && call.variables.join() === "amount,category")).toBe(true);
  });

  it("explains when the dataset is no longer in server memory", async () => {
    mockBackend({ relationship_ranking: () => new Response(JSON.stringify({
      detail: { code: "DATASET_NOT_FOUND", message: "The dataset is no longer in memory." },
    }), { status: 404 }) });
    await openAssociations();
    expect(await screen.findByRole("heading", { name: "Dataset no longer available" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Upload again" })).toHaveAttribute("href", "/");
  });

  it("asks for a dataset when nothing has been uploaded", async () => {
    const fetchMock = mockBackend();
    render(<MemoryRouter initialEntries={["/associations"]}><App /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "No dataset yet" })).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).not.toHaveBeenCalled());
  });
});
