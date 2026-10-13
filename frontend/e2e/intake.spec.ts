import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

test("real CSV upload, profile download and responsive layout", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Analyze your data" })).toBeVisible();
  if (process.env.UI_SCREENSHOT_DIR) {
    await page.screenshot({ path: join(process.env.UI_SCREENSHOT_DIR, "intake-desktop.png"), fullPage: true });
  }
  await page.getByLabel("Dataset file", { exact: true }).setInputFiles(
    fileURLToPath(new URL("../../tests/fixtures/sample.csv", import.meta.url)),
  );
  await page.getByRole("button", { name: "Understand Dataset", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Dataset Overview" })).toBeVisible();
  await expect(page.getByText("Intake completed", { exact: true })).toBeVisible();
  await expect(page.getByRole("cell", { name: "age", exact: true })).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download profile" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("sample.profile.json");
  const profile = JSON.parse(await readFile((await download.path())!, "utf8"));
  expect(profile.row_count).toBe(3);
  expect(profile.columns.map((column: { semantic_type: string }) => column.semantic_type))
    .toEqual(["numeric", "numeric", "categorical"]);
  for (const width of [1440, 1024, 480]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.evaluate(() => window.scrollTo(0, 0));
    await expect(page.getByRole("heading", { name: "Dataset Overview" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    if (process.env.UI_SCREENSHOT_DIR) {
      await page.screenshot({ path: join(process.env.UI_SCREENSHOT_DIR, `dataset-${width}.png`), fullPage: true });
    }
  }
  expect(errors).toEqual([]);
});
