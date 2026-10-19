import { expect, test } from "@playwright/test";
import { traceFixture } from "../src/test/trace-fixture";

test("real report preserves calls, stage measurements and identity across Report, Metrics and Trace", async ({ page }) => {
  await page.goto("/trace");
  await expect(page.getByRole("heading", { name: "Sin reporte disponible" })).toBeVisible();
  await page.getByRole("button", { name: "Nuevo análisis", exact: true }).first().click();
  await page.getByLabel("Archivo del dataset", { exact: true }).setInputFiles({
    name: "trace.csv", mimeType: "text/csv", buffer: Buffer.from("x,y\n1,2\n3,4\n"),
  });
  await page.getByRole("button", { name: "Comprender dataset", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Resumen del dataset" })).toBeVisible();
  await page.getByRole("link", { name: "Hallazgos", exact: true }).click();
  const responseEvent = page.waitForResponse((response) => response.url().includes("/analysis/datasets/") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Generar reporte", exact: true }).click();
  const report = await (await responseEvent).json();
  for (const name of ["Métricas", "Traza", "Hallazgos", "Traza"]) {
    await page.getByRole("link", { name, exact: true }).click();
    await expect(page.getByText(`Ejecución: ${report.run_id}`, { exact: true })).toBeVisible();
    await expect(page.getByText(`Dataset del reporte: ${report.dataset_profile.dataset_id}`, { exact: true })).toBeVisible();
    await expect(page.getByText("Este reporte corresponde al dataset activo.")).toBeVisible();
  }
  const entries = page.getByRole("region", { name: "Entradas de la traza" });
  await expect(entries.locator("tbody tr")).toHaveCount(report.execution_trace.length);
  for (const [index, event] of report.execution_trace.entries()) {
    const row = entries.locator("tbody tr").nth(index);
    await expect(row.locator("th")).toHaveText(String(index + 1));
    await expect(row.locator("td").nth(0)).toHaveText(event.kind);
    await expect(row.locator("td").nth(2)).toContainText(event.status);
    await expect(row.locator("td").nth(3)).toHaveText(`${event.duration_seconds} s`);
  }
  const stages = page.getByRole("region", { name: "Información de etapas" });
  await expect(stages.locator("tbody tr")).toHaveCount(new Set([
    ...Object.keys(report.stage_statuses), ...Object.keys(report.stage_durations),
  ]).size);
  for (const [stage, duration] of Object.entries(report.stage_durations)) {
    const row = stages.getByRole("row").filter({ has: page.getByRole("rowheader", { name: `(${stage})`, exact: false }) });
    await expect(row).toContainText(`${duration} s`);
    if (report.stage_statuses[stage]) await expect(row).toContainText(report.stage_statuses[stage]);
  }
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  await page.getByRole("button", { name: "Nuevo análisis", exact: true }).first().click();
  await page.getByRole("link", { name: "Traza", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Sin reporte disponible" })).toBeVisible();
  await expect(page.getByRole("table")).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Sin reporte disponible" })).toBeVisible();
});

test("reset during recovery cannot restore a late trace", async ({ page }) => {
  let release!: () => void;
  const held = new Promise<void>((done) => { release = done; });
  let completed!: () => void;
  const handled = new Promise<void>((done) => { completed = done; });
  await page.route(`**/api/reports/${traceFixture.run_id}`, async (route) => {
    await held;
    try { await route.fulfill({ json: traceFixture }); } finally { completed(); }
  });
  await page.goto("/report");
  await page.getByLabel("ID de ejecución").fill(traceFixture.run_id);
  const requested = page.waitForRequest(`**/api/reports/${traceFixture.run_id}`);
  await page.getByRole("button", { name: "Consultar", exact: true }).click();
  await requested;
  await page.getByRole("link", { name: "Traza", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Solicitud de reporte pendiente");
  await page.getByRole("button", { name: "Nuevo análisis", exact: true }).first().click();
  await page.getByRole("link", { name: "Traza", exact: true }).click();
  release();
  await handled;
  await expect(page.getByRole("heading", { name: "Sin reporte disponible" })).toBeVisible();
  await expect(page.getByRole("table")).toHaveCount(0);
});
