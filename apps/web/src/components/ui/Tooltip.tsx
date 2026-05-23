import type { ReactNode } from "react";

import { cn } from "../../lib/utils";

interface TooltipProps {
  label: ReactNode;
  hint?: ReactNode;
  /** Gatilho (deve ser focável para o tooltip aparecer no teclado). */
  children: ReactNode;
  className?: string;
}

/**
 * Tooltip CSS-only: aparece no hover e no focus-within do gatilho. Posiciona à direita.
 * Para casos com colisão de borda, prefira um popover com posicionamento dinâmico.
 */
export function Tooltip({ label, hint, children, className }: TooltipProps) {
  return (
    <span className={cn("group relative inline-flex", className)}>
      {children}
      <span
        role="tooltip"
        className="pointer-events-none absolute left-full top-1/2 z-50 ml-2 -translate-y-1/2 whitespace-nowrap rounded-[8px] border border-forge-line bg-forge-ink-deep px-3 py-2 opacity-0 shadow-soft transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100"
      >
        <span
          aria-hidden
          className="absolute -left-1 top-1/2 h-2 w-2 -translate-y-1/2 rotate-45 border-b border-l border-forge-line bg-forge-ink-deep"
        />
        <span className="block text-xs leading-snug text-forge-text">{label}</span>
        {hint && <span className="mt-1 block font-mono text-[9.5px] text-forge-faint">{hint}</span>}
      </span>
    </span>
  );
}
