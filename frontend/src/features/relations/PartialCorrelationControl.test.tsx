
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";

import { runTool } from "../../lib/api-client";
import { PartialCorrelationControl } from "./PartialCorrelationControl";

// Simular las respuestas del backend durante las pruebas
vi.mock("../../lib/api-client", () => ({
  runTool: vi.fn(),
}));

const numericColumns = [
  "publicidad",
  "ventas",
  "campaña",
  "precio",
];

const variables = ["publicidad", "ventas"];

beforeEach(() => {
  vi.resetAllMocks();
});

test("requests a new persisted report explicitly without replacing the exploratory action", async () => {
  const onGenerateReport = vi.fn().mockResolvedValue(undefined);
  const user = userEvent.setup();
  const view = render(<PartialCorrelationControl datasetId="dataset-001" numericColumns={numericColumns}
    variables={variables} onGenerateReport={onGenerateReport} />);
  await user.selectOptions(screen.getByRole("combobox", { name: "Variable de control" }), "campaña");
  await user.click(screen.getByRole("button", { name: "Generar nuevo reporte con este control" }));
  expect(onGenerateReport).toHaveBeenCalledWith({ variables, control_variable: "campaña" });
  expect(runTool).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "Solicitar correlación parcial" })).toBeEnabled();
  view.rerender(<PartialCorrelationControl datasetId="dataset-001" numericColumns={numericColumns}
    variables={variables} onGenerateReport={onGenerateReport} reportLoading />);
  expect(screen.getByRole("combobox", { name: "Variable de control" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Generando reporte con control…" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Solicitar correlación parcial" })).toBeDisabled();
});

// PRUEBA 1: Enviar correctamente la variable de control
test("AUD-038: solicita correlacion parcial con el control elegido", async () => {
  const user = userEvent.setup();

  vi.mocked(runTool).mockResolvedValue({
    analysis_id: "partial-001",
    method: "partial_correlation",
    variables,
    status: "SUCCESS",
    completeness: "complete",
    result: { correlation: 0.16 },
    effect_size: 0.16,
    p_value: 0.03,
    sample_size: 100,
    execution_time: 0,
    warnings: ["La correlación no demuestra causalidad."],
  });

  render(
    <PartialCorrelationControl
      datasetId="dataset-001"
      numericColumns={numericColumns}
      variables={variables}
    />,
  );

  await user.selectOptions(
    screen.getByRole("combobox", {
      name: "Variable de control",
    }),
    "campaña",
  );

  await user.click(
    screen.getByRole("button", {
      name: "Solicitar correlación parcial",
    }),
  );

  expect(runTool).toHaveBeenCalledWith(
    "dataset-001",
    "partial_correlation",
    {
      variables: ["publicidad", "ventas"],
      parameters: {
        control_variable: "campaña",
      },
    },
    expect.any(AbortSignal),
  );

  expect(
    await screen.findByText("Coeficiente: 0.16"),
  ).toBeInTheDocument();

  expect(
    screen.getByText("Valor p: 0.03"),
  ).toBeInTheDocument();
});

// PRUEBA 2: Impedir solicitudes sin un control elegido
test("AUD-038: bloquea la solicitud sin seleccionar control", () => {
  render(
    <PartialCorrelationControl
      datasetId="dataset-001"
      numericColumns={numericColumns}
      variables={variables}
    />,
  );

  expect(
    screen.getByRole("button", {
      name: "Solicitar correlación parcial",
    }),
  ).toBeDisabled();

  expect(runTool).not.toHaveBeenCalled();
});

// PRUEBA 3: Evitar controles cuando no hay otras variables
test("AUD-038: informa cuando no existen controles disponibles", () => {
  render(
    <PartialCorrelationControl
      datasetId="dataset-001"
      numericColumns={["publicidad", "ventas"]}
      variables={variables}
    />,
  );

  expect(
    screen.getByText(/No existen variables numéricas adicionales/),
  ).toBeInTheDocument();

  expect(runTool).not.toHaveBeenCalled();
});

// PRUEBA 4: Manejar resultados no evaluables
test("AUD-038: muestra resultados omitidos sin inventar coeficientes", async () => {
  const user = userEvent.setup();

  vi.mocked(runTool).mockResolvedValue({
    analysis_id: "partial-002",
    method: "partial_correlation",
    variables,
    status: "SKIPPED",
    completeness: "partial",
    execution_time: 0,
    warnings: ["Muestra insuficiente."],
  });

  render(
    <PartialCorrelationControl
      datasetId="dataset-001"
      numericColumns={numericColumns}
      variables={variables}
    />,
  );

  await user.selectOptions(
    screen.getByRole("combobox", {
      name: "Variable de control",
    }),
    "campaña",
  );

  await user.click(
    screen.getByRole("button", {
      name: "Solicitar correlación parcial",
    }),
  );

  expect(
    await screen.findByText("El análisis no pudo completarse."),
  ).toBeInTheDocument();

  expect(
    screen.getByText("Muestra insuficiente."),
  ).toBeInTheDocument();

  expect(
    screen.queryByText(/Coeficiente:/),
  ).not.toBeInTheDocument();
});
