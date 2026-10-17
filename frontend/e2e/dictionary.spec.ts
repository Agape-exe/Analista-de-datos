import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

test("AUD-011: CSV y TSV reales, procedencia, descarga, cambio, reinicio y diseño adaptable", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/dictionary");
  await expect(page.getByRole("heading", { name: "Aún no hay dataset" })).toBeVisible();
  await page.getByRole("link", { name: "Ir a Nuevo análisis" }).click();
  const columnName = "importe_de_ventas_con_un_nombre_de_columna_muy_largo_".repeat(3);
  await page.getByLabel("Archivo del dataset", { exact: true }).setInputFiles({
    name: "ventas.csv", mimeType: "text/csv", buffer: Buffer.from(`${columnName},segmento\n10,A\n20,B\n`),
  });
  await page.getByLabel("Archivo del diccionario de datos").setInputFiles({
    name: "metadatos.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify({ entries: [
      { column_name: columnName, source: "official", data_type: "integer", description: "Importe de ventas declarado", unit: "PEN", confidence: 0.9 },
    ] })),
  });
  await page.getByRole("button", { name: "Comprender dataset", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Resumen del dataset" })).toBeVisible();
  await page.getByRole("link", { name: "Diccionario de datos", exact: true }).click();
  const table = page.getByRole("region", { name: "Diccionario de datos por columna" });
  await expect(table.getByRole("rowheader", { name: columnName, exact: true })).toBeVisible();
  await expect(table.getByRole("cell").filter({ hasText: "Importe de ventas declarado" })).toContainText("Importe de ventas declarado");
  await expect(table.getByText("Fuente: Oficial", { exact: true })).toHaveText("Fuente: Oficial");
  await expect(table.getByText("Confianza: 90%", { exact: true })).toHaveText("Confianza: 90%");

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Descargar diccionario JSON" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("ventas.dictionary.json");
  const dictionary = JSON.parse(await readFile((await download.path())!, "utf8"));
  expect(Object.keys(dictionary)).toEqual(["entries"]);
  expect(dictionary.entries[0]).toMatchObject({ column_name: columnName, source: "official", data_type: "integer", description: "Importe de ventas declarado", unit: "PEN", confidence: 0.9, inferred_fields: ["semantic_type"] });
  expect(dictionary.entries[1]).toMatchObject({ column_name: "segmento", source: "inferred", confidence: null });
  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await expect(page.getByRole("heading", { name: "Diccionario de datos", exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    expect(await table.evaluate((element) => element.scrollWidth > element.clientWidth)).toBe(true);
    if (process.env.UI_SCREENSHOT_DIR) await page.screenshot({ path: join(process.env.UI_SCREENSHOT_DIR, `dictionary-${width}.png`), fullPage: true });
  }
  await page.getByRole("button", { name: "Nuevo análisis", exact: true }).first().click();
  await page.getByRole("link", { name: "Diccionario de datos", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Aún no hay dataset" })).toBeVisible();
  await page.getByRole("link", { name: "Ir a Nuevo análisis" }).click();
  await page.getByLabel("Archivo del dataset", { exact: true }).setInputFiles({
    name: "nuevo.tsv", mimeType: "text/tab-separated-values", buffer: Buffer.from("codigo\tvalor_nuevo\n001\t4\n002\t8\n"),
  });
  await page.getByRole("button", { name: "Comprender dataset", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Resumen del dataset" })).toBeVisible();
  await page.getByRole("link", { name: "Diccionario de datos", exact: true }).click();
  await expect(table.getByRole("rowheader", { name: "valor_nuevo", exact: true })).toBeVisible();
  await expect(table.getByRole("rowheader", { name: columnName, exact: true })).toHaveCount(0);
  const nextDownloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Descargar diccionario JSON" }).click();
  const nextDownload = await nextDownloadPromise;
  expect(nextDownload.suggestedFilename()).toBe("nuevo.dictionary.json");
  const nextDictionary = JSON.parse(await readFile((await nextDownload.path())!, "utf8"));
  expect(nextDictionary.entries.map((entry: { column_name: string }) => entry.column_name)).toEqual(["codigo", "valor_nuevo"]);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Aún no hay dataset" })).toBeVisible();
  expect(errors).toEqual([]);
});
