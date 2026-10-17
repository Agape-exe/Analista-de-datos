import { expect, test } from "@playwright/test";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

test("associations computed by the real backend are ranked and drawn", async ({ page }) => {
  test.setTimeout(90_000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.getByLabel("Dataset file", { exact: true }).setInputFiles(
    fileURLToPath(new URL("../../tests/fixtures/associations.csv", import.meta.url)),
  );
  await page.getByRole("button", { name: "Understand Dataset", exact: true }).click();
  await page.getByRole("link", { name: "Explore Associations" }).click();
  await expect(page.getByRole("heading", { name: "Associations", exact: true })).toBeVisible();
  const table = page.getByRole("region", { name: "Ranked relationships" });
  await expect(table.getByText("MONTO_DEVENGADO ↔ MONTO_GIRADO")).toBeVisible();
  await expect(page.getByRole("figure", { name: /Scatter plot of MONTO_GIRADO against MONTO_DEVENGADO/ })).toBeVisible();
  await expect(page.getByRole("figure", { name: /correlation matrix/ })).toBeVisible();
  await expect(page.getByRole("figure", { name: /Histogram of/ })).toBeVisible();
  await page.getByRole("button", { name: /View MONTO_DEVENGADO and SECTOR|View SECTOR and MONTO_DEVENGADO/ }).click();
  await expect(page.getByRole("figure", { name: "Box plot of MONTO_DEVENGADO by SECTOR" })).toBeVisible();
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
