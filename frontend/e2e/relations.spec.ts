import { expect, test } from "@playwright/test";
import { reportFixture } from "../src/test/report-fixture";

const report = {
  ...reportFixture,
  run_id: "relations-e2e",
  analysis_results: [{
    analysis_id: "partial-001", method: "partial_correlation", variables: ["publicidad", "ventas"],
    status: "SUCCESS", completeness: "complete", result: { correlation: 0.16 }, effect_size: 0.16,
    sample_size: 100, execution_time: 0, warnings: [], metadata: { control_variables: ["campaña"] },
  }],
  evidence: [{
    evidence_id: "evidence-001", analysis_id: "partial-001",
    description: "La correlación disminuyó al controlar campaña.", limitations: ["No demuestra causalidad."],
  }],
  relationship_assessments: [{
    variables: ["publicidad", "ventas"], evidence_ids: ["evidence-001"], potentially_spurious: true,
    rationale: "Debilitamiento relevante de la correlación.",
    limitations: ["Screening ranking-001: método=pearson; n=100; p crudo=0.01; p ajustado=0.02."],
  }],
};

test("AUD-032/AUD-043: recovered relations preserve evidence and provenance", async ({ page }) => {
  await page.route("**/api/reports/relations-e2e", (route) => route.fulfill({ json: report }));
  await page.goto("/report");
  await page.getByLabel("ID de ejecución").fill("relations-e2e");
  await page.getByRole("button", { name: "Consultar", exact: true }).click();
  await expect(page.getByText("Ejecución: relations-e2e", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Relaciones", exact: true }).click();

  await expect(page.getByRole("heading", { name: "publicidad ↔ ventas" })).toBeVisible();
  await expect(page.getByText(/Potencialmente espuria/)).toBeVisible();
  await expect(page.getByText("La correlación disminuyó al controlar campaña.")).toBeVisible();
  await expect(page.getByText("Variables de control: campaña")).toBeVisible();
  await page.getByText("Limitaciones de la evaluación").click();
  await expect(page.getByText(/Screening ranking-001: método=pearson/)).toBeVisible();
  await page.getByRole("link", { name: "Ver resultado original" }).click();
  await expect(page).toHaveURL(/\/relations#analysis-partial-001$/);
  await expect(page.getByRole("heading", { name: "Correlación parcial · SUCCESS" })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
