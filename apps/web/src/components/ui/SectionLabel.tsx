import type { ReactNode } from "react";

import { cn } from "../../lib/utils";

interface SectionLabelProps {
  children: ReactNode;
  /** Ação opcional alinhada à direita (botão/ícone). */
  action?: ReactNode;
  className?: string;
}

/** Cabeçalho de seção mono-uppercase calmo (sidebar, painéis). */
export function SectionLabel({ children, action, className }: SectionLabelProps) {
  return (
    <div className={cn("flex items-center justify-between px-3 pb-1.5 pt-4", className)}>
      <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-forge-faint">{children}</span>
      {action}
    </div>
  );
}
