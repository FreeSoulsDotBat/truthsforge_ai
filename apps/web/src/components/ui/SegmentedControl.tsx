import type { ReactNode } from "react";

import { cn } from "../../lib/utils";

export interface SegmentOption {
  value: string;
  label: ReactNode;
}

interface SegmentedControlProps {
  options: SegmentOption[];
  value: string;
  onChange?: (value: string) => void;
  label?: string;
  className?: string;
}

/** Seletor 1-de-N (exclusivo). Para filtros independentes, use FilterPillRow. */
export function SegmentedControl({ options, value, onChange, label, className }: SegmentedControlProps) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={cn(
        "inline-flex gap-0.5 rounded-[10px] border border-forge-line-soft bg-forge-ink-deep p-[3px]",
        className
      )}
    >
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange?.(option.value)}
            className={cn(
              "rounded-[7px] px-3 py-1.5 text-xs transition-colors",
              active
                ? "bg-forge-panel font-medium text-forge-text shadow-[0_1px_0_var(--line-soft)]"
                : "text-forge-muted hover:text-forge-text"
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
