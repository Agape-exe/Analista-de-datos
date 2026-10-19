import { TriangleAlert } from "lucide-react";
import { useState } from "react";
import { formatValue } from "../../components/charts/chart-utils";
import type { ContingencyChart } from "../../types/exploration";
import { contingencyWarnings } from "./contingency-contract";

type Mode = "count" | "row" | "column" | "total";
const MODES: { value: Mode; label: string }[] = [
  { value: "count", label: "Conteos" },
  { value: "row", label: "% de fila" },
  { value: "column", label: "% de columna" },
  { value: "total", label: "% del total" },
];

/** Single-hue sequential wash: magnitude only, the number is always printed. */
const shade = (value: number, max: number) => `rgba(42, 120, 214, ${max > 0 ? 0.05 + 0.35 * (value / max) : 0})`;

export function ContingencyTable({ table, stale }: { table: ContingencyChart; stale?: boolean }) {
  const [mode, setMode] = useState<Mode>("count");
  const max = Math.max(...table.counts.flat());
  const label = (labels: string[], index: number, folded: number) =>
    folded > 0 && index === labels.length - 1 ? `Otras (${folded} categorías)` : labels[index];
  const percent = (part: number, whole: number) => whole > 0 ? `${formatValue((100 * part) / whole, 1)} %` : "—";
  const share = (count: number, row: number, column: number) =>
    percent(count, mode === "row" ? table.row_totals[row] : mode === "column" ? table.column_totals[column] : table.total);
  // Margins: the percentage base gives 100 %; the other margin shows the overall distribution.
  const rowMargin = (row: number) => mode === "count" ? formatValue(table.row_totals[row], 0)
    : mode === "row" ? "100 %" : percent(table.row_totals[row], table.total);
  const columnMargin = (column: number) => mode === "count" ? formatValue(table.column_totals[column], 0)
    : mode === "column" ? "100 %" : percent(table.column_totals[column], table.total);
  const sparse = table.expected.some((row) => row.some((value) => value !== null && value < 5));

  return <div className={`contingency ${stale ? "stale" : ""}`}>
    <div className="contingency-toolbar" role="group" aria-label="Valores mostrados">
      {MODES.map((item) => <button key={item.value} type="button" className={`chip ${mode === item.value ? "active" : ""}`}
        aria-pressed={mode === item.value} onClick={() => setMode(item.value)}>{item.label}</button>)}
    </div>
    <div className="table-scroll" role="region" aria-label={`Tabla de contingencia de ${table.x} y ${table.y}`} tabIndex={0}>
      <table className="contingency-table">
        <caption className="contingency-caption">Filas: <strong>{table.x}</strong> · Columnas: <strong>{table.y}</strong> · n = {formatValue(table.total, 0)}</caption>
        <thead><tr>
          <th scope="col" aria-label={`${table.x} \\ ${table.y}`} />
          {table.column_labels.map((_, index) => <th key={index} scope="col">{label(table.column_labels, index, table.folded_columns)}</th>)}
          <th scope="col">Total</th>
        </tr></thead>
        <tbody>
          {table.counts.map((row, rowIndex) => <tr key={rowIndex}>
            <th scope="row">{label(table.row_labels, rowIndex, table.folded_rows)}</th>
            {row.map((count, columnIndex) => {
              const expected = table.expected[rowIndex][columnIndex];
              const low = expected !== null && expected < 5;
              return <td key={columnIndex} style={{ background: shade(count, max) }}
                title={expected === null ? undefined : `Esperado si fueran independientes: ${formatValue(expected, 2)}`}>
                {mode === "count" ? formatValue(count, 0) : share(count, rowIndex, columnIndex)}
                {low && <sup aria-label="frecuencia esperada menor que 5">†</sup>}
              </td>;
            })}
            <td className="total">{rowMargin(rowIndex)}</td>
          </tr>)}
        </tbody>
        <tfoot><tr>
          <th scope="row">Total</th>
          {table.column_totals.map((_, columnIndex) => <td key={columnIndex} className="total">{columnMargin(columnIndex)}</td>)}
          <td className="total">{mode === "count" ? formatValue(table.total, 0) : "100 %"}</td>
        </tr></tfoot>
      </table>
    </div>
    {sparse && <p className="chart-note">† Frecuencia esperada menor que 5 si las variables fueran independientes.</p>}
    <ul className="contingency-warnings" aria-label="Advertencias de la tabla de contingencia">
      {contingencyWarnings(table).map((note, index, all) => <li key={note}>
        {index < all.length - 1 && <TriangleAlert size={13} aria-hidden="true" />}{note}</li>)}
    </ul>
  </div>;
}
