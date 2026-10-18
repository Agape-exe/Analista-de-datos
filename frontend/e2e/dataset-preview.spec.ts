import { expect, test } from "@playwright/test";
import { join } from "node:path";

test("AUD-010: CSV real, endpoint preview, paginación, nulos, teclado y diseño adaptable", async ({ page }) => {
  const errors: string[] = [];
  const requests: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => { if (request.url().includes("/preview?")) requests.push(request.url()); });
  await page.goto("/dataset");
  await expect(page.getByRole("heading", { name: "Aún no hay dataset" })).toBeVisible();
  expect(requests).toHaveLength(0);
  await page.getByRole("link", { name: "Subir dataset" }).click();
  const column = "codigo_con_nombre_largo_".repeat(5);
  const rows = Array.from({ length: 45 }, (_, index) => `${String(index + 1).padStart(3, "0")},${index + 0.5},${index % 2 === 0},${index === 1 ? "" : index === 2 ? "null" : "nota"}`);
  await page.getByLabel("Archivo del dataset", { exact: true }).setInputFiles({
    name: "preview.csv", mimeType: "text/csv", buffer: Buffer.from(`${column},importe,activo,nota\n${rows.join("\n")}\n`),
  });
  const previewResponse = page.waitForResponse((response) => response.url().includes("/preview?") && response.request().method() === "GET");
  await page.getByRole("button", { name: "Comprender dataset", exact: true }).click();
  const first = await previewResponse;
  expect(first.status()).toBe(200);
  const json = await first.json();
  expect(first.url()).toContain(`/datasets/${json.dataset_id}/preview?offset=0&limit=20`);
  expect(json.rows).toHaveLength(20);
  await expect(page.getByText("Filas 1–20 de 45 · 20 registros mostrados")).toBeVisible();
  const region = page.getByRole("region", { name: "Filas del dataset" });
  await expect(region.getByRole("columnheader", { name: `${column} string` })).toBeVisible();
  await expect(region.getByRole("cell", { name: "001", exact: true })).toBeVisible();
  await expect(region.getByRole("cell", { name: "Sin dato", exact: true })).toBeVisible();
  await expect(region.getByRole("cell", { name: "null", exact: true })).toBeVisible();
  expect(requests).toHaveLength(1);
  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await region.scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    if (process.env.UI_SCREENSHOT_DIR) {
      await page.locator(".preview-card").screenshot({ path: join(process.env.UI_SCREENSHOT_DIR, `dataset-preview-${width}.png`) });
      if (width === 1440 || width === 390) await page.screenshot({ path: join(process.env.UI_SCREENSHOT_DIR, `dataset-screen-${width}.png`), fullPage: true });
    }
  }
  await region.focus();
  await page.keyboard.press("ArrowRight");
  await expect.poll(() => region.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("button", { name: "Siguiente", exact: true }).click();
  await expect(page.getByText("Filas 21–40 de 45 · 20 registros mostrados")).toBeVisible();
  await expect(region.getByRole("cell", { name: "001", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Siguiente", exact: true }).click();
  await expect(page.getByText("Filas 41–45 de 45 · 5 registros mostrados")).toBeVisible();
  await expect(page.getByRole("button", { name: "Siguiente", exact: true })).toBeDisabled();
  expect(requests).toHaveLength(3);
  if (process.env.UI_SCREENSHOT_DIR) await page.locator(".preview-card").screenshot({ path: join(process.env.UI_SCREENSHOT_DIR, "dataset-preview-last.png") });
  await page.getByRole("button", { name: "Anterior", exact: true }).click();
  await expect(page.getByText("Filas 21–40 de 45 · 20 registros mostrados")).toBeVisible();
  await page.getByLabel("Filas por página").selectOption("10");
  await expect(page.getByText("Filas 1–10 de 45 · 10 registros mostrados")).toBeVisible();
  expect(requests).toHaveLength(5);
  await expect(page.getByRole("heading", { name: "Comprensión de columnas" })).toBeVisible();
  await page.getByRole("link", { name: "Diccionario de datos", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Metadatos por columna" })).toBeVisible();
  await page.getByRole("button", { name: "Nuevo análisis", exact: true }).first().click();
  await page.getByRole("link", { name: "Dataset", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Aún no hay dataset" })).toBeVisible();
  expect(requests).toHaveLength(5);
  expect(errors).toEqual([]);
});

test("AUD-010: TSV real, precisión numérica, recuperación de conexión y límite de página", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Archivo del dataset", { exact: true }).setInputFiles({
    name: "precision.tsv", mimeType: "text/tab-separated-values",
    buffer: Buffer.from("codigo\tentero\n001\t9007199254740993\n002\t9007199254740994\n"),
  });
  let intercept = "network";
  await page.route("**/datasets/*/preview?*", async (route) => {
    if (intercept === "network") { intercept = "real"; await route.abort("failed"); }
    else if (intercept === "large") {
      intercept = "real";
      await route.fulfill({ status: 413, contentType: "application/json", body: JSON.stringify({ detail: { code: "PREVIEW_TOO_LARGE", message: "Too large" } }) });
    } else await route.continue();
  });
  await page.getByRole("button", { name: "Comprender dataset", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("No se puede conectar con el servidor");
  if (process.env.UI_SCREENSHOT_DIR) await page.locator(".preview-card").screenshot({ path: join(process.env.UI_SCREENSHOT_DIR, "dataset-preview-network-error.png") });
  const realResponse = page.waitForResponse((response) => response.url().includes("/preview?") && response.status() === 200);
  await page.getByRole("button", { name: "Reintentar", exact: true }).click();
  expect(await (await realResponse).text()).toContain("9007199254740993");
  await expect(page.getByRole("region", { name: "Filas del dataset" }).getByText("Precisión no garantizada")).toHaveCount(2);
  await expect(page.getByRole("region", { name: "Filas del dataset" }).getByRole("cell", { name: "001", exact: true })).toBeVisible();
  intercept = "large";
  await page.getByLabel("Filas por página").selectOption("50");
  await expect(page.getByRole("alert")).toContainText("La página es demasiado grande");
  if (process.env.UI_SCREENSHOT_DIR) await page.locator(".preview-card").screenshot({ path: join(process.env.UI_SCREENSHOT_DIR, "dataset-preview-too-large.png") });
  await page.getByLabel("Filas por página").selectOption("10");
  await expect(page.getByText("Filas 1–2 de 2 · 2 registros mostrados")).toBeVisible();
});
