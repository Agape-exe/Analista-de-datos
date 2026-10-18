import type { GroupedSummary, NumericSummary } from "../../types/exploration";
import { toolProblem, type ToolProblem } from "../associations/tool-state";
import type { useTool } from "../associations/useTool";

/**
 * Seam between the Patterns screen and its data. Today it reads the `grouped_summary`
 * tool (AUD-019); when the shared results contract (AUD-022) lands, only this module
 * should need to change.
 */
export interface PatternGroup {
  label: string;
  rows: number;
  observed: number;
  missing: number;
  mean: number | null;
  median: number | null;
  std: number | null;
  q1: number | null;
  q3: number | null;
  iqr: number | null;
  min: number | null;
  max: number | null;
  smallSample: boolean;
}

export interface PatternsView {
  column: string;
  groupBy: string;
  groups: PatternGroup[];
  totalGroups: number;
  minimumSampleSize: number;
  omitted: { groups: number; rows: number; observed: number };
  missingGroup: { rows: number; observed: number };
  overall: { observed: number; missing: number; mean: number | null; median: number | null; std: number | null };
}

export type PatternsReading =
  | { kind: "pending" }
  | { kind: "problem"; problem: ToolProblem }
  | { kind: "invalid" }
  | { kind: "ready"; view: PatternsView };

const natural = (value: unknown): value is number => typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
const number = (value: unknown): number | null => typeof value === "number" && Number.isFinite(value) ? value : null;
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);

function group(raw: unknown, minimum: number): PatternGroup | null {
  if (!object(raw) || typeof raw.label !== "string" || !natural(raw.rows) || !natural(raw.count) || !natural(raw.missing)
    || raw.count + raw.missing !== raw.rows) return null;
  return {
    label: raw.label, rows: raw.rows, observed: raw.count, missing: raw.missing,
    mean: number(raw.mean), median: number(raw.median), std: number(raw.std), q1: number(raw.q1), q3: number(raw.q3),
    iqr: number(raw.iqr), min: number(raw.min), max: number(raw.max),
    smallSample: typeof raw.small_sample === "boolean" ? raw.small_sample : raw.count < minimum,
  };
}

function counts<K extends string>(raw: unknown, keys: K[]): Record<K, number> | null {
  if (!object(raw) || !keys.every((key) => natural(raw[key]))) return null;
  return raw as Record<K, number>;
}

export function readGroupedSummary(tool: ReturnType<typeof useTool>, column: string | undefined, groupBy: string | undefined): PatternsReading {
  const problem = toolProblem(tool);
  if (problem) return { kind: "problem", problem };
  if (!column || !groupBy || tool.loading || tool.stale || !tool.data) return { kind: "pending" };
  const result = tool.data.result as Partial<GroupedSummary> | null | undefined;
  if (tool.data.method !== "grouped_summary" || !object(result) || result.column !== column || result.group_by !== groupBy
    || !natural(result.total_groups) || !natural(result.minimum_sample_size) || !Array.isArray(result.groups)) return { kind: "invalid" };
  const minimum = result.minimum_sample_size;
  const groups = result.groups.map((item) => group(item, minimum));
  const omitted = counts(result.omitted, ["groups", "rows", "observed"]);
  const missingGroup = counts(result.missing_group, ["rows", "observed"]);
  const overall = result.overall as NumericSummary | undefined;
  if (groups.some((item) => item === null) || !omitted || !missingGroup || !object(overall)
    || !natural(overall.count) || !natural(overall.missing)
    || result.total_groups !== groups.length + omitted.groups) return { kind: "invalid" };
  return {
    kind: "ready",
    view: {
      column, groupBy, groups: groups as PatternGroup[], totalGroups: result.total_groups, minimumSampleSize: minimum,
      omitted, missingGroup,
      overall: { observed: overall.count, missing: overall.missing, mean: number(overall.mean), median: number(overall.median), std: number(overall.std) },
    },
  };
}

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

/** Every limitation the screen must state; nothing left out is ever silent. */
export function limitations(view: PatternsView): string[] {
  const notes: string[] = [];
  if (view.omitted.groups > 0) {
    notes.push(`Se muestran los ${view.groups.length} grupos con más filas de ${view.totalGroups}. `
      + `Se omitieron ${plural(view.omitted.groups, "grupo", "grupos")} con ${plural(view.omitted.rows, "fila", "filas")} `
      + `(${plural(view.omitted.observed, "valor observado", "valores observados")}); no aparecen en la tabla ni en el gráfico.`);
  }
  if (view.missingGroup.rows > 0) {
    notes.push(`${plural(view.missingGroup.rows, "fila no tiene", "filas no tienen")} categoría en «${view.groupBy}» y no se asignan a ningún grupo `
      + `(${plural(view.missingGroup.observed, "tiene", "tienen")} valor en «${view.column}»).`);
  }
  const small = view.groups.filter((item) => item.smallSample).length;
  if (small > 0) {
    notes.push(`${plural(small, "grupo tiene", "grupos tienen")} menos de ${view.minimumSampleSize} observaciones: sus estadísticas son orientativas y no conviene compararlas.`);
  }
  const empty = view.groups.filter((item) => item.observed === 0).length;
  if (empty > 0) notes.push(`${plural(empty, "grupo no tiene", "grupos no tienen")} valores observados en «${view.column}»; solo se cuentan sus filas.`);
  return notes;
}
