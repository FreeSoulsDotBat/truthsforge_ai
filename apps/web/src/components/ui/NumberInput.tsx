import { forwardRef, useEffect, useState, type InputHTMLAttributes } from "react";

import {
  incompleteNumericDrafts,
  normalizeNumberDraft,
  numberInputDraft,
  numericDraftPattern
} from "../../shared/utils/common";
import { cn } from "../../lib/utils";

interface NumberInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "type"> {
  value: number | null;
  /** Unidade decorativa à direita (`tok`, `°`, `%`). Inclua no label para a11y. */
  suffix?: string;
  error?: boolean;
  onChange?: (value: number | null) => void;
}

/**
 * Input numérico que aceita rascunhos incompletos (`0.`, `-`, `1,`) enquanto digita e
 * normaliza no blur. Nunca use `<input type="number">` direto — ele descarta o draft.
 */
export const NumberInput = forwardRef<HTMLInputElement, NumberInputProps>(function NumberInput(
  { value, suffix, error = false, onChange, className, ...props },
  ref
) {
  const [draft, setDraft] = useState(() => numberInputDraft(value));

  // Reflete mudanças externas do valor sem atropelar o rascunho que o próprio input gerou.
  useEffect(() => {
    setDraft((current) => (normalizeNumberDraft(current) === String(value ?? "") ? current : numberInputDraft(value)));
  }, [value]);

  const handleChange = (raw: string) => {
    if (raw !== "" && !numericDraftPattern.test(raw)) return;
    setDraft(raw);
    if (raw === "") {
      onChange?.(null);
      return;
    }
    if (incompleteNumericDrafts.has(raw)) return;
    const parsed = Number(normalizeNumberDraft(raw));
    if (Number.isFinite(parsed)) onChange?.(parsed);
  };

  const invalid =
    error ||
    (draft !== "" && !incompleteNumericDrafts.has(draft) && !Number.isFinite(Number(normalizeNumberDraft(draft))));

  return (
    <div className="relative inline-block">
      <input
        ref={ref}
        type="text"
        inputMode="decimal"
        value={draft}
        aria-invalid={invalid || undefined}
        onChange={(event) => handleChange(event.target.value)}
        onBlur={() => setDraft(numberInputDraft(value))}
        className={cn(
          "h-9 rounded-sm border bg-forge-ink-deep px-3 font-mono text-[13px] text-forge-text outline-none focus-visible:border-forge-amber",
          invalid ? "border-forge-red" : "border-forge-line-soft",
          suffix && "pr-10",
          className
        )}
        {...props}
      />
      {suffix && (
        <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 font-mono text-[10.5px] text-forge-faint">
          {suffix}
        </span>
      )}
    </div>
  );
});
