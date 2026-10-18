import type { DatasetPreview } from "../lib/api-client";
import { intakeFixture } from "./fixture";

export const intakePreviewFixture: DatasetPreview = {
  dataset_id: intakeFixture.profile.dataset_id,
  columns: [
    { name: "id", data_type: "string", nullable: false },
    { name: "amount", data_type: "Int64", nullable: true },
    { name: "category", data_type: "string", nullable: false },
  ],
  rows: [["001", 10, "A"], ["002", null, "A"]],
  total_rows: 2, offset: 0, limit: 20, returned_rows: 2, has_more: false, next_offset: null,
};

// Synthetic pages for tests only. Production always uses the backend response.
export function previewFixture(offset = 0, limit = 20, total = 45, datasetId = "dataset-a"): DatasetPreview {
  const count = Math.min(limit, Math.max(0, total - offset));
  const end = offset + count;
  return {
    dataset_id: datasetId,
    columns: [
      { name: "codigo", data_type: "string", nullable: false },
      { name: "importe", data_type: "Float64", nullable: false },
      { name: "activo", data_type: "boolean", nullable: false },
      { name: "nota", data_type: "string", nullable: true },
    ],
    rows: Array.from({ length: count }, (_, index) => [String(offset + index + 1).padStart(3, "0"), offset + index + 1.5, index % 2 === 0, null]),
    total_rows: total, offset, limit, returned_rows: count,
    has_more: end < total, next_offset: end < total ? end : null,
  };
}
