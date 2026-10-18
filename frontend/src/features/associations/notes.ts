/**
 * Display-only Spanish wording for the notes exploration tools return in English.
 * The backend contract is unchanged; unknown notes are shown as received.
 */
const NOTES: [RegExp, (match: RegExpMatchArray) => string][] = [
  [/^Pearson and Spearman disagree; check outliers or non-linear patterns\.$/,
    () => "Pearson y Spearman no coinciden: revisa si hay valores atípicos o una relación no lineal."],
  [/^Mutual information suggests a non-linear dependence\.$/,
    () => "La información mutua sugiere una asociación no lineal en estos datos; no indica qué variable influye en la otra."],
  [/^ANOVA assumptions are not met; prefer Kruskal-Wallis\.$/,
    () => "No se cumplen los supuestos de ANOVA; es preferible Kruskal-Wallis."],
  [/^(\d+) group\(s\) with fewer than 2 observations were excluded\.$/,
    ([, count]) => `Se excluyeron ${count} grupo(s) con menos de 2 observaciones.`],
  [/^Showing the (\d+) largest of (\d+) groups\.$/,
    ([, shown, total]) => `Se muestran los ${shown} grupos más grandes de ${total}.`],
  [/^Showing a random sample of (\d+) of (\d+) points\.$/,
    ([, shown, total]) => `Se dibuja una muestra aleatoria reproducible de ${shown} de ${total} puntos; los cálculos usan todos.`],
  [/^(\d+)% of expected frequencies are below 5; the chi-square approximation may be unreliable\.$/,
    ([, share]) => `El ${share} % de las frecuencias esperadas es menor que 5: la aproximación χ² puede no ser fiable.`],
  [/^Some cells are undefined \(constant columns or too few pairs\)\.$/,
    () => "Algunas celdas no están definidas (columnas constantes o muy pocos pares completos)."],
  [/^Relationships are statistical candidates, not causal or validated findings\.$/,
    () => "Las relaciones son candidatas estadísticas, no hallazgos causales ni validados."],
  [/^(\d+) pairs found; only the first (\d+) were screened\.$/,
    ([, total, screened]) => `Se encontraron ${total} pares; solo se evaluaron los primeros ${screened}.`],
  [/^constant or empty column$/, () => "columna constante o vacía"],
  [/^(\d+) categories exceed (\d+)$/, ([, count, limit]) => `${count} categorías superan el límite de ${limit}`],
];

export function explainNote(note: string): string {
  for (const [pattern, render] of NOTES) {
    const match = note.match(pattern);
    if (match) return render(match);
  }
  return note;
}
