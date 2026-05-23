import type { CSSProperties, ReactNode } from "react";

import { cn } from "../../lib/utils";
import { StatusDot } from "./StatusDot";

interface ChipProps {
  /** Label técnico curto (mono uppercase, à esquerda). */
  label?: ReactNode;
  /** Valor em destaque (à direita). */
  value?: ReactNode;
  dot?: boolean;
  dotColor?: string;
  className?: string;
  style?: CSSProperties;
}

/** Pílula compacta `label · valor` com ponto de status opcional. */
export function Chip({ label, value, dot = false, dotColor = "var(--ember)", className, style }: ChipProps) {
  return (
    <span
      className={cn(
        "inline-flex h-7 items-center gap-2 rounded-full bg-forge-chip px-2.5 text-xs text-forge-text-soft",
        className
      )}
      style={style}
    >
      {dot && <StatusDot color={dotColor} />}
      {label != null && (
        <span className="font-mono text-[10.5px] uppercase tracking-[0.06em] text-forge-muted">{label}</span>
      )}
      {value != null && <span className="text-forge-text">{value}</span>}
    </span>
  );
}
