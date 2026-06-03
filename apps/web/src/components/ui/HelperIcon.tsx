import { Info } from "lucide-react";

import { Tooltip } from "./Tooltip";

interface HelperIconProps {
  /** Texto explicativo (obrigatório). Anunciado e exibido via componente Tooltip. */
  tip: string;
  size?: number;
  className?: string;
}

/**
 * Ícone de ajuda que explica um campo técnico. Foca por teclado e anuncia o tip,
 * exibindo o texto pelo componente Tooltip (visual/acessibilidade unificados v4).
 */
export function HelperIcon({ tip, size = 13, className }: HelperIconProps) {
  return (
    <Tooltip label={tip} className={className}>
      <span
        tabIndex={0}
        role="img"
        aria-label={tip}
        className="inline-flex cursor-help items-center text-forge-muted transition-colors hover:text-forge-amber focus-visible:text-forge-amber"
      >
        <Info size={size} strokeWidth={1.75} aria-hidden />
      </span>
    </Tooltip>
  );
}
