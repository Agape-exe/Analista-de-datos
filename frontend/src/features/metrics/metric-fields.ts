import type { components } from "../../types/api";

type Metrics = components["schemas"]["ExperimentMetrics"];

// Exhaustive against the generated contract, including optional/omitted fields.
// Rates are displayed in their original 0–1 scale; no frontend calculation.
export const metricUnits = {
  precision: "0–1", recall: "0–1", f1_score: "0–1", false_positive_rate: "0–1",
  pattern_detection_rate: "0–1", spurious_detection_rate: "0–1",
  hypothesis_consistency: "0–1", insight_consistency: "0–1", tool_selection_consistency: "0–1",
  conclusion_agreement: "0–1", semantic_similarity: "0–1",
  total_response_time: "s", time_to_first_insight: "s", llm_calls: "llamadas",
  tool_calls: "llamadas", tokens_used: "tokens", iterations: "iteraciones",
  profiling_time: "s", analytics_time: "s", completion_rate: "0–1",
  human_intervention_rate: "0–1", valid_tool_selection_rate: "0–1", invalid_analysis_rate: "0–1",
} satisfies Record<keyof Metrics, string>;

export const metricFields = Object.keys(metricUnits) as (keyof Metrics)[];
