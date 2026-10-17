import type { BoxPlotChart } from "../../types/exploration";
import { ChartFrame, useChartTooltip } from "./ChartTooltip";
import { formatTick, formatValue, linearScale, niceDomain, niceTicks, truncate } from "./chart-utils";

const W = 640;
const ROW = 40;
const BOX = 20;
const M = { top: 12, right: 24, bottom: 44 };

/** Horizontal box plots so long category labels stay readable. */
export function BoxPlot({ chart, stale }: { chart: BoxPlotChart; stale?: boolean }) {
  const { frame, hide, fromPointer, fromFocus, tooltip } = useChartTooltip();
  const values = chart.boxes.flatMap((box) => [box.lower_whisker, box.upper_whisker, ...box.outliers]);
  const domain = niceDomain(Math.min(...values), Math.max(...values));
  const grouped = chart.group_by != null;
  const left = grouped ? 128 : 24;
  const H = M.top + chart.boxes.length * ROW + M.bottom;
  const sx = linearScale(domain, [left, W - M.right]);
  const ticks = niceTicks(...domain);

  return <ChartFrame frame={frame} onLeave={hide} stale={stale}
    label={`Box plot of ${chart.column}${grouped ? ` by ${chart.group_by}` : ""}`}>
    <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg">
      {ticks.map((tick) => <g key={tick}>
        <line x1={sx(tick)} x2={sx(tick)} y1={M.top} y2={H - M.bottom} className="gridline" />
        <text x={sx(tick)} y={H - M.bottom + 18} className="tick-label" textAnchor="middle">{formatTick(tick)}</text>
      </g>)}
      {chart.boxes.map((box, index) => {
        const cy = M.top + index * ROW + ROW / 2;
        const title = grouped ? box.label : chart.column;
        const rows = [
          { label: "median", value: formatValue(box.median) },
          { label: "Q1 – Q3", value: `${formatValue(box.q1)} – ${formatValue(box.q3)}` },
          { label: "whiskers", value: `${formatValue(box.lower_whisker)} – ${formatValue(box.upper_whisker)}` },
          { label: "rows", value: formatValue(box.count, 0) },
          { label: "outliers", value: formatValue(box.outlier_count, 0) },
        ];
        return <g key={box.label} className="box-mark" tabIndex={0}
          aria-label={`${title}: median ${formatValue(box.median)}, ${box.count} rows`}
          onPointerMove={(event) => fromPointer(event, title, rows)}
          onFocus={(event) => fromFocus(event, title, rows)}>
          <rect x={left} y={cy - ROW / 2} width={W - left - M.right} height={ROW} fill="transparent" />
          {grouped && <text x={left - 10} y={cy} textAnchor="end" dominantBaseline="middle" className="axis-label">
            {truncate(box.label, 18)}<title>{box.label}</title></text>}
          <line x1={sx(box.lower_whisker)} x2={sx(box.q1)} y1={cy} y2={cy} className="whisker" />
          <line x1={sx(box.q3)} x2={sx(box.upper_whisker)} y1={cy} y2={cy} className="whisker" />
          <line x1={sx(box.lower_whisker)} x2={sx(box.lower_whisker)} y1={cy - 6} y2={cy + 6} className="whisker" />
          <line x1={sx(box.upper_whisker)} x2={sx(box.upper_whisker)} y1={cy - 6} y2={cy + 6} className="whisker" />
          <rect x={sx(box.q1)} y={cy - BOX / 2} width={Math.max(sx(box.q3) - sx(box.q1), 2)} height={BOX} rx={4} className="box-fill" />
          <line x1={sx(box.median)} x2={sx(box.median)} y1={cy - BOX / 2} y2={cy + BOX / 2} className="median-line" />
          {box.outliers.map((value, outlier) => <circle key={outlier} cx={sx(value)} cy={cy} r={4} className="outlier-dot" />)}
        </g>;
      })}
      <text x={(left + W - M.right) / 2} y={H - 6} textAnchor="middle" className="axis-title">{chart.column}</text>
    </svg>
    {tooltip}
  </ChartFrame>;
}
