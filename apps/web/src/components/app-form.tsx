import { Info } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";

import {
  incompleteNumericDrafts,
  normalizeNumberDraft,
  numberInputDraft,
  numericDraftPattern
} from "../shared/utils/common";
import type { AgentLLMConfig } from "../types/api";

export function InfoTip({ text }: { text: string }) {
  return (
    <span className="group relative inline-flex text-forge-muted" tabIndex={0} aria-label={text}>
      <Info size={13} className="cursor-help transition group-hover:text-forge-amber group-focus:text-forge-amber" />
      <span className="pointer-events-none absolute left-1/2 top-5 z-30 hidden w-64 -translate-x-1/2 rounded-md border border-forge-line bg-[#080908] p-2 text-left text-xs normal-case leading-5 text-forge-text shadow-soft group-hover:block group-focus:block">
        {text}
      </span>
    </span>
  );
}

export function SubFieldLabel({ text, tip, className = "" }: { text: string; tip?: string; className?: string }) {
  return (
    <span className={["flex items-center gap-1.5 text-[11px] uppercase text-forge-muted", className].join(" ")}>
      {text}
      {tip && <InfoTip text={tip} />}
    </span>
  );
}

export function Field({
  label,
  required = false,
  tip,
  children,
  className = ""
}: {
  label: string;
  required?: boolean;
  tip?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={["block space-y-2 text-sm", className].join(" ")}>
      <span className="flex items-center gap-1.5 text-xs uppercase text-forge-muted">
        {label}
        {required && <span className="text-forge-red">*</span>}
        {tip && <InfoTip text={tip} />}
      </span>
      {children}
    </label>
  );
}

export function AgentLLMNumberInput({
  label,
  field,
  value,
  tip,
  required = false,
  onChange
}: {
  label: string;
  field: keyof AgentLLMConfig;
  value: number | string;
  tip?: string;
  required?: boolean;
  onChange: (field: keyof AgentLLMConfig, value: AgentLLMConfig[keyof AgentLLMConfig]) => void;
}) {
  const [draftValue, setDraftValue] = useState(() => numberInputDraft(value));

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDraftValue(numberInputDraft(value));
  }, [value]);

  function commitDraft(rawValue: string, clearIncomplete = false) {
    const normalized = normalizeNumberDraft(rawValue);
    if (!normalized) {
      onChange(field, null);
      return;
    }
    if (incompleteNumericDrafts.has(normalized)) {
      if (clearIncomplete) {
        setDraftValue("");
        onChange(field, null);
      }
      return;
    }
    const parsedValue = Number(normalized);
    if (!Number.isFinite(parsedValue)) return;
    onChange(field, parsedValue);
    if (clearIncomplete) setDraftValue(String(parsedValue));
  }

  function handleChange(rawValue: string) {
    if (!numericDraftPattern.test(rawValue)) return;
    setDraftValue(rawValue);
    commitDraft(rawValue);
  }

  return (
    <Field label={label} tip={tip} required={required}>
      <input
        inputMode="decimal"
        value={draftValue}
        onBlur={() => commitDraft(draftValue, true)}
        onChange={(event) => handleChange(event.target.value)}
        className="h-10 w-full rounded-md border border-forge-line bg-[#0e0f0e] px-3 text-sm text-forge-text"
      />
    </Field>
  );
}

export function AgentLLMSelect({
  label,
  field,
  value,
  options,
  tip,
  required = false,
  onChange
}: {
  label: string;
  field: keyof AgentLLMConfig;
  value: string;
  options: string[];
  tip?: string;
  required?: boolean;
  onChange: (field: keyof AgentLLMConfig, value: AgentLLMConfig[keyof AgentLLMConfig]) => void;
}) {
  return (
    <Field label={label} tip={tip} required={required}>
      <select
        value={value}
        onChange={(event) => onChange(field, event.target.value || null)}
        className="h-10 w-full rounded-md border border-forge-line bg-[#0e0f0e] px-2 text-sm text-forge-text"
      >
        {options.map((option) => (
          <option key={option || "default"} value={option}>
            {option || "padrão"}
          </option>
        ))}
      </select>
    </Field>
  );
}
