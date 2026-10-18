import { expect, test } from "@playwright/test";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

test("AUD-021: categorical pair shows a real contingency table with totals and warnings", async ({ page }) => {
  test.setTimeout(90_000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.getByLabel("Archivo del dataset", { exact: true }).setInputFiles(
    fileURLToPath(new URL("../../tests/fixtures/contingency.csv", import.meta.url)),
  );
  await page.getByRole("button", { name: "Comprender dataset", exact: true }).click();
  await page.getByRole("link", { name: "Explorar asociaciones" }).click();
  await page.getByRole("button", { name: /Ver (REGION y CANAL|CANAL y REGION)/ }).click();
  const table = page.getByRole("region", { name: /Tabla de contingencia de (REGION y CANAL|CANAL y REGION)/ });
  await expect(table).toBeVisible();
  await expect(page.getByText(/aún no está disponible/)).toHaveCount(0);
  const totals = table.getByRole("row").last().getByRole("cell");
  const grand = Number((await totals.last().textContent())!.replace(/,/g, ""));
  expect(grand).toBeGreaterThan(0);
  await expect(page.getByRole("list", { name: "Advertencias de la tabla de contingencia" })).toContainText("no implica que una cause la otra");
  await page.getByRole("button", { name: "% de fila" }).click();
  await expect(table.getByRole("row").nth(1).getByRole("cell").last()).toHaveText("100 %");
  for (const width of [1440, 1024, 480]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.evaluate(() => window.scrollTo(0, 0));
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    if (process.env.UI_SCREENSHOT_DIR) {
      await table.screenshot({ path: join(process.env.UI_SCREENSHOT_DIR, `contingency-${width}.png`) });
    }
  }
  expect(errors).toEqual([]);
});
