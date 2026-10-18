import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../../app/App";
import { intakeFixture } from "../../test/fixture";
import { intakePreviewFixture } from "../../test/preview-fixture";
import type { IntakeResponse } from "../../types/intake";
import { IntakeProvider, useIntake } from "../data-intake/IntakeProvider";
import { DataDictionaryPage } from "./DataDictionaryPage";

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

const response = (result: IntakeResponse) => new Response(JSON.stringify(result), { status: 200 });
const clone = (): IntakeResponse => structuredClone(intakeFixture);

// Exercise the real provider while keeping the dictionary visible through state changes.
function IntakeControls() {
  const { updateDraft, analyze, reset } = useIntake();
  return <><input aria-label="Dataset de prueba" type="file" onChange={(event) => updateDraft({ file: event.target.files?.[0] ?? null })} />
    <button onClick={() => void analyze()}>Cargar en prueba</button><button onClick={reset}>Reiniciar en prueba</button></>;
}

function renderDictionary() {
  return render(<MemoryRouter><IntakeProvider><IntakeControls /><DataDictionaryPage /></IntakeProvider></MemoryRouter>);
}

async function load(result: IntakeResponse = clone()) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(result)));
  renderDictionary();
  fireEvent.change(screen.getByLabelText("Dataset de prueba"), { target: { files: [new File(["a\n1"], result.filename)] } });
  fireEvent.click(screen.getByRole("button", { name: "Cargar en prueba" }));
  await screen.findByRole("heading", { name: "Metadatos por columna" });
}

function row(name: string) {
  return within(screen.getByRole("rowheader", { name }).closest("tr")!);
}

