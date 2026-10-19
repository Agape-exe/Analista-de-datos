import { expect, test, type Route } from "@playwright/test";

test("AUD-045: navigation keeps drafts and report inputs; new analysis clears the session", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Archivo del dataset", { exact: true }).setInputFiles({
    name: "navigation.csv", mimeType: "text/csv", buffer: Buffer.from("x|y\n1|2\n3|4\n"),
  });
  await page.getByLabel("Separador CSV").selectOption("|");
  await page.getByRole("button", { name: "Comprender dataset", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Resumen del dataset" })).toBeVisible();
  await page.getByRole("link", { name: "Hallazgos", exact: true }).click();
  await page.getByLabel("Pregunta del análisis").fill("Compare x and y");
  await page.getByLabel("ID de ejecución").fill("draft-id");
  await page.getByRole("link", { name: "Diccionario de datos", exact: true }).click();
  await page.getByRole("link", { name: "Hallazgos", exact: true }).click();
  await expect(page.getByLabel("Pregunta del análisis")).toHaveValue("Compare x and y");
  await expect(page.getByLabel("ID de ejecución")).toHaveValue("draft-id");
  await page.getByRole("button", { name: "Generar reporte", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Estado: Pendiente" })).toBeVisible();
  const run = await page.getByLabel("ID de ejecución").inputValue();
  expect(run).not.toBe("draft-id");
  await page.getByRole("link", { name: "Inicio de Analista de Datos IA" }).click();
  await expect(page.getByLabel("Separador CSV")).toHaveValue("|");
  await expect(page.getByRole("heading", { name: "navigation.csv" })).toBeVisible();
  await page.getByRole("link", { name: "Hallazgos", exact: true }).click();
  await expect(page.getByLabel("ID de ejecución")).toHaveValue(run);
  await expect(page.getByLabel("Pregunta del análisis")).toHaveValue("Compare x and y");
  await page.getByRole("button", { name: "Nuevo análisis", exact: true }).first().click();
  await expect(page.getByRole("button", { name: "Comprender dataset", exact: true })).toBeDisabled();
  await expect(page.getByLabel("Separador CSV")).toHaveValue(",");
  await page.getByRole("link", { name: "Hallazgos", exact: true }).click();
  await expect(page.getByLabel("ID de ejecución")).toHaveValue("");
  await expect(page.getByRole("heading", { name: "Reporte generado" })).toHaveCount(0);
});

test("AUD-045: cancelling intake keeps its draft and permits retry or reset", async ({ page }) => {
  let held: Route | undefined;
  await page.route("**/api/intake", (route) => { held = route; });
  await page.goto("/");
  await page.getByLabel("Archivo del dataset", { exact: true }).setInputFiles({
    name: "cancel.csv", mimeType: "text/csv", buffer: Buffer.from("x,y\n1,2\n3,4\n"),
  });
  await page.getByRole("button", { name: "Comprender dataset", exact: true }).click();
  await expect(page.getByRole("button", { name: "Cancelar espera de carga" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Nuevo análisis", exact: true }).first()).toBeEnabled();
  await page.getByRole("button", { name: "Cancelar espera de carga" }).click();
  await expect(page.getByRole("status")).toContainText("Los archivos y opciones se conservan");
  await expect(page.getByRole("button", { name: "Comprender dataset", exact: true })).toBeEnabled();
  if (held) await held.abort();
  await page.unroute("**/api/intake");
  await page.getByRole("button", { name: "Comprender dataset", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Resumen del dataset" })).toBeVisible();
});
