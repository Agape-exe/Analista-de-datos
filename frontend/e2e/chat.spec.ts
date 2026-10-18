import { expect, test } from "@playwright/test";
import { reportFixture } from "../src/test/report-fixture";

const report = {
  ...reportFixture,
  run_id: "chat-e2e",
  analysis_results: [{ analysis_id: "analysis-001", method: "pearson", variables: ["x", "y"],
    status: "SUCCESS", completeness: "complete", execution_time: 0, warnings: [] }],
  evidence: [{ evidence_id: "evidence-001", analysis_id: "analysis-001", description: "Coeficiente medido" }],
};

test("AUD-044: grounded chat preserves history, navigates to evidence and resets", async ({ page }) => {
  await page.route("**/api/questions/catalog", (route) => route.fulfill({ json: { questions: {
    evidencias: "¿Qué evidencias respaldan el reporte?",
    metricas: "¿Qué métricas se midieron?",
  } } }));
  await page.route("**/api/reports/chat-e2e/questions", async (route) => {
    const body = route.request().postDataJSON();
    await route.fulfill({ json: {
      question: body.question, status: "ANSWERED", answer: "El reporte conserva una evidencia medida.",
      references: [{ path: "/evidence/0", evidence_id: "evidence-001", analysis_id: "analysis-001" }],
    } });
  });
  await page.route("**/api/reports/chat-e2e", (route) => route.fulfill({ json: report }));

  await page.goto("/report");
  await page.getByLabel("ID de ejecución").fill("chat-e2e");
  await page.getByRole("button", { name: "Consultar", exact: true }).click();
  await expect(page.getByText("Ejecución: chat-e2e", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Chat", exact: true }).click();
  await page.getByRole("button", { name: "Usar pregunta: ¿Qué evidencias respaldan el reporte?" }).click();
  await page.getByRole("button", { name: "Preguntar", exact: true }).click();
  await expect(page.getByText("El reporte conserva una evidencia medida.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Evidencia evidence-001" }))
    .toHaveAttribute("href", "/report#evidence-evidence-001");

  await page.getByRole("link", { name: "Evidencia evidence-001" }).click();
  await expect(page).toHaveURL(/\/report#evidence-evidence-001$/);
  await expect(page.getByRole("heading", { name: "evidence-001" })).toBeVisible();
  await page.getByRole("link", { name: "Chat", exact: true }).click();
  await expect(page.getByText("El reporte conserva una evidencia medida.")).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);

  await page.getByRole("button", { name: "Nuevo análisis", exact: true }).first().click();
  await page.getByRole("link", { name: "Chat", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Sin reporte disponible" })).toBeVisible();
  await expect(page.getByText("El reporte conserva una evidencia medida.")).toHaveCount(0);
});
