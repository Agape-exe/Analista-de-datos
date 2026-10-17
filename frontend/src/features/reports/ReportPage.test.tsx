import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { IntakeProvider } from "../data-intake/IntakeProvider";
import { ReportPage } from "./ReportPage";

afterEach(() => vi.unstubAllGlobals());

test("null metrics stay unmeasured and no insights are invented", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
    run_id: "fixture", status: "SKIPPED", metrics: { precision: null, llm_calls: 0 },
    insights: [], evidence: [], analysis_results: [], stage_statuses: {}, warnings: [], errors: [],
  }))));
  render(<IntakeProvider><ReportPage /></IntakeProvider>);
  await userEvent.type(screen.getByLabelText("ID de ejecución"), "fixture");
  await userEvent.click(screen.getByRole("button", { name: "Consultar" }));
  await screen.findByText("Estado: SKIPPED");
  expect(screen.getByText("Sin medición")).toBeInTheDocument();
  expect(screen.getByText("0", { exact: true })).toBeInTheDocument();
  expect(screen.getByText("No hay insights respaldados por evidencia disponibles.")).toBeInTheDocument();
});

test("missing report shows server error and enables retry", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
    detail: { message: "Unknown run ID" },
  }), { status: 404 })));
  render(<IntakeProvider><ReportPage /></IntakeProvider>);
  await userEvent.type(screen.getByLabelText("ID de ejecución"), "missing");
  await userEvent.click(screen.getByRole("button", { name: "Consultar" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Unknown run ID");
  await waitFor(() => expect(screen.getByRole("button", { name: "Consultar" })).toBeEnabled());
});
