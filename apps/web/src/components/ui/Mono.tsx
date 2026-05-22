import type { HTMLAttributes } from "react";

import { cn } from "../../lib/utils";

interface MonoProps extends HTMLAttributes<HTMLSpanElement> {
  /** Tamanho da fonte em px (escalas finas do design não cabem na escala Tailwind). */
  size?: number;
}

/**
 * Texto monoespaçado da identidade v4 — metadados, labels técnicos, valores.
 * Cor padrão `forge-muted`; sobrescreva via `className` (ex.: `text-forge-faint`).
 */
export function Mono({ size = 11, className, style, ...props }: MonoProps) {
  return (
    <span
      className={cn("font-mono tracking-[0.04em] text-forge-muted", className)}
      style={{ fontSize: size, ...style }}
      {...props}
    />
  );
}
