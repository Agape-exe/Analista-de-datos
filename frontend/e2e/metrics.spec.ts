import { expect, test } from "@playwright/test";
import { reportFixture } from "../src/test/report-fixture";

test("real report metrics preserve dataset identity across navigation and reset", async ({ page }) => {
  test.setTimeout(60_000);
  await page.goto("/metrics");
  await expect(page.getByRole("heading", { name: "Sin reporte disponible" })).toBeVisible();
  await page.getByRole("button", { name: "Nuevo análisis", exact: true }).first().click();
  await page.getByLabel("Archivo del dataset", { exact: true }).setInputFiles({
    name: "metrics.csv", mimeType: "text/csv", buffer: Buffer.from("x,y\n1,2\n3,4\n"),
  });
  await page.getByRole("button", { name: "Comprender dataset", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Resumen del dataset" })).toBeVisible();
  await page.getByRole("link", { name: "Hallazgos", exact: true }).click();
  const responseEvent = page.waitForResponse((response) => response.url().includes("/analysis/datasets/") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Generar reporte", exact: true }).click();
  const report = await (await responseEvent).json();
  await page.getByRole("link", { name: "Métricas", exact: true }).click();
  await expect(page.getByText(`Ejecución: ${report.run_id}`, { exact: true })).toBeVisible();
  await expect(page.getByText(`Dataset del reporte: ${report.dataset_profile.dataset_id}`, { exact: true })).toBeVisible();
  await expect(page.getByText("Este reporte corresponde al dataset activo.")).toBeVisible();
  const measurements = page.getByRole("region", { name: "Métricas del reporte" });
  await expect(measurements.getByRole("row", { name: `Llamadas al LLM ${report.metrics.llm_calls} llamadas`, exact: true })).toBeVisible();
  await expect(measurements.getByRole("row", { name: "Tokens usados No disponible tokens", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Resumen", exact: true }).click();
  await page.getByRole("link", { name: "Métricas", exact: true }).click();
  await expect(page.getByText(`Ejecución: ${report.run_id}`, { exact: true })).toBeVisible();
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  await page.getByRole("button", { name: "Nuevo análisis", exact: true }).first().click();
  await page.getByRole("link", { name: "Métricas", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Sin reporte disponible" })).toBeVisible();
  await expect(page.getByText(`Ejecución: ${report.run_id}`, { exact: true })).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Sin reporte disponible" })).toBeVisible();
});

test("pending recovery and a late response cannot repopulate metrics after New Analysis", async ({ page }) => {
  let release!: () => void;
  const held = new Promise<void>((done) => { release = done; });
  let completed!: () => void;
  const handled = new Promise<void>((done) => { completed = done; });
  await page.route(`**/api/reports/${reportFixture.run_id}`, async (route) => {
    await held;
    try { await route.fulfill({ json: reportFixture }); } finally { completed(); }
  });
  await page.goto("/report");
  await page.getByLabel("ID de ejecución").fill(reportFixture.run_id);
  const requested = page.waitForRequest(`**/api/reports/${reportFixture.run_id}`);
  await page.getByRole("button", { name: "Consultar", exact: true }).click();
  await requested;
  await page.getByRole("link", { name: "Métricas", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Solicitud de reporte pendiente");
  await page.getByRole("button", { name: "Nuevo análisis", exact: true }).first().click();
  await page.getByRole("link", { name: "Métricas", exact: true }).click();
  release();
  await handled;
  await expect(page.getByRole("heading", { name: "Sin reporte disponible" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Métricas del reporte" })).toHaveCount(0);
});
