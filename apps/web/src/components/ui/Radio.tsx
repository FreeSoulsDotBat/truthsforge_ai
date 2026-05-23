import type { ReactNode } from "react";

import { cn } from "../../lib/utils";

interface RadioProps {
  checked?: boolean;
  onChange?: (checked: boolean) => void;
  /** Nome do grupo (exclusividade entre rádios). */
  name?: string;
  value?: string;
  label?: ReactNode;
  hint?: ReactNode;
  disabled?: boolean;
  className?: string;
}

/** Rádio (1-de-N dentro de um `name`). Input nativo sr-only + alvo customizado. */
export function Radio({
  checked = false,
  onChange,
  name,
  value,
  label,
  hint,
  disabled = false,
  className
}: RadioProps) {
  return (
    <label
      className={cn(
        "inline-flex items-start gap-2.5",
        disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer",
        className
      )}
    >
      <input
        type="radio"
        name={name}
        value={value}
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange?.(event.target.checked)}
        className="peer sr-only"
      />
      <span
        aria-hidden
        className={cn(
          "mt-px flex h-4 w-4 shrink-0 items-center justify-center rounded-full border-[1.5px] peer-focus-visible:ring-2 peer-focus-visible:ring-forge-amber",
          checked ? "border-forge-amber" : "border-forge-line"
        )}
      >
        {checked && (
          <span className="h-2 w-2 rounded-full bg-forge-amber" style={{ boxShadow: "0 0 6px var(--ember-glow)" }} />
        )}
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
