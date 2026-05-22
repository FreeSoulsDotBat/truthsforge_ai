import { Info } from "lucide-react";

import { cn } from "../../lib/utils";

interface HelperIconProps {
  /** Texto explicativo (obrigatório). Anunciado e exibido como tooltip nativo. */
  tip: string;
  size?: number;
  className?: string;
}

/**
 * Ícone de ajuda que explica um campo técnico. Foca por teclado e anuncia o tip.
 * TODO: integrar com o componente Tooltip (molécula) quando ele existir — hoje usa
 * `title`/`aria-label` nativo.
 */
export function HelperIcon({ tip, size = 13, className }: HelperIconProps) {
  return (
    <span
      tabIndex={0}
      role="img"
      aria-label={tip}
      title={tip}
      className={cn(
        "inline-flex cursor-help items-center text-forge-muted transition-colors hover:text-forge-amber focus-visible:text-forge-amber",
        className
      )}
    >
      <Info size={size} strokeWidth={1.75} aria-hidden />
    </span>
  );
}
