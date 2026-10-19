import type { AnalysisReport } from "../lib/api-client";
import { intakeFixture } from "./fixture";

// Partial measurements are permitted even for SUCCESS. No benchmark quality is implied.
export const reportFixture = {
  run_id: "metrics-run-a", status: "SUCCESS", dataset_profile: intakeFixture.profile,
  metrics: { precision: null, llm_calls: 0, total_response_time: 0.125, tokens_used: null },
  stage_statuses: { Insight: "SUCCESS" }, stage_durations: { Insight: 0 },
  configuration: { execution_scope: "finalization_only" },
  analysis_results: [], evidence: [], insights: [], relationship_assessments: [],
  warnings: [], errors: [], execution_trace: [],
} satisfies AnalysisReport;
