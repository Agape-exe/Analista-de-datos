import type { HeatmapChart } from "../../types/exploration";
import { ChartFrame, useChartTooltip } from "./ChartTooltip";
import { divergingColor, formatPValue, formatValue, inkOn, truncate } from "./chart-utils";

const CELL = 44;
const GAP = 2;
const LABELED_LIMIT = 12;

export function CorrelationHeatmap({ chart, onSelect, stale }: {
  chart: HeatmapChart;
  onSelect?: (x: string, y: string) => void;
  stale?: boolean;
}) {
  const { frame, hide, fromPointer, fromFocus, tooltip } = useChartTooltip();
  const n = chart.columns.length;
  const labelChars = Math.min(18, Math.max(...chart.columns.map((name) => name.length)));
  const left = labelChars * 7.2 + 16;
  const top = labelChars * 5.2 + 16;
  const width = left + n * CELL;
  const height = top + n * CELL;
  const labeled = n <= LABELED_LIMIT;
  const method = chart.method === "spearman" ? "ρ de Spearman" : "r de Pearson";

  return <div className="heatmap">
    <ChartFrame frame={frame} onLeave={hide} stale={stale}
      label={`Matriz de correlación (${method}) de ${n} columnas numéricas`}>
      <svg viewBox={`0 0 ${width} ${height}`} style={{ maxWidth: width }} className="chart-svg">
        {chart.columns.map((name, index) => <g key={name}>
          <text x={left - 8} y={top + index * CELL + CELL / 2} className="axis-label" textAnchor="end"
            dominantBaseline="middle">{truncate(name, 18)}<title>{name}</title></text>
          <text className="axis-label" textAnchor="start" dominantBaseline="middle"
            transform={`translate(${left + index * CELL + CELL / 2}, ${top - 8}) rotate(-45)`}>
            {truncate(name, 18)}<title>{name}</title></text>
        </g>)}
        {chart.values.map((row, i) => row.map((value, j) => {
          const x = chart.columns[j];
          const y = chart.columns[i];
          const rows = [
            { label: method, value: formatValue(value) },
            { label: "valor p sin corregir", value: i === j ? "—" : formatPValue(chart.p_values[i][j]) },
            { label: "pares", value: formatValue(chart.sample_sizes[i][j], 0) },
          ];
          const interactive = i !== j && value != null && onSelect;
          return <g key={`${i}-${j}`}
            className={`heat-cell ${interactive ? "clickable" : ""}`}
            tabIndex={labeled && interactive ? 0 : undefined}
            role={interactive ? "button" : undefined}
            aria-label={`${y} y ${x}: ${formatValue(value)}`}
            onPointerMove={(event) => fromPointer(event, `${y} × ${x}`, rows)}
            onFocus={(event) => fromFocus(event, `${y} × ${x}`, rows)}
            onClick={() => interactive && onSelect(y, x)}
            onKeyDown={(event) => {
              if (interactive && (event.key === "Enter" || event.key === " ")) {
                event.preventDefault();
                onSelect(y, x);
              }
            }}>
            <rect x={left + j * CELL + GAP / 2} y={top + i * CELL + GAP / 2} width={CELL - GAP} height={CELL - GAP}
              rx={3} fill={value == null ? "#ffffff" : divergingColor(value)}
              className={value == null ? "heat-empty" : undefined} />
            {labeled && <text x={left + j * CELL + CELL / 2} y={top + i * CELL + CELL / 2} textAnchor="middle"
              dominantBaseline="middle" className="cell-label" fill={value == null ? "#9aa3b2" : inkOn(value)}>
              {value == null ? "—" : value.toFixed(2)}</text>}
          </g>;
        }))}
      </svg>
      {tooltip}
    </ChartFrame>
    <div className="diverging-legend" aria-hidden="true">
      <span>−1 · negativa</span><span className="diverging-ramp" /><span>+1 · positiva</span>
    </div>
  </div>;
}
