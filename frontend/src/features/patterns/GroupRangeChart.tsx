import { ChartFrame, useChartTooltip } from "../../components/charts/ChartTooltip";
import { formatTick, formatValue, linearScale, niceDomain, niceTicks, truncate } from "../../components/charts/chart-utils";
import type { PatternGroup } from "./patterns-contract";

const W = 960;
const ROW = 36;
const BOX = 16;
const LEFT = 160;
const RIGHT = 150;
const M = { top: 12, bottom: 44 };

type Drawable = PatternGroup & { min: number; q1: number; median: number; q3: number; max: number };
const drawable = (group: PatternGroup): group is Drawable =>
  [group.min, group.q1, group.median, group.q3, group.max].every((value) => value !== null);

/** One row per existing group: min–max line, Q1–Q3 box, median mark and n as a direct label. */
export function GroupRangeChart({ column, groupBy, groups, stale }: {
  column: string;
  groupBy: string;
  groups: PatternGroup[];
  stale?: boolean;
}) {
  const { frame, hide, fromPointer, fromFocus, tooltip } = useChartTooltip();
  const values = groups.filter(drawable).flatMap((group) => [group.min, group.max]);
  const domain = values.length ? niceDomain(Math.min(...values), Math.max(...values)) : [0, 1] as [number, number];
  const sx = linearScale(domain, [LEFT, W - RIGHT]);
  const ticks = niceTicks(...domain);
  const H = M.top + groups.length * ROW + M.bottom;

  return <div className="patterns-chart"><ChartFrame frame={frame} onLeave={hide} stale={stale}
    label={`Distribución de ${column} por cada categoría de ${groupBy}`}>
    <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg">
      {ticks.map((tick) => <g key={tick}>
        <line x1={sx(tick)} x2={sx(tick)} y1={M.top} y2={H - M.bottom} className="gridline" />
        <text x={sx(tick)} y={H - M.bottom + 18} className="tick-label" textAnchor="middle">{formatTick(tick)}</text>
      </g>)}
      {groups.map((group, index) => {
        const cy = M.top + index * ROW + ROW / 2;
        const rows = [
          { label: "observaciones", value: formatValue(group.observed, 0) },
          { label: "mediana", value: formatValue(group.median) },
          { label: "media", value: formatValue(group.mean) },
          { label: "Q1 – Q3", value: `${formatValue(group.q1)} – ${formatValue(group.q3)}` },
          { label: "mín – máx", value: `${formatValue(group.min)} – ${formatValue(group.max)}` },
        ];
        const note = group.observed === 0 ? "sin valores" : group.smallSample ? "muestra pequeña" : "";
        return <g key={group.label} className={`range-mark ${group.smallSample ? "small-sample" : ""}`} tabIndex={0}
          aria-label={`${group.label}: ${group.observed} observaciones, mediana ${formatValue(group.median)}${note ? `, ${note}` : ""}`}
          onPointerMove={(event) => fromPointer(event, group.label, rows)}
          onFocus={(event) => fromFocus(event, group.label, rows)}>
          <rect x={0} y={cy - ROW / 2} width={W} height={ROW} fill="transparent" />
          <text x={LEFT - 10} y={cy} textAnchor="end" dominantBaseline="middle" className="axis-label">
            {truncate(group.label, 20)}<title>{group.label}</title></text>
          {drawable(group) && <>
            <line x1={sx(group.min)} x2={sx(group.max)} y1={cy} y2={cy} className="whisker" />
            <rect x={sx(group.q1)} y={cy - BOX / 2} width={Math.max(sx(group.q3) - sx(group.q1), 2)} height={BOX} rx={4}
              className="box-fill range-box" />
            <line x1={sx(group.median)} x2={sx(group.median)} y1={cy - BOX / 2} y2={cy + BOX / 2} className="median-line" />
          </>}
          <text x={W - RIGHT + 10} y={cy} dominantBaseline="middle" className="tick-label">
            n = {formatValue(group.observed, 0)}{note && <tspan className="range-note"> · {note}</tspan>}</text>
        </g>;
      })}
      <text x={(LEFT + W - RIGHT) / 2} y={H - 6} textAnchor="middle" className="axis-title">{column}</text>
    </svg>
    {tooltip}
  </ChartFrame></div>;
}
