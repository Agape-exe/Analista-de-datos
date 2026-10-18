import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { intakeFixture } from "../test/fixture";

function renderApp(path = "/") {
  return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
}

afterEach(() => vi.unstubAllGlobals());

describe("intake workflow", () => {
  it("does not allow submitting without a file and explains unavailable features", () => {
    renderApp();
    expect(screen.getByRole("button", { name: "Comprender dataset" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Anomalías Pronto" })).toBeDisabled();
    expect(screen.getByRole("link", { name: "Patrones" })).toHaveAttribute("href", "/patterns");
    expect(screen.getByRole("link", { name: "Asociaciones" })).toHaveAttribute("href", "/associations");
    expect(screen.getByLabelText("¿Qué te gustaría investigar?", { exact: false })).toBeDisabled();
  });

  it("uploads a dataset with options and dictionary, renders metadata and downloads JSON", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(intakeFixture), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const createUrl = vi.fn().mockReturnValue("blob:test");
    const revokeUrl = vi.fn();
    vi.stubGlobal("URL", Object.assign(class extends URL {}, { createObjectURL: createUrl, revokeObjectURL: revokeUrl }));
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    renderApp();
    const file = new File(["id;amount;category\n001;10;A\n002;;A\n"], "sales.csv", { type: "text/csv" });
    const dictionary = new File(['{"entries":[]}'], "dictionary.json", { type: "application/json" });
    await user.upload(screen.getByLabelText("Archivo del dataset"), file);
    await user.upload(screen.getByLabelText("Archivo del diccionario de datos"), dictionary);
    await user.selectOptions(screen.getByLabelText("Separador CSV"), ";");
    await user.selectOptions(screen.getByLabelText("Codificación del archivo"), "cp1252");
    await user.click(screen.getByRole("button", { name: "Comprender dataset" }));
    expect(await screen.findByRole("heading", { name: "Resumen del dataset" })).toBeInTheDocument();
    const request = fetchMock.mock.calls[0][1] as RequestInit;
    const body = request.body as FormData;
    expect(body.get("file")).toBe(file);
    expect(body.get("data_dictionary")).toBe(dictionary);
    expect(body.get("delimiter")).toBe(";");
    expect(body.get("encoding")).toBe("cp1252");
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.getByText("Total amount")).toBeInTheDocument();
    expect(screen.getByText("80%")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Notas de revisión" })).toBeInTheDocument();
    // The two unmeasured column confidences remain; AUD-014 replaces the old
    // unavailable quality-score placeholder with navigation to measured controls.
    expect(screen.getAllByText(/^No evaluad[oa]$/)).toHaveLength(2);
    expect(screen.getByText("Controles de calidad")).toBeInTheDocument();
    expect(screen.queryByText("Puntaje de calidad")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ver calidad de datos" })).toHaveAttribute("href", "/quality");
    expect(screen.getByRole("link", { name: "Explorar asociaciones" })).toHaveAttribute("href", "/associations");
    await user.click(screen.getByRole("button", { name: "Descargar diccionario" }));
    expect(createUrl).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
    expect(revokeUrl).toHaveBeenCalledWith("blob:test");
    click.mockRestore();
  });

  it("preserves selected files and options after a validation error and allows retry", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: { message: "Invalid row at line 2" } }), {
        status: 400, headers: { "X-Request-ID": "test-request" },
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify(intakeFixture), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    renderApp();
    await user.upload(screen.getByLabelText("Archivo del dataset"), new File(["a\n1\n"], "sales.csv"));
    await user.selectOptions(screen.getByLabelText("Separador CSV"), "|");
    await user.click(screen.getByRole("button", { name: "Comprender dataset" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid row at line 2");
    expect(screen.getByRole("alert")).toHaveTextContent("test-request");
    expect(screen.getByLabelText("Separador CSV")).toHaveValue("|");
    expect(screen.getByRole("button", { name: "Comprender dataset" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Comprender dataset" }));
    expect(await screen.findByRole("heading", { name: "Resumen del dataset" })).toBeInTheDocument();
  });

  it("shows actual in-flight state and prevents duplicate submissions", async () => {
    const user = userEvent.setup();
    let resolve!: (value: Response) => void;
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((done) => { resolve = done; })));
    renderApp();
    await user.upload(screen.getByLabelText("Archivo del dataset"), new File(["a\n1\n"], "sales.csv"));
    await user.click(screen.getByRole("button", { name: "Comprender dataset" }));
    expect(screen.getByRole("status")).toHaveTextContent("Comprendiendo tu dataset");
    expect(screen.getByRole("button", { name: "Procesando…" })).toBeDisabled();
    resolve(new Response(JSON.stringify(intakeFixture), { status: 200 }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Resumen del dataset" })).toBeInTheDocument());
  });

  it("shows an actionable empty state when opening Dataset without a result", () => {
    renderApp("/dataset");
    expect(screen.getByRole("heading", { name: "Aún no hay dataset" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Subir dataset" })).toHaveAttribute("href", "/");
  });
});
