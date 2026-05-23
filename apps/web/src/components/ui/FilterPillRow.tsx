import type { CSSProperties } from "react";

import { cn } from "../../lib/utils";

export interface FilterOption {
  value: string;
  label: string;
}

interface FilterPillRowProps {
  options: FilterOption[];
  /** Conjunto de valores ativos (filtros independentes, não exclusivos). */
  selected: Set<string>;
  onChange?: (next: Set<string>) => void;
  label?: string;
  className?: string;
}

const ACTIVE_STYLE: CSSProperties = {
  background: "var(--bg-card)",
  borderColor: "var(--line-soft)",
  color: "var(--text)"
};
const INACTIVE_STYLE: CSSProperties = {
  background: "transparent",
  borderColor: "color-mix(in srgb, var(--line-soft) 30%, transparent)",
  color: "color-mix(in srgb, var(--muted) 60%, transparent)"
};

/** Linha de pills toggleáveis (filtros independentes). Para 1-de-N, use SegmentedControl. */
export function FilterPillRow({ options, selected, onChange, label, className }: FilterPillRowProps) {
  const toggle = (value: string) => {
    const next = new Set(selected);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    onChange?.(next);
  };

  return (
    <div role="group" aria-label={label} className={cn("flex flex-wrap gap-1.5", className)}>
      {options.map((option) => {
        const active = selected.has(option.value);
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            onClick={() => toggle(option.value)}
            className="cursor-pointer rounded-full border px-2.5 py-[3px] font-mono text-[10px] uppercase tracking-[0.12em] transition-colors"
            style={active ? ACTIVE_STYLE : INACTIVE_STYLE}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
