import type { components } from "../types/api";

export type DatasetQuality = components["schemas"]["DatasetQuality"];
const natural = (value: unknown): value is number => typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
const percentage = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 100;

// Validate aggregates for consistency; presentation always uses server percentages.
export function validQuality(payload: unknown, datasetId: string): payload is DatasetQuality {
  if (!payload || typeof payload !== "object") return false;
  const q = payload as Partial<DatasetQuality>;
  if (q.dataset_id !== datasetId || !natural(q.total_rows) || !natural(q.total_columns) || !natural(q.total_cells)
    || q.total_cells !== q.total_rows * q.total_columns
    || q.status !== (q.total_rows && q.total_columns ? "EVALUATED" : "NOT_EVALUATED")) return false;
  const m = q.missing, d = q.duplicates;
  if (!m || !d || !natural(m.missing_cells) || m.missing_cells > q.total_cells || !percentage(m.missing_percentage)
    || !natural(m.complete_rows) || !natural(m.incomplete_rows) || m.complete_rows + m.incomplete_rows !== q.total_rows
    || m.incomplete_rows > m.missing_cells || m.missing_cells > m.incomplete_rows * q.total_columns
    || !Array.isArray(m.columns) || m.columns.length !== q.total_columns) return false;
  if (!m.columns.every((c) => c && typeof c.column_name === "string" && c.column_name.length > 0
    && typeof c.data_type === "string" && natural(c.missing_count) && c.missing_count <= q.total_rows!
    && percentage(c.missing_percentage))) return false;
  if (new Set(m.columns.map((c) => c.column_name)).size !== m.columns.length
    || m.columns.reduce((sum, c) => sum + c.missing_count, 0) !== m.missing_cells) return false;
  if (!natural(d.duplicate_rows) || d.duplicate_rows > Math.max(0, q.total_rows - 1)
    || !natural(d.duplicate_groups) || d.duplicate_groups > d.duplicate_rows
    || Boolean(d.duplicate_groups) !== Boolean(d.duplicate_rows)
    || d.duplicate_groups + d.duplicate_rows > q.total_rows || !percentage(d.duplicate_percentage)) return false;
  if (!Array.isArray(q.rules) || !q.rules.every((r) => r && typeof r.rule_id === "string" && r.rule_id.length > 0
    && typeof r.description === "string" && r.description.length > 0
    && ["PASS", "FAIL", "NOT_EVALUATED"].includes(r.status)
    && (r.observed_count == null || natural(r.observed_count))
    && (r.reason == null || typeof r.reason === "string")
    && (r.status !== "NOT_EVALUATED" || r.observed_count == null)
    && (q.status !== "NOT_EVALUATED" || r.status === "NOT_EVALUATED"))) return false;
  return new Set(q.rules.map((r) => r.rule_id)).size === q.rules.length;
}
