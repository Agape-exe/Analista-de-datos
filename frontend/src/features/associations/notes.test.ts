import { describe, expect, it } from "vitest";
import { explainNote } from "./notes";

describe("explainNote", () => {
  it.each([
    ["Pearson and Spearman disagree; check outliers or non-linear patterns.", "Pearson y Spearman no coinciden: revisa si hay valores atípicos o una relación no lineal."],
    ["Mutual information suggests a non-linear dependence.", "La información mutua sugiere una asociación no lineal en estos datos; no indica qué variable influye en la otra."],
    ["Relationships are statistical candidates, not causal or validated findings.", "Las relaciones son candidatas estadísticas, no hallazgos causales ni validados."],
    ["3 group(s) with fewer than 2 observations were excluded.", "Se excluyeron 3 grupo(s) con menos de 2 observaciones."],
    ["Showing a random sample of 2000 of 9000 points.", "Se dibuja una muestra aleatoria reproducible de 2000 de 9000 puntos; los cálculos usan todos."],
    ["40% of expected frequencies are below 5; the chi-square approximation may be unreliable.", "El 40 % de las frecuencias esperadas es menor que 5: la aproximación χ² puede no ser fiable."],
    ["60 categories exceed 50", "60 categorías superan el límite de 50"],
  ])("translates %s for display", (note, expected) => {
    expect(explainNote(note)).toBe(expected);
  });

  it("never claims causation and keeps unknown notes untouched", () => {
    expect(explainNote("Mutual information suggests a non-linear dependence.")).not.toMatch(/causa|provoca|determina/);
    expect(explainNote("Something new from the backend.")).toBe("Something new from the backend.");
  });
});
