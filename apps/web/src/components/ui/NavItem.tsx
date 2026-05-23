import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "../../lib/utils";
import { Mono } from "./Mono";

interface NavItemProps extends HTMLAttributes<HTMLDivElement> {
  icon?: ReactNode;
  label: ReactNode;
  active?: boolean;
  /** Contador numérico à direita (ex.: nº de itens). */
  count?: number;
  /** Selo textual à direita (ex.: "novo"). */
  badge?: ReactNode;
}

/**
 * Linha de navegação da sidebar. Ativo: fundo elevado, barra ember à esquerda,
 * ícone/contagem em ember.
 */
export function NavItem({ icon, label, active = false, count, badge, className, ...props }: NavItemProps) {
  return (
    <div
      aria-current={active ? "page" : undefined}
      className={cn(
        "relative flex h-[34px] items-center gap-2.5 rounded-sm px-2.5 text-[13px]",
        active ? "bg-forge-panel text-forge-text" : "text-forge-muted",
        className
      )}
      {...props}
    >
      {active && <span className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-forge-amber" />}
      {icon && <span className={active ? "text-forge-amber" : "text-forge-muted"}>{icon}</span>}
      <span className={cn("flex-1", active && "font-medium")}>{label}</span>
      {badge != null && (
        <Mono size={10} className={active ? "text-forge-amber" : "text-forge-faint"}>
          {badge}
        </Mono>
      )}
      {count !== undefined && (
        <Mono size={10} className={active ? "text-forge-text-soft" : "text-forge-faint"}>
          {count}
        </Mono>
      )}
    </div>
  );
}
