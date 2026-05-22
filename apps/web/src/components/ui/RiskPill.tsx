import type { CSSProperties } from "react";

import { cn } from "../../lib/utils";

export type RiskLevel = "low" | "medium" | "high";

/** Mapeamento fixo nível → cor semântica (low=ok, medium=ember, high=err). */
const RISK_STYLE: Record<RiskLevel, CSSProperties> = {
  low: {
    color: "var(--ok)",
    background: "color-mix(in srgb, var(--ok) 14%, transparent)",
    borderColor: "color-mix(in srgb, var(--ok) 35%, transparent)"
  },
  medium: {
    color: "var(--ember)",
    background: "color-mix(in srgb, var(--ember) 14%, transparent)",
    borderColor: "color-mix(in srgb, var(--ember) 35%, transparent)"
  },
  high: {
    color: "var(--err)",
    background: "color-mix(in srgb, var(--err) 14%, transparent)",
    borderColor: "color-mix(in srgb, var(--err) 35%, transparent)"
  }
};

/** Pílula de nível de risco. Texto sempre presente (não confia só na cor). */
export function RiskPill({ level, className }: { level: RiskLevel; className?: string }) {
  return (
    <span
      aria-label={`risco ${level}`}
      className={cn(
        "inline-flex items-center rounded-[4px] border px-[9px] py-[3px] font-mono text-[10px] font-semibold uppercase tracking-[0.1em]",
        className
      )}
      style={RISK_STYLE[level]}
    >
      {level}
    </span>
  );
}