describe("AUD-011 diccionario de datos", () => {
  it("habilita la navegación real desde Datos y ofrece Nuevo análisis sin dataset", async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><App /></MemoryRouter>);
    const link = screen.getByRole("link", { name: "Diccionario de datos" });
    expect(link).toHaveAttribute("href", "/dictionary");
    await user.click(link);
    expect(link).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("heading", { name: "Aún no hay dataset" })).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Ir a Nuevo análisis" }));
    expect(screen.getByRole("heading", { name: "Analiza tus datos" })).toBeInTheDocument();
  });

  it("muestra columnas del intake existente sin nuevas consultas ni edición", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async (url: string) => url.includes("/preview?")
      ? new Response(JSON.stringify(intakePreviewFixture)) : response(clone()));
    vi.stubGlobal("fetch", fetchMock);
    render(<MemoryRouter><App /></MemoryRouter>);
    await user.upload(screen.getByLabelText("Archivo del dataset", { exact: true }), new File(["id\n001"], "sales.csv"));
    await user.click(screen.getByRole("button", { name: "Comprender dataset" }));
    await screen.findByRole("heading", { name: "Resumen del dataset" });
    await screen.findByRole("region", { name: "Filas del dataset" });
    const callsBeforeDictionary = fetchMock.mock.calls.length;
    await user.click(screen.getByRole("link", { name: "Diccionario de datos" }));
    expect(screen.getAllByRole("rowheader").map((element) => element.textContent)).toEqual(["id", "amount", "category"]);
    expect(screen.getByText("Solo lectura")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(callsBeforeDictionary).toBe(2); // Intake + preview on Dataset; dictionary adds none.
    expect(fetchMock).toHaveBeenCalledTimes(callsBeforeDictionary);
  });

  it("distingue tipo observado, tipo declarado y semántica declarada del rol del perfil", async () => {
    const result = clone();
    result.summary.data_dictionary.entries![1] = {
      column_name: "amount", source: "official", data_type: "decimal", semantic_type: "ingreso",
      description: "Importe declarado", unit: "PEN", confidence: 0, inferred_fields: [],
    };
    await load(result);
    const amount = row("amount");
    expect(amount.getByText("Int64")).toBeInTheDocument();
    expect(amount.getByText("decimal")).toBeInTheDocument();
    expect(amount.getByText("ingreso")).toBeInTheDocument();
    expect(amount.getByText("Rol del perfil: Numérica")).toBeInTheDocument();
    expect(amount.getByText("Importe declarado")).toBeInTheDocument();
    expect(amount.getByText("PEN")).toBeInTheDocument();
    expect(amount.getByText("Fuente: Oficial")).toBeInTheDocument();
    expect(amount.getByText("Confianza: 0%")).toBeInTheDocument();
  });

  it("marca campos inferidos de una entrada manual sin presentarlos como declarados", async () => {
    const result = clone();
    result.summary.data_dictionary.entries![1] = {
      column_name: "amount", source: "manual", data_type: "Int64", semantic_type: "numeric",
      description: "Importe proporcionado", inferred_fields: ["data_type", "semantic_type"],
      inference_reason: "Observed numeric values; uniqueness alone is not an ID.",
    };
    await load(result);
    const amount = row("amount");
    expect(amount.getByText("Fuente: Manual")).toBeInTheDocument();
    expect(amount.getByText("Tipo técnico: Int64")).toBeInTheDocument();
    expect(amount.getByText("Campos inferidos")).toBeInTheDocument();
    expect(amount.getByText("Importe proporcionado")).toBeInTheDocument();
    expect(amount.getByText("Inferido")).toBeInTheDocument();
    expect(amount.getAllByRole("cell")[1]).toHaveTextContent("No disponible");
    expect(amount.getByText(/Justificación: Valores numéricos observados/)).toBeInTheDocument();
  });

  it("traduce la descripción estructural inferida sin confirmar significado de negocio", async () => {
    const result = clone();
    result.summary.data_dictionary.entries![0] = {
      column_name: "id", source: "inferred", data_type: "string", semantic_type: "identifier",
      description: "Column 'id' with observed type string and proposed role identifier. Business meaning is unverified.",
      inferred_fields: ["description", "data_type", "semantic_type"],
      inference_reason: "Explicit identifier label and discrete values.",
    };
    await load(result);
    const id = row("id");
    expect(id.getByText(/Columna «id» con tipo observado string y rol propuesto Identificador/)).toBeInTheDocument();
    expect(id.getByText("Significado de negocio sin verificar")).toBeInTheDocument();
    expect(id.getByText(/Justificación: Nombre explícito de identificador/)).toBeInTheDocument();
  });

  it("representa opcionales ausentes y columnas sin entrada sin inventar valores", async () => {
    const result = clone();
    result.summary.data_dictionary.entries = [{ column_name: "id", source: "inferred" }];
    delete result.warnings;
    await load(result);
    expect(row("id").getByText("Confianza: No evaluada")).toBeInTheDocument();
    expect(row("id").queryByText("Campos inferidos")).not.toBeInTheDocument();
    expect(row("amount").getByText("Int64")).toBeInTheDocument();
    expect(row("amount").getByText("Fuente: No disponible")).toBeInTheDocument();
    expect(row("amount").getAllByText("No disponible").length).toBeGreaterThan(0);
  });

  it("informa diccionario vacío y conserva únicamente los tipos observados", async () => {
    const result = clone();
    result.summary.data_dictionary.entries = [];
    await load(result);
    expect(screen.getByRole("status")).toHaveTextContent("No existen metadatos disponibles");
    expect(screen.getByRole("button", { name: "Descargar diccionario JSON" })).toBeDisabled();
    expect(screen.getAllByRole("rowheader")).toHaveLength(3);
  });

  it("tolera colecciones opcionales vacías según el contrato generado", async () => {
    const result = clone();
    delete result.profile.columns;
    delete result.summary.data_dictionary.entries;
    await load(result);
    expect(screen.getByRole("status")).toHaveTextContent("No existen metadatos disponibles");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("presenta advertencias locales y globales existentes en español", async () => {
    const result = clone();
    result.profile.columns![0].warnings = ["Identifier candidate is not unique; it may be a foreign key, not a primary key."];
    await load(result);
    expect(row("id").getByText(/El identificador candidato no es único/)).toBeInTheDocument();
    expect(screen.getByText("La columna «unused» del diccionario no existe en el archivo y fue excluida.")).toBeInTheDocument();
  });

  it("descarga exactamente el diccionario activo con nulos y procedencia sin mutar el contrato", async () => {
    const result = clone();
    const original = clone();
    let blob!: Blob;
    const createUrl = vi.fn((value: Blob) => { blob = value; return "blob:dictionary"; });
    const revokeUrl = vi.fn();
    vi.stubGlobal("URL", Object.assign(class extends URL {}, { createObjectURL: createUrl, revokeObjectURL: revokeUrl }));
    let filename = "";
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) { filename = this.download; });
    await load(result);
    fireEvent.click(screen.getByRole("button", { name: "Descargar diccionario JSON" }));
    const content = await new Promise<string>((resolve) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.readAsText(blob);
    });
    expect(JSON.parse(content)).toEqual(result.summary.data_dictionary);
    expect(filename).toBe("sales.dictionary.json");
    expect(blob.type).toBe("application/json");
    expect(createUrl).toHaveBeenCalledTimes(1);
    expect(revokeUrl).toHaveBeenCalledWith("blob:dictionary");
    expect(result).toEqual(original);
    expect(document.querySelector('a[download]')).toBeNull();
  });

  it("permite reintentar un error real de descarga", async () => {
    const createUrl = vi.fn().mockImplementationOnce(() => { throw new Error("local failure"); }).mockReturnValue("blob:dictionary");
    vi.stubGlobal("URL", Object.assign(class extends URL {}, { createObjectURL: createUrl, revokeObjectURL: vi.fn() }));
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    await load();
    fireEvent.click(screen.getByRole("button", { name: "Descargar diccionario JSON" }));
    expect(screen.getByRole("alert")).toHaveTextContent("No se pudo descargar el diccionario");
    fireEvent.click(screen.getByRole("button", { name: "Descargar diccionario JSON" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("retira el dataset anterior durante la carga y muestra el nuevo al finalizar", async () => {
    await load();
    let resolve!: (value: Response) => void;
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((done) => { resolve = done; })));
    fireEvent.click(screen.getByRole("button", { name: "Cargar en prueba" }));
    expect(screen.getByRole("status")).toHaveTextContent("Preparando el diccionario");
    expect(screen.queryByRole("rowheader", { name: "amount" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Descargar diccionario JSON" })).not.toBeInTheDocument();
    const next = clone();
    next.filename = "nuevo.tsv";
    next.profile = { dataset_id: "second-dataset", row_count: 2, columns: [{ column_name: "nueva_columna", data_type: "string" }] };
    next.summary.data_dictionary.entries = [{ column_name: "nueva_columna", source: "manual", description: "Nueva descripción" }];
    await act(async () => resolve(response(next)));
    expect(await screen.findByRole("rowheader", { name: "nueva_columna" })).toBeInTheDocument();
    expect(screen.queryByText("Total amount")).not.toBeInTheDocument();
    expect(screen.getByText("nuevo.tsv")).toBeInTheDocument();
  });

  it("limpia el diccionario al reiniciar el proveedor", async () => {
    await load();
    fireEvent.click(screen.getByRole("button", { name: "Reiniciar en prueba" }));
    expect(screen.getByRole("heading", { name: "Aún no hay dataset" })).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("muestra la ruta directa sin estado y el reinicio desde la navegación real", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(clone())));
    render(<MemoryRouter initialEntries={["/dictionary"]}><App /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "Aún no hay dataset" })).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Ir a Nuevo análisis" }));
    await user.upload(screen.getByLabelText("Archivo del dataset", { exact: true }), new File(["a\n1"], "sales.csv"));
    await user.click(screen.getByRole("button", { name: "Comprender dataset" }));
    await screen.findByRole("heading", { name: "Resumen del dataset" });
    await user.click(screen.getByRole("link", { name: "Diccionario de datos" }));
    await user.click(screen.getAllByRole("button", { name: "Nuevo análisis" })[0]);
    await user.click(screen.getByRole("link", { name: "Diccionario de datos" }));
    expect(screen.getByRole("heading", { name: "Aún no hay dataset" })).toBeInTheDocument();
  });

  it("ante carga fallida no muestra metadatos previos y ofrece recuperar el flujo", async () => {
    await load();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: { message: "Archivo inválido" } }), { status: 400, headers: { "X-Request-ID": "aud011-error" } })));
    fireEvent.click(screen.getByRole("button", { name: "Cargar en prueba" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("La carga del dataset falló");
    expect(screen.getByRole("alert")).toHaveTextContent("aud011-error");
    expect(screen.getByRole("link", { name: "Revisar carga" })).toHaveAttribute("href", "/");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("descarta una respuesta que llega después de reiniciar", async () => {
    let resolve!: (value: Response) => void;
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((done) => { resolve = done; })));
    renderDictionary();
    fireEvent.change(screen.getByLabelText("Dataset de prueba"), { target: { files: [new File(["a\n1"], "test.csv")] } });
    fireEvent.click(screen.getByRole("button", { name: "Cargar en prueba" }));
    fireEvent.click(screen.getByRole("button", { name: "Reiniciar en prueba" }));
    await act(async () => resolve(response(clone())));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Aún no hay dataset" })).toBeInTheDocument());
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("conserva nombres largos y muestra contenido no confiable como texto", async () => {
    const result = clone();
    const name = "columna_con_nombre_muy_largo_".repeat(8);
    result.profile.columns![0].column_name = name;
    result.summary.data_dictionary.entries![0] = { column_name: name, source: "manual", semantic_type: "__proto__", description: '<img src=x onerror="alert(1)">', inference_reason: "__proto__" };
    await load(result);
    expect(screen.getByRole("rowheader", { name })).toHaveTextContent(name);
    expect(row(name).getByText('<img src=x onerror="alert(1)">')).toBeInTheDocument();
    expect(row(name).getByText("__proto__", { exact: true })).toBeInTheDocument();
    expect(document.querySelector(".dictionary-table img")).toBeNull();
  });
});
