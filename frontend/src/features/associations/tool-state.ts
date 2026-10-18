import type { OutlierSummary } from "../../types/exploration";
import type { useTool } from "./useTool";

type Tool = ReturnType<typeof useTool>;

export interface ToolProblem {
  /** error: the request did not complete; failed: the computation raised; skipped: not applicable. */
  kind: "error" | "failed" | "skipped";
  message: string;
  /** Raw backend note, shown only as secondary technical detail. */
  detail?: string;
  requestId?: string;
  retryable: boolean;
}

/** Explains why a finished tool has nothing to draw; null while loading or when it succeeded. */
export function toolProblem(tool: Tool): ToolProblem | null {
  if (tool.error) {
    return { kind: "error", message: tool.error.message, requestId: tool.error.requestId, retryable: !tool.error.expired };
  }
  if (tool.loading || !tool.data) return null;
  const detail = tool.data.warnings?.[0];
  if (tool.data.status === "FAILED") {
    return { kind: "failed", message: "El cálculo falló en el servidor. No se muestran resultados parciales.", detail, retryable: true };
  }
  if (tool.data.status === "SKIPPED") {
    return { kind: "skipped", message: "Este cálculo no es aplicable a la selección actual.", detail, retryable: false };
  }
  return null;
}

type Evaluated = OutlierSummary & { iqr: NonNullable<OutlierSummary["iqr"]> };

export type OutlierReading =
  | { kind: "pending" }
  | { kind: "problem"; problem: ToolProblem }
  /** The response does not belong to the current column or is malformed. */
  | { kind: "invalid" }
  /** Too few observations: the backend declined to evaluate. */
  | { kind: "small-sample" }
  | {
    kind: "evaluated";
    summary: Evaluated;
    /** Every observed value is equal: no spread, so no value can be atypical. */
    constant: boolean;
    /** Interquartile range is 0: any value different from the quartiles falls outside the fences. */
    iqrZero: boolean;
    /** MAD is 0 (half or more of the values equal the median): robust z-scores are undefined. */
    madZero: boolean;
  };

const count = (value: unknown): value is number => typeof value === "number" && Number.isSafeInteger(value) && value >= 0;

/** Single, validated way to read the `outliers` tool for one column. */
export function readOutliers(tool: Tool, column: string | undefined): OutlierReading {
  const problem = toolProblem(tool);
  if (problem) return { kind: "problem", problem };
  if (!column || tool.loading || tool.stale || !tool.data) return { kind: "pending" };
  const { data } = tool;
  const result = data.result;
  if (data.method !== "outliers" || !Array.isArray(data.variables) || data.variables.length !== 1
    || data.variables[0] !== column || !result || typeof result !== "object" || Array.isArray(result)) return { kind: "invalid" };
  const summary = (result as Record<string, unknown>)[column] as OutlierSummary | undefined;
  if (!summary || typeof summary !== "object") return { kind: "invalid" };
  if (summary.skipped) return { kind: "small-sample" };
  const iqr = summary.iqr;
  if (!iqr || typeof iqr !== "object" || !count(iqr.count)) return { kind: "invalid" };
  const madCount = summary.mad?.count;
  if (madCount != null && !count(madCount)) return { kind: "invalid" };
  const iqrZero = iqr.lower_fence != null && iqr.lower_fence === iqr.upper_fence;
  const madZero = summary.mad !== undefined && madCount == null;
  return { kind: "evaluated", summary: summary as Evaluated, constant: iqrZero && iqr.count === 0, iqrZero, madZero };
}
