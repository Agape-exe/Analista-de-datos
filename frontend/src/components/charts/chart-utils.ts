export type Scale = (value: number) => number;

export function linearScale([d0, d1]: [number, number], [r0, r1]: [number, number]): Scale {
  const span = d1 - d0 || 1;
  return (value) => r0 + ((value - d0) / span) * (r1 - r0);
}

/** Round tick values ("nice numbers") covering [min, max]. */
export function niceTicks(min: number, max: number, count = 5): number[] {
  if (min === max) return [min];
  const raw = (max - min) / Math.max(count - 1, 1);
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= raw) ?? raw;
  const start = Math.ceil(min / step) * step;
  const ticks: number[] = [];
  for (let value = start; value <= max + step * 1e-9; value += step) ticks.push(Number(value.toPrecision(12)));
  return ticks;
}

/** Extend a domain to the outer nice ticks so marks never touch the plot edge. */
export function niceDomain(min: number, max: number, count = 5): [number, number] {
  if (min === max) return [min - 1, max + 1];
  const ticks = niceTicks(min, max, count);
  const step = ticks.length > 1 ? ticks[1] - ticks[0] : max - min;
  return [Math.floor(min / step) * step, Math.ceil(max / step) * step];
}

const compact = new Intl.NumberFormat("es-PE", { notation: "compact", maximumFractionDigits: 1 });
const precise = new Intl.NumberFormat("es-PE", { maximumFractionDigits: 3 });

export function formatTick(value: number): string {
  return Math.abs(value) >= 1000 ? compact.format(value) : precise.format(value);
}

export function formatValue(value: number | null | undefined, digits = 3): string {
  if (value == null || !Number.isFinite(value)) return "—";
  if (Math.abs(value) >= 1e5) return compact.format(value);
  return new Intl.NumberFormat("es-PE", { maximumFractionDigits: digits }).format(value);
}

export function formatPValue(value: number | null | undefined): string {
  if (value == null) return "—";
  if (value < 0.001) return "<0.001";
  return value.toFixed(3);
}

// Diverging blue <-> red with a neutral gray midpoint (never a hue at zero).
const NEUTRAL = [240, 239, 236];
const POSITIVE = [28, 92, 171];
const NEGATIVE = [180, 50, 50];

export function divergingColor(value: number): string {
  const t = Math.min(Math.abs(value), 1);
  const pole = value >= 0 ? POSITIVE : NEGATIVE;
  const [r, g, b] = NEUTRAL.map((channel, index) => Math.round(channel + (pole[index] - channel) * t));
  return `rgb(${r}, ${g}, ${b})`;
}

/** Ink that stays legible on a diverging cell. */
export function inkOn(value: number): string {
  return Math.abs(value) > 0.55 ? "#ffffff" : "#242c3e";
}

export function truncate(label: string, max: number): string {
  return label.length > max ? `${label.slice(0, max - 1)}…` : label;
}
