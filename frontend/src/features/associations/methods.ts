export const methodLabels: Record<string, string> = {
  pearson: "Pearson r",
  spearman: "Spearman ρ",
  cramers_v: "Cramér's V",
  chi_square: "Chi-square",
  anova: "ANOVA η²",
  kruskal_wallis: "Kruskal-Wallis ε²",
  mutual_information: "Mutual information",
};

export function methodLabel(method: string): string {
  return methodLabels[method] ?? method;
}

export type PairKind = "numeric" | "mixed" | "categorical";

export function pairKind(x: string, y: string, numeric: string[]): PairKind {
  const count = [x, y].filter((name) => numeric.includes(name)).length;
  return count === 2 ? "numeric" : count === 1 ? "mixed" : "categorical";
}
