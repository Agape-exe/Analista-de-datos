import type { IntakeResponse } from "../types/intake";

// Test-only response representing a two-row fixture; never imported by production screens.
export const intakeFixture: IntakeResponse = {
  status: "SUCCESS",
  filename: "sales.csv",
  profiling_time: 0.02,
  warnings: ["Dictionary column 'unused' is absent from the source and was excluded."],
  profile: {
    dataset_id: "test-dataset", row_count: 2,
    columns: [
      { column_name: "id", data_type: "string", semantic_type: "identifier", missing_count: 0, unique_count: 2, classification_source: "inferred", warnings: [] },
      { column_name: "amount", data_type: "Int64", semantic_type: "numeric", missing_count: 1, unique_count: 1, classification_source: "inferred", warnings: [] },
      { column_name: "category", data_type: "string", semantic_type: "categorical", missing_count: 0, unique_count: 1, classification_source: "inferred", warnings: [] },
    ],
  },
  summary: {
    rows: 2, columns: 3, numeric_columns: ["amount"], categorical_columns: ["category"],
    temporal_columns: [], identifiers: ["id"], text_columns: [], unknown_columns: [],
    data_dictionary: { entries: [
      { column_name: "id", source: "inferred", semantic_type: "identifier", inferred_fields: ["description"], description: "Identifier, meaning unverified.", confidence: null },
      { column_name: "amount", source: "official", semantic_type: "numeric", inferred_fields: [], description: "Total amount", confidence: null },
      { column_name: "category", source: "manual", semantic_type: "categorical", inferred_fields: [], description: "Segment", confidence: 0.8 },
    ] },
  },
  completeness: { missing_cells: 1, total_cells: 6, missing_percentage: 100 / 6,
    column_missing_percentages: { id: 0, amount: 50, category: 0 } },
};

// Test-only intake with two numeric columns so the associations page requests every view.
export const associationsIntakeFixture: IntakeResponse = {
  ...intakeFixture,
  summary: { ...intakeFixture.summary, numeric_columns: ["amount", "price"], categorical_columns: ["category"] },
};

const success = (method: string, result: unknown) => ({
  analysis_id: method, method, variables: [], status: "SUCCESS", result, warnings: [], execution_time: 0.01, metadata: {},
});

// Test-only tool responses keyed by tool name; shapes mirror the Python chart and ranking models.
export const toolFixtures: Record<string, unknown> = {
  relationship_ranking: success("relationship_ranking", {
    top_relationships: [
      { x: "amount", y: "price", method: "pearson", score: 0.91, strength: 0.91, p_value: 0.0001, adjusted_p_value: 0.0002,
        sample_size: 120, supporting: [{ method: "spearman", variables: ["amount", "price"], strength: 0.88, p_value: 0.0001 }],
        warnings: [] },
      { x: "amount", y: "category", method: "kruskal_wallis", score: 0.42, strength: 0.18, p_value: 0.01, adjusted_p_value: 0.02,
        sample_size: 118, supporting: [], warnings: ["2 group(s) with fewer than 2 observations were excluded."] },
    ],
    evaluated_pairs: 3, significant_pairs: 2, skipped_pairs: [], excluded_columns: { id_like: "constant or empty column" },
    significance_level: 0.05, correction: "benjamini-hochberg",
  }),
  chart_correlation_heatmap: success("chart_correlation_heatmap", {
    kind: "heatmap", method: "pearson", columns: ["amount", "price"],
    values: [[1, 0.91], [0.91, 1]], p_values: [[null, 0.0001], [0.0001, null]], sample_sizes: [[120, 120], [120, 120]],
  }),
  chart_scatter: success("chart_scatter", {
    kind: "scatter", x: "amount", y: "price", points: [[1, 2], [2, 4.1], [3, 5.9]], total_points: 3, sampled: false,
    trend: { slope: 1.95, intercept: 0.1 },
  }),
  chart_boxplot: success("chart_boxplot", {
    kind: "boxplot", column: "amount", group_by: "category", boxes: [
      { label: "A", count: 60, lower_whisker: 1, q1: 2, median: 3, q3: 4, upper_whisker: 6, outliers: [9], outlier_count: 1 },
      { label: "B", count: 58, lower_whisker: 2, q1: 4, median: 5, q3: 6, upper_whisker: 8, outliers: [], outlier_count: 0 },
    ],
  }),
  chart_histogram: success("chart_histogram", { kind: "histogram", column: "amount", edges: [0, 5, 10], counts: [70, 50] }),
  descriptive_statistics: success("descriptive_statistics", {
    amount: { count: 120, missing: 0, mean: 5.25, std: 1.5, min: 1, median: 5, max: 9, iqr: 2, skewness: 0.3 },
  }),
  outliers: success("outliers", {
    amount: { count: 120, iqr: { count: 1, percentage: 0.83, lower_fence: -1, upper_fence: 8 }, mad: { count: 1, percentage: 0.83 } },
  }),
};
