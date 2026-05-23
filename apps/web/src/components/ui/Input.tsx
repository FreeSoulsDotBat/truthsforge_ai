import { forwardRef, type InputHTMLAttributes, type ReactNode } from "react";

import { cn } from "../../lib/utils";

interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "prefix"> {
  mono?: boolean;
  error?: boolean;
  /** Conteúdo à esquerda dentro da moldura (redefine o atributo HTML nativo `prefix`). */
  prefix?: ReactNode;
  suffix?: ReactNode;
}

/** Input de linha única com prefix/suffix opcionais e variante mono. */
export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { mono = false, error = false, prefix, suffix, className, ...props },
  ref
) {
  return (
    <div
      className={cn(
        "flex h-9 items-center gap-2 rounded-[10px] border bg-forge-ink-deep px-3 focus-within:border-forge-amber",
        error ? "border-forge-red" : "border-forge-line-soft"
      )}
    >
      {prefix && <span className="shrink-0 text-forge-muted">{prefix}</span>}
      <input
        ref={ref}
        aria-invalid={error || undefined}
        className={cn(
          "min-w-0 flex-1 bg-transparent text-[13px] text-forge-text outline-none placeholder:text-forge-muted",
          mono ? "font-mono" : "font-sans",
          className
        )}
        {...props}
      />
      {suffix && <span className="shrink-0 font-mono text-[10px] text-forge-muted">{suffix}</span>}
    </div>
  );
});
