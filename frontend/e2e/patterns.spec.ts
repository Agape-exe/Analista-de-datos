import { expect, test } from "@playwright/test";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

test("patterns summarise existing groups computed by the real backend", async ({ page }) => {
  test.setTimeout(90_000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.getByLabel("Archivo del dataset", { exact: true }).setInputFiles(
    fileURLToPath(new URL("../../tests/fixtures/associations.csv", import.meta.url)),
  );
  await page.getByRole("button", { name: "Comprender dataset", exact: true }).click();
  await page.getByRole("link", { name: "Patrones" }).click();
  await expect(page.getByRole("heading", { name: "Patrones por grupo" })).toBeVisible();
  await expect(page.getByText("Los grupos son categorías existentes, no clusters.")).toBeVisible();
  const table = page.getByRole("region", { name: "Tabla de grupos" });
  await expect(table.getByRole("rowheader").first()).toBeVisible();
  await expect(page.getByRole("figure", { name: /Distribución de .+ por cada categoría de/ })).toBeVisible();
  for (const width of [1440, 1024, 480]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.evaluate(() => window.scrollTo(0, 0));
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    if (process.env.UI_SCREENSHOT_DIR) {
      await page.screenshot({ path: join(process.env.UI_SCREENSHOT_DIR, `patterns-${width}.png`), fullPage: true });
    }
  }
  expect(errors).toEqual([]);
});
