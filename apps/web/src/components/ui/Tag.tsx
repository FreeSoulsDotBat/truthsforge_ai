import type { CSSProperties, HTMLAttributes } from "react";

import { cn } from "../../lib/utils";

export type TagTone = "neutral" | "ember" | "amethyst" | "azure" | "ok" | "warn" | "err";

/** Fundo/cor/borda por tom. color-mix mantém o tom translúcido sobre o fundo warm. */
const TONE_STYLE: Record<TagTone, CSSProperties> = {
  neutral: { background: "var(--bg-chip)", color: "var(--muted)", borderColor: "transparent" },
  ember: {
    background: "color-mix(in srgb, var(--ember) 12%, transparent)",
    color: "var(--ember)",
    borderColor: "color-mix(in srgb, var(--ember) 25%, transparent)"
  },
  amethyst: {
    background: "color-mix(in srgb, var(--amethyst) 14%, transparent)",
    color: "var(--amethyst)",
    borderColor: "color-mix(in srgb, var(--amethyst) 28%, transparent)"
  },
  azure: {
    background: "color-mix(in srgb, var(--azure) 12%, transparent)",
    color: "var(--azure)",
    borderColor: "color-mix(in srgb, var(--azure) 25%, transparent)"
  },
  ok: {
    background: "color-mix(in srgb, var(--ok) 12%, transparent)",
    color: "var(--ok)",
    borderColor: "transparent"
  },
  warn: {
    background: "color-mix(in srgb, var(--warn) 12%, transparent)",
    color: "var(--warn)",
    borderColor: "transparent"
  },
  err: {
    background: "color-mix(in srgb, var(--err) 12%, transparent)",
    color: "var(--err)",
    borderColor: "color-mix(in srgb, var(--err) 28%, transparent)"
  }
};

interface TagProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: TagTone;
}

/** Etiqueta tonal mono-uppercase para status, classificações e metadados. */
export function Tag({ tone = "neutral", className, style, ...props }: TagProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-[3px] font-mono text-[10.5px] uppercase tracking-[0.06em]",
        className
      )}
      style={{ ...TONE_STYLE[tone], ...style }}
      {...props}
    />
  );
}
