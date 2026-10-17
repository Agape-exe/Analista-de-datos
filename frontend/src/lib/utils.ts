import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(value: number) {
  return new Intl.NumberFormat("es-PE").format(value);
}

export function formatPercentage(value: number) {
  return `${new Intl.NumberFormat("es-PE", { maximumFractionDigits: 2 }).format(value)}%`;
}
