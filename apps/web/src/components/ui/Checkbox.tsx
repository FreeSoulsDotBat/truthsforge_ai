import { Check } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "../../lib/utils";

interface CheckboxProps {
  checked?: boolean;
  onChange?: (checked: boolean) => void;
  label?: ReactNode;
  hint?: ReactNode;
  disabled?: boolean;
  className?: string;
}

/** Checkbox com label/hint. Input nativo (sr-only) preserva foco e semântica de formulário. */
export function Checkbox({ checked = false, onChange, label, hint, disabled = false, className }: CheckboxProps) {
  return (
    <label
      className={cn(
        "inline-flex items-start gap-2.5",
        disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer",
        className
      )}
    >
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange?.(event.target.checked)}
        className="peer sr-only"
      />
      <span
        aria-hidden
        className={cn(
          "mt-px flex h-4 w-4 shrink-0 items-center justify-center rounded-[4px] border-[1.5px] peer-focus-visible:ring-2 peer-focus-visible:ring-forge-amber",
          checked ? "border-forge-amber bg-forge-amber" : "border-forge-line"
        )}
      >
        {checked && <Check size={11} strokeWidth={3} style={{ color: "var(--ember-ink)" }} />}
      </span>
      {(label || hint) && (
        <span className="leading-tight">
          {label && <span className="block text-[13px] text-forge-text">{label}</span>}
          {hint && <span className="mt-0.5 block font-mono text-[10px] text-forge-muted">{hint}</span>}
        </span>
      )}
    </label>
  );
}
