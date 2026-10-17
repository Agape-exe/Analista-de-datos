import { useRef, useState, type FocusEvent, type PointerEvent, type ReactNode } from "react";

export interface TooltipRow {
  label: string;
  value: string;
}

interface TooltipState {
  x: number;
  y: number;
  title: string;
  rows: TooltipRow[];
}

/**
 * One tooltip per chart. Values lead and labels follow; content is rendered as React
 * text (never HTML strings) because column names come from user files.
 */
export function useChartTooltip() {
  const frame = useRef<HTMLDivElement>(null);
  const [tip, setTip] = useState<TooltipState | null>(null);

  function place(clientX: number, clientY: number, title: string, rows: TooltipRow[]) {
    const box = frame.current?.getBoundingClientRect();
    if (!box) return;
    setTip({ x: clientX - box.left, y: clientY - box.top, title, rows });
  }

  return {
    frame,
    hide: () => setTip(null),
    fromPointer: (event: PointerEvent, title: string, rows: TooltipRow[]) =>
      place(event.clientX, event.clientY, title, rows),
    fromFocus: (event: FocusEvent<Element>, title: string, rows: TooltipRow[]) => {
      const mark = event.currentTarget.getBoundingClientRect();
      place(mark.left + mark.width / 2, mark.top, title, rows);
    },
    tooltip: tip && <div className="chart-tooltip" role="status"
      style={{ left: tip.x, top: tip.y }}>
      <span className="chart-tooltip-title">{tip.title}</span>
      {tip.rows.map((row) => <span className="chart-tooltip-row" key={row.label}>
        <strong>{row.value}</strong><span>{row.label}</span>
      </span>)}
    </div>,
  };
}

export function ChartFrame({ children, frame, onLeave, label, stale }: {
  children: ReactNode;
  frame: React.RefObject<HTMLDivElement | null>;
  onLeave: () => void;
  label: string;
  stale?: boolean;
}) {
  return <div ref={frame} className={`chart-frame ${stale ? "stale" : ""}`} role="figure" aria-label={label}
    onPointerLeave={onLeave} onBlur={onLeave}>
    {children}
  </div>;
}
