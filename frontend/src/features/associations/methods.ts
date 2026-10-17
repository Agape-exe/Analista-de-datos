export const methodLabels: Record<string, string> = {
  pearson: "r de Pearson",
  spearman: "ρ de Spearman",
  cramers_v: "V de Cramér",
  chi_square: "Chi-cuadrado",
  anova: "ANOVA η²",
  kruskal_wallis: "Kruskal-Wallis ε²",
  mutual_information: "Información mutua",
  anova_one_way: "ANOVA de una vía",
  partial_correlation: "Correlación parcial",
  correlation_matrix: "Matriz de correlación",
  relationship_ranking: "Ranking de relaciones",
  descriptive_statistics: "Estadística descriptiva",
  distribution: "Distribución",
  cardinality: "Cardinalidad",
  missing_values: "Valores faltantes",
  outliers: "Valores atípicos",
};

export function methodLabel(method: string): string {
  return methodLabels[method] ?? method;
}

export type PairKind = "numeric" | "mixed" | "categorical";

export function pairKind(x: string, y: string, numeric: string[]): PairKind {
  const count = [x, y].filter((name) => numeric.includes(name)).length;
  return count === 2 ? "numeric" : count === 1 ? "mixed" : "categorical";
}
