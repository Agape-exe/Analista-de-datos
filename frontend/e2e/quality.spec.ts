import { expect, test, type Page } from "@playwright/test";
import { join } from "node:path";

async function capture(page: Page, name: string) {
  if (process.env.UI_SCREENSHOT_DIR) {
    await page.evaluate(() => { (document.activeElement as HTMLElement | null)?.blur(); window.scrollTo(0, 0); });
    await page.screenshot({ path: join(process.env.UI_SCREENSHOT_DIR, name), fullPage: true });
  }
}
async function upload(page: Page, clean = false) {
  await page.getByLabel("Archivo del dataset", { exact: true }).setInputFiles({
    name: clean ? "clean.csv" : "quality.csv", mimeType: "text/csv",
    buffer: Buffer.from(clean ? "id,nombre,valor\n001,Ana,10\n002,Luis,20\n003,Sol,30\n" : "id,nombre,valor\n001,Ana,10\n002,Luis,\n002,Luis,\n"),
  });
  await page.getByRole("button", { name: "Comprender dataset", exact: true }).click();
  await expect(page.getByRole("region", { name: "Filas del dataset" })).toBeVisible();
}

test("AUD-014: calidad real, métricas, FAIL/PASS, navegación, teclado y diseño adaptable", async ({ page }) => {
  const errors: string[] = [], requests: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => { if (request.url().includes("/datasets/") && request.url().endsWith("/quality")) requests.push(request.url()); });
  await page.goto("/quality");
  await expect(page.getByRole("heading", { name: "Aún no hay dataset" })).toBeVisible();
  expect(requests).toHaveLength(0);
  await capture(page, "quality-no-dataset.png");
  await page.getByRole("link", { name: "Ir a Nuevo análisis" }).click();
  await upload(page);
  expect(requests).toHaveLength(0);
  const qualityResponse = page.waitForResponse((r) => r.url().endsWith("/quality") && r.request().method() === "GET");
  await page.getByRole("link", { name: "Ver calidad de datos" }).click();
  const real = await qualityResponse;
  expect(real.status()).toBe(200);
  const data = await real.json();
  expect(real.url()).toContain(`/datasets/${data.dataset_id}/quality`);
  expect(data.missing.missing_cells).toBe(2);
  expect(data.duplicates.duplicate_rows).toBe(1);
  expect(data.duplicates.duplicate_groups).toBe(1);
  await expect(page.getByText("FAIL · Incumplida")).toHaveCount(2);
  const summary = page.getByRole("region", { name: "Resumen de calidad" });
  for (const [label, value] of [["Total de filas", "3"], ["Total de columnas", "3"], ["Total de celdas", "9"], ["Celdas faltantes", "2"], ["Filas completas", "1"], ["Filas incompletas", "2"], ["Filas duplicadas adicionales", "1"], ["Grupos de duplicados", "1"]]) {
    await expect(summary.locator(".quality-metric").filter({ has: page.getByText(label, { exact: true }) }).locator("dd")).toHaveText(value);
  }
  await expect(summary.getByText("22.22%", { exact: true })).toBeVisible();
  await expect(summary.getByText("33.33%", { exact: true })).toBeVisible();
  await expect(page.getByRole("rowheader")).toHaveText(["id", "nombre", "valor"]);
  expect(requests).toHaveLength(1);
  await capture(page, "quality-screen-desktop.png");
  if (process.env.UI_SCREENSHOT_DIR) {
    for (const [section, file] of [["Valores faltantes por columna", "quality-missing-values.png"], ["Filas completamente duplicadas", "quality-duplicates.png"], ["Reglas de calidad", "quality-rules-fail.png"]]) {
      await page.getByRole("region", { name: section, exact: true }).screenshot({ path: join(process.env.UI_SCREENSHOT_DIR, file) });
    }
  }
  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    if (width === 390) await capture(page, "quality-screen-mobile.png");
  }
  const region = page.getByRole("region", { name: "Detalle de valores faltantes" });
  await region.focus(); await page.keyboard.press("ArrowRight");
  await expect.poll(() => region.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("link", { name: "Ver Dataset", exact: true }).click();
  await expect(page.getByRole("region", { name: "Filas del dataset" })).toBeVisible();
  await page.getByRole("link", { name: "Diccionario de datos", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Metadatos por columna" })).toBeVisible();
  expect(requests).toHaveLength(1);
  await page.getByRole("button", { name: "Nuevo análisis", exact: true }).first().click();
  await upload(page, true);
  await page.getByRole("link", { name: "Calidad de datos", exact: true }).click();
  await expect(page.getByText("PASS · Cumplida")).toHaveCount(2);
  await expect(page.getByText("FAIL · Incumplida")).toHaveCount(0);
  await capture(page, "quality-rules-pass.png");
  expect(requests).toHaveLength(2);
  expect(errors).toEqual([]);
});

test("AUD-014: 404, 413 y desconexión controlados; reintento contra backend real", async ({ page }) => {
  const errors: string[] = []; page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/"); await upload(page);
  let mode = "missing";
  await page.route("**/datasets/*/quality", async (route) => {
    if (mode === "real") await route.continue();
    else if (mode === "network") await route.abort("failed");
    else await route.fulfill({ status: mode === "missing" ? 404 : 413, contentType: "application/json",
      body: JSON.stringify({ detail: { code: mode === "missing" ? "DATASET_NOT_FOUND" : "QUALITY_TOO_LARGE", message: "Synthetic controlled error" } }) });
  });
  await page.getByRole("link", { name: "Calidad de datos", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("El dataset ya no está disponible");
  await capture(page, "quality-expired-dataset.png");
  mode = "large";
  await page.getByRole("link", { name: "Ver Dataset", exact: true }).click();
  await page.getByRole("link", { name: "Calidad de datos", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("La evaluación excede los límites");
  await expect(page.getByRole("alert")).toContainText("No se muestran resultados parciales");
  await capture(page, "quality-too-large.png");
  mode = "network";
  await page.getByRole("link", { name: "Ver Dataset", exact: true }).click();
  await page.getByRole("link", { name: "Calidad de datos", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("No se puede conectar con el servidor");
  await capture(page, "quality-error.png");
  mode = "real";
  const real = page.waitForResponse((r) => r.url().endsWith("/quality") && r.status() === 200);
  await page.getByRole("button", { name: "Reintentar", exact: true }).click();
  expect((await (await real).json()).missing.missing_cells).toBe(2);
  await expect(page.getByText("FAIL · Incumplida")).toHaveCount(2);
  expect(errors).toEqual([]);
});
