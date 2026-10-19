import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { expect, test } from "vitest";
import { App } from "../../app/App";

test("preserves the restored available capabilities and links to Hallazgos", async () => {
  render(<MemoryRouter><App /></MemoryRouter>);
  expect(screen.getByText("Tu dataset se procesa en el servidor con Python.")).toBeVisible();
  expect(screen.getByText("Disponible en Hallazgos")).toBeVisible();
  expect(screen.queryByText(/Herramientas estadísticas, controles y análisis multiagente en una próxima etapa/)).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/¿Qué te gustaría investigar/)).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("link", { name: "Configurar Hallazgos" }));
  expect(screen.getByRole("heading", { name: "Hallazgos y evidencia" })).toBeVisible();
});
