import type { DatasetQuality } from "../lib/quality-response";

// Synthetic aggregate responses for tests only; never imported by production.
export function qualityFixture(datasetId = "dataset-a", clean = false): DatasetQuality {
  return {
    dataset_id: datasetId, status: "EVALUATED", total_rows: 3, total_columns: 3, total_cells: 9,
    missing: {
      missing_cells: clean ? 0 : 2, missing_percentage: clean ? 0 : 200 / 9,
      incomplete_rows: clean ? 0 : 2, complete_rows: clean ? 3 : 1,
      columns: [
        { column_name: "id", data_type: "string", missing_count: 0, missing_percentage: 0 },
        { column_name: "nombre", data_type: "string", missing_count: 0, missing_percentage: 0 },
        { column_name: "valor", data_type: "Int64", missing_count: clean ? 0 : 2, missing_percentage: clean ? 0 : 200 / 3 },
      ],
    },
    duplicates: { duplicate_rows: clean ? 0 : 1, duplicate_percentage: clean ? 0 : 100 / 3, duplicate_groups: clean ? 0 : 1 },
    rules: [
      { rule_id: "NO_MISSING_VALUES", description: "Ausencia de valores faltantes", status: clean ? "PASS" : "FAIL", observed_count: clean ? 0 : 2, reason: clean ? null : "Se observaron valores faltantes." },
      { rule_id: "NO_DUPLICATE_ROWS", description: "Ausencia de filas completamente duplicadas", status: clean ? "PASS" : "FAIL", observed_count: clean ? 0 : 1, reason: clean ? null : "Se observaron filas duplicadas." },
    ],
  };
}

export function emptyQualityFixture(): DatasetQuality {
  return {
    dataset_id: "dataset-a", status: "NOT_EVALUATED", total_rows: 0, total_columns: 0, total_cells: 0,
    missing: { missing_cells: 0, missing_percentage: 0, incomplete_rows: 0, complete_rows: 0, columns: [] },
    duplicates: { duplicate_rows: 0, duplicate_percentage: 0, duplicate_groups: 0 },
    rules: qualityFixture().rules.map((rule) => ({ ...rule, status: "NOT_EVALUATED", observed_count: null, reason: "Sin filas o columnas evaluables." })),
  };
}
