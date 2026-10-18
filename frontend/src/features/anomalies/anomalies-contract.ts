import type { OutlierSummary } from "../../types/exploration";
import { classifyOutliers, toolProblem, type OutlierReading, type ToolProblem } from "../associations/tool-state";
import type { useTool } from "../associations/useTool";

type ColumnReading = Exclude<OutlierReading, { kind: "pending" } | { kind: "problem" }>;

export interface ColumnAnomalies {
  column: string;
  reading: ColumnReading;
}

export type AnomaliesReading =
  | { kind: "pending" }
  | { kind: "problem"; problem: ToolProblem }
  | { kind: "invalid" }
  | { kind: "ready"; columns: ColumnAnomalies[] };

/** Reads the `outliers` tool run over every numeric column (variables = []). */
export function readAnomalies(tool: ReturnType<typeof useTool>): AnomaliesReading {
  const problem = toolProblem(tool);
  if (problem) return { kind: "problem", problem };
  if (tool.loading || tool.stale || !tool.data) return { kind: "pending" };
  const { data } = tool;
  const result = data.result as Record<string, unknown> | null | undefined;
  if (data.method !== "outliers" || !Array.isArray(data.variables) || !result || typeof result !== "object"
    || Array.isArray(result) || !data.variables.every((name) => typeof name === "string" && name in result)) return { kind: "invalid" };
  return { kind: "ready", columns: data.variables.map((column) => ({ column, reading: classifyOutliers(result[column]) })) };
}

export interface AnomalyExample {
  rowIndex: number;
  value: number | null;
  iqr: boolean;
  /** Robust z-score when MAD flagged this record; null when only IQR did. */
  robustZ: number | null;
}

export type ExamplesReading =
  /** Older responses without original positions: never infer records from values. */
  | { kind: "no-positions" }
  | { kind: "invalid" }
  | { kind: "ready"; examples: AnomalyExample[]; madDetail: boolean };

const index = (value: unknown, total: number): value is number =>
  typeof value === "number" && Number.isSafeInteger(value) && value >= 0 && value < total;
const finiteOrNull = (value: unknown): value is number | null =>
  value === null || (typeof value === "number" && Number.isFinite(value));

/** IQR and MAD examples merged by original record; IQR order first, then MAD-only records. */
export function mergeExamples(summary: OutlierSummary, totalRows: number): ExamplesReading {
  const iqrRows = summary.iqr?.example_rows;
  if (iqrRows === undefined) return { kind: "no-positions" };
  const madRows = summary.mad?.example_rows;
  const madDetail = Array.isArray(madRows);
  if (!Array.isArray(iqrRows) || !Number.isSafeInteger(totalRows)) return { kind: "invalid" };
  const merged = new Map<number, AnomalyExample>();
  for (const row of iqrRows) {
    if (!row || !index(row.row_index, totalRows) || !finiteOrNull(row.value) || merged.has(row.row_index)) return { kind: "invalid" };
    merged.set(row.row_index, { rowIndex: row.row_index, value: row.value, iqr: true, robustZ: null });
  }
  const seenMad = new Set<number>();
  for (const row of madDetail ? madRows : []) {
    if (!row || !index(row.row_index, totalRows) || !finiteOrNull(row.value) || !finiteOrNull(row.robust_z)
      || seenMad.has(row.row_index)) return { kind: "invalid" };
    seenMad.add(row.row_index);
    const existing = merged.get(row.row_index);
    if (existing && existing.value !== row.value) return { kind: "invalid" };
    merged.set(row.row_index, { rowIndex: row.row_index, value: row.value, iqr: existing?.iqr ?? false, robustZ: row.robust_z });
  }
  return { kind: "ready", examples: [...merged.values()], madDetail };
}

/** Plain-language state of a column, shared by the overview table and the detail. */
export function columnState(reading: ColumnReading): string | null {
  if (reading.kind === "small-sample") return "Muestra pequeña: no se evalúan atípicos";
  if (reading.kind === "invalid") return "Respuesta no válida";
  if (reading.constant) return "Columna constante: sin dispersión";
  if (reading.madZero) return "MAD = 0: criterio MAD no evaluable";
  if (reading.iqrZero) return "IQR = 0: interpretar IQR con cautela";
  return null;
}
