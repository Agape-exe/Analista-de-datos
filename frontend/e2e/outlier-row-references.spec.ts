import { expect, test, type Page } from "@playwright/test";
import { join } from "node:path";

async function capture(page: Page, name: string) {
  if (process.env.UI_SCREENSHOT_DIR) {
    await page.evaluate(() => { (document.activeElement as HTMLElement | null)?.blur(); window.scrollTo(0, 0); });
    await page.screenshot({ path: join(process.env.UI_SCREENSHOT_DIR, name), fullPage: true });
  }
}

test("AUD-018: IQR real, nulos, repeticiones y posiciones originales consistentes con preview", async ({ page }) => {
  const errors: string[] = []; page.on("pageerror", (error) => errors.push(error.message));
  const values = [null, 500, ...Array.from({ length: 41 }, (_, i) => i - 20), null, 500, -400, null];
  // A blank physical CSV line is not a dataset record.
  const csv = "code,measure\n\n" + values.map((value, i) => `r${i},${value ?? ""}`).join("\n") + "\n";
  await page.goto("/");
  await page.getByLabel("Archivo del dataset", { exact: true }).setInputFiles({ name: "outliers.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
  await page.getByRole("button", { name: "Comprender dataset", exact: true }).click();
  await expect(page.getByRole("region", { name: "Filas del dataset" })).toBeVisible();
  const outlierResponse = page.waitForResponse((r) => r.url().endsWith("/tools/outliers") && r.status() === 200);
  await page.getByRole("link", { name: "Explorar asociaciones" }).click();
  await page.getByLabel("Columna", { exact: true }).selectOption("measure");
  const real = await outlierResponse;
  const payload = await real.json();
  expect(payload.status).toBe("SUCCESS");
  expect(payload.variables).toEqual(["measure"]);
  const expected = [{ row_index: 1, value: 500 }, { row_index: 44, value: 500 }, { row_index: 45, value: -400 }];
  expect(payload.result.measure.iqr.examples).toEqual([500, 500, -400]);
  expect(payload.result.measure.iqr.example_rows).toEqual(expected);
  const region = page.getByRole("region", { name: "Ejemplos de valores atípicos", exact: true });
  await expect(region.getByRole("rowheader")).toHaveText(["Registro 2", "Registro 45", "Registro 46"]);
  await expect(region.getByRole("cell", { name: "500", exact: true })).toHaveCount(2);
  await expect(region.getByText(/puede ser una observación válida/)).toBeVisible();
  await expect(page.getByRole("link", { name: "Anomalías", exact: true })).toHaveAttribute("href", "/anomalies");
  await capture(page, "outliers-original-positions.png");
  if (process.env.UI_SCREENSHOT_DIR) {
    await region.screenshot({ path: join(process.env.UI_SCREENSHOT_DIR, "outliers-repeated-values.png") });
    await page.locator(".explorer-card").screenshot({ path: join(process.env.UI_SCREENSHOT_DIR, "outliers-column-explorer.png") });
  }
  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    if (width === 390) {
      await capture(page, "outliers-mobile.png");
      const scroll = page.getByRole("region", { name: "Registros de ejemplos IQR" });
      await scroll.focus(); await page.keyboard.press("ArrowRight");
      await expect.poll(() => scroll.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0);
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("link", { name: "Dataset", exact: true }).click();
  await page.getByLabel("Filas por página").selectOption("100");
  const preview = page.getByRole("region", { name: "Filas del dataset" });
  await expect(page.getByText("Filas 1–47 de 47 · 47 registros mostrados")).toBeVisible();
  const datasetId = real.url().split("/datasets/")[1].split("/")[0];
  const pageResponse = await page.request.get(`/api/datasets/${datasetId}/preview?offset=0&limit=100`);
  const rows = (await pageResponse.json()).rows;
  for (const example of expected) {
    expect(rows[example.row_index][1]).toBe(example.value);
    expect(rows[example.row_index][0]).toBe(`r${example.row_index}`);
    await expect(preview.getByRole("row").nth(example.row_index + 1)).toContainText(`r${example.row_index}`);
  }
  await expect(preview.getByRole("cell", { name: "Sin dato", exact: true })).toHaveCount(3);
  await capture(page, "outliers-with-missing-values.png");
  expect(errors).toEqual([]);
});

test("AUD-018: dataset sin atípicos muestra estado vacío real", async ({ page }) => {
  const errors: string[] = []; page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.getByLabel("Archivo del dataset", { exact: true }).setInputFiles({
    name: "normal.csv", mimeType: "text/csv", buffer: Buffer.from("measure\n" + Array.from({ length: 41 }, (_, i) => i - 20).join("\n")),
  });
  await page.getByRole("button", { name: "Comprender dataset", exact: true }).click();
  await expect(page.getByRole("region", { name: "Filas del dataset" })).toBeVisible();
  await page.getByRole("link", { name: "Explorar asociaciones" }).click();
  await expect(page.getByText("No se detectaron valores atípicos IQR.")).toBeVisible();
  await capture(page, "outliers-empty-state.png");
  expect(errors).toEqual([]);
});
