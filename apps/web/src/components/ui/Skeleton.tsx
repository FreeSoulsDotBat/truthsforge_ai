import type { CSSProperties } from "react";

import { cn } from "../../lib/utils";

interface SkeletonProps {
  className?: string;
  style?: CSSProperties;
}

/** Bloco de carregamento com shimmer. Defina tamanho via `className` (ex.: `h-3 w-1/2`). */
export function Skeleton({ className, style }: SkeletonProps) {
  return (
    <span
      aria-hidden
      className={cn("block rounded-[4px]", className)}
      style={{
        background: "linear-gradient(90deg, var(--bg-card), var(--bg-hover), var(--bg-card))",
        backgroundSize: "200% 100%",
        animation: "tfShimmer 1.4s infinite",
        ...style
      }}
    />
  );
}

interface TypingDotsProps {
  className?: string;
  "aria-label"?: string;
}

/** Três pontos pulsantes (anima `tfDot`) — "JUDITE está respondendo". */
export function TypingDots({ className, "aria-label": ariaLabel = "carregando" }: TypingDotsProps) {
  return (
    <span className={cn("inline-flex items-center gap-1", className)} role="status" aria-label={ariaLabel}>
      {[0, 0.2, 0.4].map((delay) => (
        <span
          key={delay}
          aria-hidden
          className="h-1.5 w-1.5 rounded-full bg-forge-amber"
          style={{ animation: "tfDot 1s infinite ease-in-out", animationDelay: `${delay}s` }}
        />
      ))}
    </span>
  );
}
