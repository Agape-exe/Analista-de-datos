import { expect, test } from "@playwright/test";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

test("AUD-017: anomalies from the real backend with thresholds, boxplot and exact records", async ({ page }) => {
  test.setTimeout(90_000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.getByLabel("Archivo del dataset", { exact: true }).setInputFiles(
    fileURLToPath(new URL("../../tests/fixtures/associations.csv", import.meta.url)),
  );
  await page.getByRole("button", { name: "Comprender dataset", exact: true }).click();
  await expect(page.getByRole("link", { name: "Explorar asociaciones" })).toBeVisible();
  await page.getByRole("link", { name: "Anomalías", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Valores atípicos" })).toBeVisible();
  await expect(page.getByText("Un valor atípico no es necesariamente un error.")).toBeVisible();
  await expect(page.getByRole("region", { name: "Atípicos por columna" }).getByRole("rowheader").first()).toBeVisible();
  await expect(page.getByRole("region", { name: "Criterio IQR" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Criterio MAD" })).toContainText("|z robusto|");
  await expect(page.getByRole("figure", { name: /Diagrama de caja de/ })).toBeVisible();

  const examples = page.getByRole("region", { name: "Registros de ejemplos atípicos" });
  const first = examples.getByRole("row").nth(1);
  const reference = (await first.getByRole("rowheader").textContent())!;
  const value = (await first.getByRole("cell").first().textContent())!;
  await first.getByRole("button", { name: /Ver registro/ }).click();
  const record = page.getByLabel(`Valores de ${reference}`);
  await expect(record).toBeVisible();
  const analysed = record.locator(".analysed dd");
  expect(Number((await analysed.textContent())!)).toBeCloseTo(Number(value.replace(/,/g, "")), 4);

  for (const width of [1440, 1024, 480]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.evaluate(() => window.scrollTo(0, 0));
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    if (process.env.UI_SCREENSHOT_DIR) {
      await page.screenshot({ path: join(process.env.UI_SCREENSHOT_DIR, `anomalies-${width}.png`), fullPage: true });
    }
  }
  expect(errors).toEqual([]);
});
