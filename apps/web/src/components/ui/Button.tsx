import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type ButtonHTMLAttributes } from "react";

import { cn } from "../../lib/utils";

const button = cva(
  "inline-flex items-center justify-center gap-2 transition disabled:cursor-not-allowed disabled:opacity-50",
  {
    variants: {
      variant: {
        // `default` reproduz exatamente o Button pré-v4 — usos existentes não mudam.
        default:
          "h-10 rounded-md border border-forge-line bg-[#1a1d20] px-3 text-sm font-medium text-forge-text hover:bg-[#222a2f]",
        // Ação primária da marca: ember tingido, mono uppercase.
        primary:
          "h-9 rounded-md border px-3.5 font-mono text-[11px] font-semibold uppercase tracking-[0.12em] text-forge-amber border-[color-mix(in_srgb,var(--ember)_40%,transparent)] bg-[color-mix(in_srgb,var(--ember)_14%,var(--bg-card))] hover:bg-[color-mix(in_srgb,var(--ember)_20%,var(--bg-card))]",
        // Secundária/discreta.
        ghost:
          "h-9 rounded-md border border-forge-line-soft px-3 font-mono text-[10px] uppercase tracking-[0.1em] text-forge-muted hover:border-forge-line hover:text-forge-text",
        // Apenas ícone (quadrado).
        icon: "h-9 w-9 rounded-md border border-forge-line-soft text-forge-muted hover:border-forge-line hover:text-forge-text"
      }
    },
    defaultVariants: { variant: "default" }
  }
);

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof button> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, type = "button", ...props },
  ref
) {
  return <button ref={ref} type={type} className={cn(button({ variant }), className)} {...props} />;
});
