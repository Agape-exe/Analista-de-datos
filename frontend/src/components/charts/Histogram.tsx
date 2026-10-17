import type { HistogramChart } from "../../types/exploration";
import { ChartFrame, useChartTooltip } from "./ChartTooltip";
import { formatTick, formatValue, linearScale, niceTicks } from "./chart-utils";

const W = 640;
const H = 300;
const M = { top: 16, right: 20, bottom: 44, left: 56 };
const GAP = 2;
const RADIUS = 4;

/** Column path with a 4px rounded data-end and a square baseline. */
function columnPath(x: number, y: number, width: number, baseline: number): string {
  const r = Math.min(RADIUS, width / 2, baseline - y);
  return `M${x},${baseline} V${y + r} Q${x},${y} ${x + r},${y} H${x + width - r} Q${x + width},${y} ${x + width},${y + r} V${baseline} Z`;
}

export function Histogram({ chart, stale }: { chart: HistogramChart; stale?: boolean }) {
  const { frame, hide, fromPointer, fromFocus, tooltip } = useChartTooltip();
  const lo = chart.edges[0];
  const hi = chart.edges.at(-1)!;
  const maxCount = Math.max(...chart.counts, 1);
  const yTicks = niceTicks(0, maxCount, 4);
  const top = Math.max(maxCount, yTicks.at(-1)!);
  const sx = linearScale([lo, hi], [M.left, W - M.right]);
  const sy = linearScale([0, top], [H - M.bottom, M.top]);
  const baseline = H - M.bottom;
  const xTicks = niceTicks(lo, hi, 6).filter((tick) => tick >= lo && tick <= hi);
  const total = chart.counts.reduce((sum, count) => sum + count, 0);

  return <ChartFrame frame={frame} onLeave={hide} stale={stale}
    label={`Histograma de ${chart.column}, ${chart.counts.length} intervalos`}>
    <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg">
      {yTicks.map((tick) => <g key={tick}>
        <line x1={M.left} x2={W - M.right} y1={sy(tick)} y2={sy(tick)} className="gridline" />
        <text x={M.left - 8} y={sy(tick)} className="tick-label" textAnchor="end" dominantBaseline="middle">{formatTick(tick)}</text>
      </g>)}
      {chart.counts.map((count, index) => {
        const x0 = sx(chart.edges[index]) + GAP / 2;
        const width = Math.max(sx(chart.edges[index + 1]) - sx(chart.edges[index]) - GAP, 1);
        const range = `${formatValue(chart.edges[index])} – ${formatValue(chart.edges[index + 1])}`;
        const rows = [{ label: "filas", value: formatValue(count, 0) },
          { label: "de lo observado", value: `${formatValue((100 * count) / (total || 1), 1)}%` }];
        return <g key={index} className="bar-mark" tabIndex={0} aria-label={`${range}: ${count} filas`}
          onPointerMove={(event) => fromPointer(event, range, rows)}
          onFocus={(event) => fromFocus(event, range, rows)}>
          <rect x={x0 - GAP / 2} y={M.top} width={width + GAP} height={baseline - M.top} fill="transparent" />
          {count > 0 && <path d={columnPath(x0, sy(count), width, baseline)} className="bar-fill" />}
        </g>;
      })}
      <line x1={M.left} x2={W - M.right} y1={baseline} y2={baseline} className="baseline" />
      {xTicks.map((tick) => <text key={tick} x={sx(tick)} y={baseline + 18} className="tick-label" textAnchor="middle">{formatTick(tick)}</text>)}
      <text x={(M.left + W - M.right) / 2} y={H - 6} textAnchor="middle" className="axis-title">{chart.column}</text>
    </svg>
    {tooltip}
  </ChartFrame>;
}
