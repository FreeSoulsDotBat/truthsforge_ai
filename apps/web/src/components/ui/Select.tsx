import { ChevronDown } from "lucide-react";
import { forwardRef, type SelectHTMLAttributes } from "react";

import { cn } from "../../lib/utils";

export interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "size"> {
  options: SelectOption[];
  size?: "sm" | "md" | "lg";
  error?: boolean;
}

const SIZE: Record<NonNullable<SelectProps["size"]>, string> = {
  sm: "h-7 text-xs",
  md: "h-9 text-[13px]",
  lg: "h-10 text-[13px]"
};

/** `<select>` nativo estilizado (a11y grátis). Para busca/rich options, use outra peça. */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { options, size = "md", error = false, className, disabled, ...props },
  ref
) {
  return (
    <div className={cn("relative inline-block", disabled && "opacity-50")}>
      <select
        ref={ref}
        disabled={disabled}
        aria-invalid={error || undefined}
        className={cn(
          "w-full appearance-none rounded-sm border bg-forge-ink-deep pl-3 pr-8 text-forge-text outline-none focus-visible:border-forge-amber disabled:cursor-not-allowed",
          error ? "border-forge-red" : "border-forge-line-soft",
          SIZE[size],
          className
        )}
        {...props}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <ChevronDown
        size={12}
        aria-hidden
        className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-forge-muted"
      />
    </div>
  );
});
