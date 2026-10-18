import type { ContingencyChart } from "../../types/exploration";
import { toolProblem, type ToolProblem } from "./tool-state";
import type { useTool } from "./useTool";

/**
 * Seam between the categorical pair view and its data. Today it reads the
 * `chart_contingency` tool; when the shared results contract (AUD-022) lands, only
 * this module should need to change.
 */
export type ContingencyReading =
  | { kind: "pending" }
  | { kind: "problem"; problem: ToolProblem }
  | { kind: "invalid" }
  | { kind: "ready"; table: ContingencyChart };

const natural = (value: unknown): value is number => typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
const sum = (values: number[]) => values.reduce((total, value) => total + value, 0);

function valid(raw: unknown, x: string, y: string): raw is ContingencyChart {
  if (!raw || typeof raw !== "object") return false;
  const table = raw as Partial<ContingencyChart>;
  const rows = table.row_labels, columns = table.column_labels, counts = table.counts;
  if (table.kind !== "contingency" || table.x !== x || table.y !== y || !Array.isArray(rows) || !Array.isArray(columns)
    || rows.length < 2 || columns.length < 2 || !rows.every((label) => typeof label === "string")
    || !columns.every((label) => typeof label === "string") || !Array.isArray(counts) || counts.length !== rows.length
    || !counts.every((row) => Array.isArray(row) && row.length === columns.length && row.every(natural))) return false;
  if (!Array.isArray(table.expected) || table.expected.length !== rows.length
    || !table.expected.every((row) => Array.isArray(row) && row.length === columns.length)) return false;
  const rowTotals = counts.map(sum);
  const columnTotals = columns.map((_, index) => sum(counts.map((row) => row[index])));
  return JSON.stringify(table.row_totals) === JSON.stringify(rowTotals)
    && JSON.stringify(table.column_totals) === JSON.stringify(columnTotals)
    && table.total === sum(rowTotals)
    && [table.folded_rows, table.folded_columns, table.cells, table.expected_below_5, table.expected_below_1,
      table.empty_cells, table.excluded_rows].every(natural);
}

export function readContingency(tool: ReturnType<typeof useTool>, x: string, y: string): ContingencyReading {
  const problem = toolProblem(tool);
  if (problem) return { kind: "problem", problem };
  if (tool.loading || tool.stale || !tool.data) return { kind: "pending" };
  if (tool.data.method !== "chart_contingency" || !valid(tool.data.result, x, y)) return { kind: "invalid" };
  return { kind: "ready", table: tool.data.result };
}

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;
const percent = (part: number, whole: number) => `${Math.round((100 * part) / whole)} %`;

/** Statistical warnings in plain language; the last one is always stated. */
export function contingencyWarnings(table: ContingencyChart): string[] {
  const notes: string[] = [];
  if (table.cells > 0 && table.expected_below_5 / table.cells > 0.2) {
    notes.push(`El ${percent(table.expected_below_5, table.cells)} de las frecuencias esperadas es menor que 5 `
      + `(${table.expected_below_5} de ${table.cells} celdas): la aproximación χ² puede no ser fiable; interpreta su valor p con cautela.`);
  }
  if (table.expected_below_1 > 0) {
    notes.push(`${plural(table.expected_below_1, "celda tiene", "celdas tienen")} una frecuencia esperada menor que 1.`);
  }
  if (table.empty_cells > 0) {
    notes.push(`${plural(table.empty_cells, "combinación de categorías no aparece", "combinaciones de categorías no aparecen")} en los datos (conteo 0).`);
  }
  if (table.excluded_rows > 0) {
    notes.push(`${plural(table.excluded_rows, "fila no se incluye", "filas no se incluyen")} porque le falta el valor de «${table.x}» o de «${table.y}».`);
  }
  for (const [folded, column] of [[table.folded_rows, table.x], [table.folded_columns, table.y]] as const) {
    if (folded > 0) notes.push(`Por legibilidad, las ${folded} categorías menos frecuentes de «${column}» se agrupan en «Otras»; las frecuencias esperadas y las advertencias usan la tabla completa.`);
  }
  notes.push("Los conteos describen cuántas veces coinciden las categorías; una asociación no implica que una cause la otra.");
  return notes;
}
