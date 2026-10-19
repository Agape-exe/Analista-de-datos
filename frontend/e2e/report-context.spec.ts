import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

// Insufficient samples deliberately exercise context without relying on Planner policy.
test("AUD-042: dataset identity, history, failed regeneration and reset", async ({ page }) => {
  test.setTimeout(60_000);
  async function upload(name: string) {
    await page.getByLabel("Archivo del dataset", { exact: true }).setInputFiles({
      name, mimeType: "text/csv", buffer: Buffer.from("x,y\n1,2\n3,4\n"),
    });
    await page.getByRole("button", { name: "Comprender dataset", exact: true }).click();
    await page.getByRole("link", { name: "Explorar asociaciones" }).waitFor();
    await page.getByRole("link", { name: "Hallazgos", exact: true }).click();
  }
  await page.goto("/");
  await upload("a.csv");
  await page.getByRole("button", { name: "Generar reporte", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Estado: Pendiente" })).toBeVisible();
  const runA = await page.getByLabel("ID de ejecución").inputValue();
  const downloadEvent = page.waitForEvent("download");
  await page.getByRole("button", { name: "Descargar JSON", exact: true }).click();
  const reportA = JSON.parse(await readFile((await (await downloadEvent).path())!, "utf8"));

  await page.getByRole("button", { name: "Nuevo análisis", exact: true }).first().click();
  await upload("b.csv");
  await page.getByLabel("ID de ejecución").fill(runA);
  await page.getByRole("button", { name: "Consultar", exact: true }).click();
  await expect(page.getByText("Este reporte pertenece a otro dataset. No describe el dataset activo.")).toBeVisible();
  await expect(page.getByText("Dataset del reporte: " + reportA.dataset_profile.dataset_id)).toBeVisible();
  await page.getByRole("button", { name: "Generar reporte", exact: true }).click();
  await expect(page.getByText("Este reporte corresponde al dataset activo.")).toBeVisible();
  const runB = await page.getByLabel("ID de ejecución").inputValue();
  expect(runB).not.toBe(runA);

  await page.route("**/api/analysis/datasets/*", (route) => route.fulfill({
    status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Service unavailable" }),
  }));
  await page.getByRole("button", { name: "Volver a generar", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("La regeneración falló");
  await expect(page.getByText("Ejecución: " + runB)).toBeVisible();
  await page.getByRole("link", { name: "Dataset", exact: true }).click();
  await page.getByRole("link", { name: "Hallazgos", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("reporte anterior");

  await page.reload();
  await page.getByLabel("ID de ejecución").fill(runA);
  await page.getByRole("button", { name: "Consultar", exact: true }).click();
  await expect(page.getByText("Consulta histórica: no hay un dataset activo asociado.")).toBeVisible();
  await page.getByRole("button", { name: "Nuevo análisis", exact: true }).first().click();
  await page.getByRole("link", { name: "Hallazgos", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Reporte recuperado" })).toHaveCount(0);
  await expect(page.getByLabel("ID de ejecución")).toHaveValue("");
});
