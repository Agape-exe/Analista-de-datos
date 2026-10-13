import type { ComponentProps } from "react";
import { cn } from "../../lib/utils";

export function Badge({ className, tone = "neutral", ...props }: ComponentProps<"span"> & {
  tone?: "neutral" | "success" | "info" | "warning";
}) {
  return <span className={cn("badge", `badge-${tone}`, className)} {...props} />;
}
