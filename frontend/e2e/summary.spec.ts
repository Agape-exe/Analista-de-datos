import { expect, test } from "@playwright/test";

test("AUD-037: summary reuses active intake, separates reports, and resets at root", async ({ page }, testInfo) => {
  await page.goto("/summary");
  await expect(page.getByRole("heading", { name: "Sin dataset activo" })).toBeVisible();
  await page.getByRole("link", { name: "Ir a Nuevo análisis", exact: true }).click();
  await page.getByLabel("Archivo del dataset", { exact: true }).setInputFiles({
    name: "summary.csv", mimeType: "text/csv", buffer: Buffer.from("x,y\n1,2\n3,4\n"),
  });
  await page.getByRole("button", { name: "Comprender dataset", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Resumen del dataset" })).toBeVisible();
  const extraRequests: string[] = [];
  page.on("request", (request) => { if (request.url().includes("/api/")) extraRequests.push(request.url()); });
  await page.getByRole("link", { name: "Resumen", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Dataset activo" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Indicadores del dataset activo" })).toContainText("Filas");
  await expect(page.getByRole("heading", { name: "Sin análisis compatible completado" })).toBeVisible();
  expect(extraRequests).toEqual([]);
  await page.getByRole("link", { name: "Ir a Hallazgos", exact: true }).click();
  await page.getByRole("button", { name: "Generar reporte", exact: true }).click();
  // A question-free analysis is intentionally SKIPPED; its metrics must remain unavailable.
  await expect(page.getByRole("heading", { name: "Estado: Pendiente" })).toBeVisible();
  await page.getByRole("link", { name: "Resumen", exact: true }).click();
  await expect(page.getByText(/El análisis tiene etapas pendientes/)).toBeVisible();
  await expect(page.getByRole("region", { name: "Indicadores del análisis compatible" }).getByText("Sin medición disponible")).toHaveCount(4);
  await page.route("**/api/reports/historical-summary", (route) => route.fulfill({ json: {
    run_id: "historical-summary", status: "SUCCESS", metrics: { tool_calls: 987654 }, insights: [],
    dataset_profile: { dataset_id: "other-dataset", row_count: 999, columns: [] },
  } }));
  await page.getByRole("link", { name: "Ir a Hallazgos", exact: true }).click();
  await page.getByLabel("ID de ejecución").fill("historical-summary");
  await page.getByRole("button", { name: "Consultar", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Reporte recuperado" })).toBeVisible();
  await page.getByRole("link", { name: "Resumen", exact: true }).click();
  await expect(page.getByText(/Pertenece a otro dataset/)).toBeVisible();
  await expect(page.getByRole("region", { name: "Indicadores del análisis compatible" })).not.toContainText("987");
  await page.screenshot({ path: testInfo.outputPath("summary-desktop.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("summary-mobile.png"), fullPage: true });
  await page.getByRole("button", { name: "Nuevo análisis", exact: true }).first().click();
  await expect(page).toHaveURL(/\/$/);
  await page.getByRole("link", { name: "Resumen", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Sin dataset activo" })).toBeVisible();
  await expect(page.getByText(/historical-summary/)).toHaveCount(0);
});
