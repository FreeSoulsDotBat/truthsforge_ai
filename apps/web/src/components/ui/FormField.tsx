import { Shield } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "../../lib/utils";
import { HelperIcon } from "./HelperIcon";

interface FormFieldProps {
  label: ReactNode;
  required?: boolean;
  /** Tooltip de ajuda ao lado do label. */
  tip?: string;
  hint?: ReactNode;
  error?: ReactNode;
  children: ReactNode;
  className?: string;
}

/** Envólucro de campo: label mono + obrigatório + ajuda, com hint/erro abaixo do controle. */
export function FormField({ label, required, tip, hint, error, children, className }: FormFieldProps) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <div className="flex items-center gap-1.5">
        <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-forge-faint">{label}</span>
        {required && <span className="text-xs text-forge-amber">*</span>}
        {tip && <HelperIcon tip={tip} size={12} />}
      </div>
      {children}
      {hint && !error && <span className="font-mono text-[10px] text-forge-muted">{hint}</span>}
      {error && (
        <span className="flex items-center gap-1.5 text-[11px] text-forge-red">
          <Shield size={10} strokeWidth={1.75} aria-hidden />
          {error}
        </span>
      )}
    </div>
  );
}
