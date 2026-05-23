import { forwardRef, useEffect, useImperativeHandle, useRef, type TextareaHTMLAttributes } from "react";

import { cn } from "../../lib/utils";

interface TextareaProps extends Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "rows"> {
  rows?: number;
  /** Quando definido, cresce com o conteúdo até este nº de linhas (depois rola). */
  maxRows?: number;
  mono?: boolean;
  resize?: "none" | "vertical";
  error?: boolean;
}

/** Campo multilinha. Auto-grow opcional (`maxRows`), variante mono, resize-y opt-in. */
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { rows = 3, maxRows, mono = false, resize = "vertical", error = false, className, style, value, ...props },
  ref
) {
  const innerRef = useRef<HTMLTextAreaElement>(null);
  useImperativeHandle(ref, () => innerRef.current as HTMLTextAreaElement, []);

  const autoGrow = maxRows != null;

  useEffect(() => {
    const el = innerRef.current;
    if (!el || !autoGrow) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [value, autoGrow]);

  return (
    <textarea
      ref={innerRef}
      rows={rows}
      value={value}
      aria-invalid={error || undefined}
      className={cn(
        "w-full rounded-[10px] border bg-forge-ink-deep px-3 py-2.5 text-[13px] text-forge-text outline-none focus-visible:border-forge-amber",
        error ? "border-forge-red" : "border-forge-line-soft",
        mono ? "font-mono" : "font-sans",
        resize === "vertical" ? "resize-y" : "resize-none",
        className
      )}
      style={maxRows != null ? { maxHeight: `${maxRows * 1.6}em`, overflowY: "auto", ...style } : style}
      {...props}
    />
  );
});
