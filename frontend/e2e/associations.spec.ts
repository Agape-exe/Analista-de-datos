import { expect, test } from "./api-diagnostics";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

test("associations computed by the real backend are ranked and drawn", async ({ page }) => {
  test.setTimeout(90_000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.getByLabel("Archivo del dataset", { exact: true }).setInputFiles(
    fileURLToPath(new URL("../../tests/fixtures/associations.csv", import.meta.url)),
  );
  await page.getByRole("button", { name: "Comprender dataset", exact: true }).click();
  await page.getByRole("link", { name: "Explorar asociaciones" }).click();
  await expect(page.getByRole("heading", { name: "Asociaciones", exact: true })).toBeVisible();
  const table = page.getByRole("region", { name: "Relaciones ordenadas" });
  await expect(table.getByText("MONTO_DEVENGADO ↔ MONTO_GIRADO")).toBeVisible();
  await expect(page.getByRole("figure", { name: /Diagrama de dispersión de MONTO_GIRADO frente a MONTO_DEVENGADO/ })).toBeVisible();
  await expect(page.getByRole("figure", { name: /Matriz de correlación/ })).toBeVisible();
  await expect(page.getByRole("figure", { name: /Histograma de/ })).toBeVisible();
  await page.getByRole("button", { name: /Ver MONTO_DEVENGADO y SECTOR|Ver SECTOR y MONTO_DEVENGADO/ }).click();
  await expect(page.getByRole("figure", { name: "Diagrama de caja de MONTO_DEVENGADO por SECTOR" })).toBeVisible();
  for (const width of [1440, 1024, 480]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.evaluate(() => window.scrollTo(0, 0));
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    if (process.env.UI_SCREENSHOT_DIR) {
      await page.screenshot({ path: join(process.env.UI_SCREENSHOT_DIR, `associations-${width}.png`), fullPage: true });
    }
  }
  expect(errors).toEqual([]);
});
