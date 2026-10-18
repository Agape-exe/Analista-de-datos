// Spanish display names for report contract values; unknown values are shown unchanged.

const statusLabels: Record<string, string> = {
  SUCCESS: "Completado",
  FAILED: "Fallido",
  SKIPPED: "Pendiente",
};

const stageLabels: Record<string, string> = {
  DataUnderstanding: "Comprensión de datos",
  Association: "Asociaciones",
  Planner: "Planificación",
  Analysis: "Análisis",
  Critic: "Revisión crítica",
  Insight: "Hallazgos",
};

const metricLabels: Record<string, string> = {
  precision: "Precisión",
  recall: "Exhaustividad (recall)",
  f1_score: "Puntaje F1",
  false_positive_rate: "Tasa de falsos positivos",
  pattern_detection_rate: "Tasa de detección de patrones",
  spurious_detection_rate: "Tasa de detecciones espurias",
  hypothesis_consistency: "Consistencia de hipótesis",
  insight_consistency: "Consistencia de hallazgos",
  tool_selection_consistency: "Consistencia en la selección de herramientas",
  conclusion_agreement: "Concordancia de conclusiones",
  semantic_similarity: "Similitud semántica",
  total_response_time: "Tiempo total de respuesta (s)",
  time_to_first_insight: "Tiempo hasta el primer hallazgo (s)",
  llm_calls: "Llamadas al LLM",
  tool_calls: "Llamadas a herramientas",
  tokens_used: "Tokens usados",
  iterations: "Iteraciones",
  profiling_time: "Tiempo de perfilado (s)",
  analytics_time: "Tiempo de análisis (s)",
  completion_rate: "Tasa de finalización",
  human_intervention_rate: "Tasa de intervención humana",
  valid_tool_selection_rate: "Tasa de selección válida de herramientas",
  invalid_analysis_rate: "Tasa de análisis inválidos",
};

const methodLabels: Record<string, string> = {
  pearson: "Correlación de Pearson",
  spearman: "Correlación de Spearman",
  partial_correlation: "Correlación parcial",
  correlation_without_outliers: "Correlación sin valores atípicos",
  chi_square: "Chi-cuadrado",
  cramers_v: "V de Cramér",
  anova_one_way: "ANOVA de un factor",
  kruskal_wallis: "Kruskal-Wallis",
  analyze_subgroups: "Análisis por subgrupos",
  additive_identity: "Identidad aditiva",
};

export const statusLabel = (status: string) => statusLabels[status] ?? status;
export const stageLabel = (stage: string) => stageLabels[stage] ?? stage;
export const metricLabel = (metric: string) => metricLabels[metric] ?? metric;
export const methodLabel = (method: string) => methodLabels[method] ?? method;
