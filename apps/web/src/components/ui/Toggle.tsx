import type { ReactNode } from "react";

import { cn } from "../../lib/utils";

interface ToggleProps {
  checked?: boolean;
  onChange?: (checked: boolean) => void;
  label?: ReactNode;
  disabled?: boolean;
  className?: string;
}

/** Switch on/off. O conjunto inteiro é o controle (role=switch); label vira nome acessível. */
export function Toggle({ checked = false, onChange, label, disabled = false, className }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange?.(!checked)}
      className={cn("inline-flex items-center gap-2.5 disabled:cursor-not-allowed disabled:opacity-50", className)}
    >
      <span
        aria-hidden
        className={cn(
          "relative h-[18px] w-8 shrink-0 rounded-full border transition-colors",
          checked ? "border-forge-amber bg-forge-amber" : "border-forge-line bg-forge-ink-deep"
        )}
        style={checked ? { boxShadow: "0 0 8px color-mix(in srgb, var(--ember) 40%, transparent)" } : undefined}
      >
        <span
          className="absolute top-px h-[14px] w-[14px] rounded-full transition-[left]"
          style={{ left: checked ? 15 : 1, background: checked ? "var(--ember-ink)" : "var(--muted)" }}
        />
      </span>
      {label && <span className="text-[13px] text-forge-text">{label}</span>}
    </button>
  );
}
