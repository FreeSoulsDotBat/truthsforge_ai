import type { CSSProperties } from "react";

import { cn } from "../../lib/utils";

interface DividerProps {
  vertical?: boolean;
  className?: string;
  style?: CSSProperties;
}

/** Separador fino (`forge-line-soft`) — horizontal por padrão, vertical opt-in. */
export function Divider({ vertical = false, className, style }: DividerProps) {
  return (
    <span
      role="separator"
      aria-orientation={vertical ? "vertical" : "horizontal"}
      className={cn("block bg-forge-line-soft", vertical ? "w-px self-stretch" : "h-px w-full", className)}
      style={style}
    />
  );
}
