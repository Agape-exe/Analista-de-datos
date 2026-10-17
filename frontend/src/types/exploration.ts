import type { components } from "./api";

export type AnalysisResult = components["schemas"]["AnalysisResult"];
export type ToolRunRequest = components["schemas"]["ToolRunRequest"];

// AnalysisResult.result is free JSON in OpenAPI. These shapes mirror the Python models
// RankedRelationship (app/shared/domain/models/analysis.py) and the chart specs in
// app/modules/exploration/adapters/visualization/charts.py; update both sides together.

export interface SupportingMeasure {
  method: string;
  variables: string[];
  strength: number | null;
  p_value: number | null;
}

export interface RankedRelationship {
  x: string;
  y: string;
  method: string;
  score: number;
  strength: number | null;
  p_value: number | null;
  adjusted_p_value: number | null;
  sample_size: number;
  supporting: SupportingMeasure[];
  warnings: string[];
}

export interface RelationshipRanking {
  top_relationships: RankedRelationship[];
  evaluated_pairs: number;
  significant_pairs: number;
  skipped_pairs: { x: string; y: string; reason: string }[];
  excluded_columns: Record<string, string>;
  significance_level: number;
  correction: string;
}

export interface HeatmapChart {
  kind: "heatmap";
  method: string;
  columns: string[];
  values: (number | null)[][];
  p_values: (number | null)[][];
  sample_sizes: number[][];
}

export interface ScatterChart {
  kind: "scatter";
  x: string;
  y: string;
  points: [number, number][];
  total_points: number;
  sampled: boolean;
  trend: { slope: number; intercept: number } | null;
}

export interface HistogramChart {
  kind: "histogram";
  column: string;
  edges: number[];
  counts: number[];
}

export interface BoxStats {
  label: string;
  count: number;
  lower_whisker: number;
  q1: number;
  median: number;
  q3: number;
  upper_whisker: number;
  outliers: number[];
  outlier_count: number;
}

export interface BoxPlotChart {
  kind: "boxplot";
  column: string;
  group_by: string | null;
  boxes: BoxStats[];
}

export type ChartSpec = HeatmapChart | ScatterChart | HistogramChart | BoxPlotChart;

export interface NumericSummary {
  count: number;
  missing: number;
  mean?: number | null;
  std?: number | null;
  min?: number | null;
  median?: number | null;
  max?: number | null;
  iqr?: number | null;
  skewness?: number | null;
}

export interface OutlierSummary {
  count: number;
  iqr: { count: number; percentage: number | null; lower_fence: number | null; upper_fence: number | null };
  mad: { count: number | null; percentage: number | null };
}
