import type { ReactNode } from "react";

import { cn } from "../../lib/utils";

interface EmptyStateProps {
  /** Ícone (ex.: <Folder /> do lucide). */
  icon?: ReactNode;
  title: ReactNode;
  hint?: ReactNode;
  action?: ReactNode;
  className?: string;
}

/** Estado vazio tipográfico: chip de ícone ember, título display + hint + ação opcional. */
export function EmptyState({ icon, title, hint, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center gap-3 rounded border border-dashed border-forge-line p-7 text-center",
        className
      )}
      style={{ background: "color-mix(in srgb, var(--bg-card) 50%, transparent)" }}
    >
      {icon && (
        <span
          className="flex h-11 w-11 items-center justify-center rounded-[12px] text-forge-amber"
          style={{
            background: "color-mix(in srgb, var(--ember) 8%, var(--bg-ink))",
            border: "1px solid color-mix(in srgb, var(--ember) 22%, transparent)"
          }}
        >
          {icon}
        </span>
      )}
      <div>
        <div className="font-display text-base uppercase tracking-[0.01em] text-forge-text">{title}</div>
        {hint && (
          <div className="mx-auto mt-1.5 max-w-[240px] text-[12.5px] leading-relaxed text-forge-muted">{hint}</div>
        )}
      </div>
      {action}
    </div>
  );
}
