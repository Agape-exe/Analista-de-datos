import { expect, test } from "@playwright/test";

test("member 5 real upload preserves pending stages and retrieves report", async ({ page }) => {
  await page.goto("/report");
  await page.getByLabel("Dataset del reporte").setInputFiles({
    name: "sample.csv", mimeType: "text/csv", buffer: Buffer.from("x,y\n1,2\n3,4\n"),
  });
  await page.getByRole("button", { name: "Generar reporte" }).click();
  await expect(page.getByRole("heading", { name: "Estado: SKIPPED" })).toBeVisible();
  await expect(page.getByText("No hay insights respaldados por evidencia disponibles.")).toBeVisible();
  const id = await page.getByLabel("ID de ejecución").inputValue();
  expect(id).toBeTruthy();
  const downloadEvent = page.waitForEvent("download");
  await page.getByRole("link", { name: "Descargar informe" }).click();
  expect((await downloadEvent).suggestedFilename()).toBe("analysis-report.md");
  await page.getByRole("button", { name: "Consultar", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Estado: SKIPPED" })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
