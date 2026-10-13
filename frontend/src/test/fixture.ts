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
