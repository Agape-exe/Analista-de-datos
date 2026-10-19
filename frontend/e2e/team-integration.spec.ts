import { expect, test } from "@playwright/test";

test("selected control generates a new saved report with plan, evidence and trace", async ({ page }) => {
  test.setTimeout(90_000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("link", { name: "Configurar Hallazgos", exact: true })).toBeVisible();
  await expect(page.getByText("Disponible en Hallazgos", { exact: true })).toBeVisible();
  const rows = ["x,y,control,label", ...Array.from({ length: 60 }, (_, i) =>
    `${i + (i % 3) / 10},${2 * i + (i % 5) / 10},${Math.floor(i / 5)},group-${i % 2}`)];
  await page.getByLabel("Archivo del dataset", { exact: true }).setInputFiles({
    name: "controls.csv", mimeType: "text/csv", buffer: Buffer.from(rows.join("\n")),
  });
  await page.getByRole("button", { name: "Comprender dataset", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Resumen del dataset", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Hallazgos", exact: true }).click();
  const initialResponse = page.waitForResponse((response) => response.url().includes("/analysis/datasets/")
    && response.request().method() === "POST");
  await page.getByRole("button", { name: "Generar reporte", exact: true }).click();
  const previous = await (await initialResponse).json();
  await expect(page.getByText(`Ejecución: ${previous.run_id}`, { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Relaciones", exact: true }).click();
  await page.getByRole("combobox", { name: "Variable de control", exact: true }).selectOption("control");
  const controlledResponse = page.waitForResponse((response) => response.url().includes("/analysis/datasets/")
    && response.request().method() === "POST");
  await page.getByRole("button", { name: "Generar nuevo reporte con este control", exact: true }).click();
  const response = await controlledResponse;
  expect(response.request().postDataJSON().control_selection).toEqual({ variables: ["x", "y"], control_variable: "control" });
  const report = await response.json();
  expect(report.run_id).not.toBe(previous.run_id);
  expect(report.analysis_plan.steps.map((step: { request: { method: string } }) => step.request.method))
    .toEqual(["pearson", "partial_correlation"]);
  const partial = report.analysis_results.find((item: { method: string }) => item.method === "partial_correlation");
  expect(partial.status).toBe("SUCCESS");
  const saved = await (await page.request.get(`/api/reports/${report.run_id}`)).json();
  expect(saved).toEqual(report);
  expect(await (await page.request.get(`/api/reports/${previous.run_id}`)).json()).toEqual(previous);
  await expect(page.getByText(`Reporte: ${report.run_id}`, { exact: true })).toBeVisible();
  await page.getByText("Limitaciones de la evaluación", { exact: true }).click();
  await expect(page.getByText(new RegExp(`Screening ${report.screening_summary.analysis_id}: método=`))).toBeVisible();
  await page.getByRole("link", { name: "Traza", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Plan y decisiones" })).toBeVisible();
  await expect(page.getByRole("link", { name: `Ver resultado ${partial.analysis_id}`, exact: true })).toBeVisible();
  await page.getByRole("link", { name: `Ver resultado ${partial.analysis_id}`, exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/report#result-${partial.analysis_id}$`));
  expect(errors).toEqual([]);
});
