import { expect, test } from "@playwright/test";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

test("AUD-035: associations separate description, association, significance and causation", async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto("/");
  await page.getByLabel("Archivo del dataset", { exact: true }).setInputFiles(
    fileURLToPath(new URL("../../tests/fixtures/associations.csv", import.meta.url)),
  );
  await page.getByRole("button", { name: "Comprender dataset", exact: true }).click();
  await page.getByRole("link", { name: "Explorar asociaciones" }).click();
  const levels = page.getByRole("list", { name: "Cómo leer estos resultados" });
  await expect(levels).toContainText("Causalidad: nunca se infiere aquí");
  await expect(page.getByRole("region", { name: "Relaciones ordenadas" }).getByRole("columnheader", { name: "Tamaño del efecto" })).toBeVisible();
  await expect(page.getByText(/no es un modelo predictivo ni causal/)).toBeVisible();
  await expect(page.getByText(/Los valores p de la matriz no están corregidos/)).toBeVisible();
  for (const width of [1440, 480]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    if (process.env.UI_SCREENSHOT_DIR) {
      await page.locator(".candidates-note").screenshot({ path: join(process.env.UI_SCREENSHOT_DIR, `claims-${width}.png`) });
    }
  }
});
