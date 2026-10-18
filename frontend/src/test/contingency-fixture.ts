import type { AnalysisResult, ContingencyChart } from "../types/exploration";

/**
 * Typed `chart_contingency` example used by the categorical pair view (AUD-021),
 * wrapped in the shared complete-result envelope formalized by AUD-022.
 */
export function contingencyTable(override: Partial<ContingencyChart> = {}, x = "region", y = "canal"): ContingencyChart {
  const counts = override.counts ?? [[40, 6, 4], [5, 30, 3], [2, 4, 1]];
  return {
    kind: "contingency", x, y,
    row_labels: ["norte", "sur", "este"], column_labels: ["web", "tienda", "teléfono"],
    counts,
    row_totals: counts.map((row) => row.reduce((a, b) => a + b, 0)),
    column_totals: counts[0].map((_, index) => counts.reduce((total, row) => total + row[index], 0)),
    total: counts.flat().reduce((a, b) => a + b, 0),
    expected: [[24.5, 20.2, 4.3], [18.8, 15.5, 3.3], [3.7, 3.1, 0.7]],
    folded_rows: 0, folded_columns: 0,
    cells: 9, expected_below_5: 5, expected_below_1: 1, min_expected: 0.7, empty_cells: 0, excluded_rows: 3,
    ...override,
  };
}

export function contingencyResult(override: Partial<ContingencyChart> = {}, x = "region", y = "canal"): AnalysisResult {
  const table = contingencyTable(override, x, y);
  return {
    method: "chart_contingency", status: "SUCCESS", variables: [x, y], execution_time: 0.01,
    sample_size: table.total, warnings: [], result: table as never, metadata: { chart: "contingency" },
    completeness: "complete", column_results: {},
  };
}
