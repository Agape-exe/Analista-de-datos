import type { AnalysisResult, GroupedSummary, GroupSummary } from "../types/exploration";

/**
 * Typed `grouped_summary` example used by Patterns (AUD-019), wrapped in the
 * shared successful-result envelope formalized by AUD-022.
 */
export function groupSummary(label: string, rows: number, missing: number, centre: number, smallSample = false): GroupSummary {
  const count = rows - missing;
  return {
    label, rows, count, missing, small_sample: smallSample,
    mean: centre + 2, median: centre, std: 12.5, q1: centre - 10, q3: centre + 10, iqr: 20, min: centre - 30, max: centre + 40,
  };
}

export function groupedSummaryFixture(override: Partial<GroupedSummary> = {}, column = "amount", groupBy = "category"): AnalysisResult {
  const groups = override.groups ?? [groupSummary("norte", 120, 4, 100), groupSummary("sur", 90, 0, 140), groupSummary("este", 12, 1, 180, true)];
  const result: GroupedSummary = {
    column, group_by: groupBy,
    total_groups: groups.length + 2, shown_groups: groups.length, max_groups: 10, minimum_sample_size: 20,
    groups,
    omitted: { groups: 2, rows: 8, observed: 7 },
    missing_group: { rows: 5, observed: 5 },
    overall: { count: 220, missing: 5, mean: 125, median: 118, std: 35 },
    ...override,
  };
  return {
    method: "grouped_summary", status: "SUCCESS", completeness: "complete", variables: [column, groupBy], execution_time: 0.01,
    sample_size: 235, warnings: [], result: result as never,
  };
}
