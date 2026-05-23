import { cn } from "../../lib/utils";

interface BrandSymbolProps {
  size?: number;
  /** Cor do traço (token). Padrão ember. */
  color?: string;
  className?: string;
}

/**
 * Marca da forja: arco + faísca + bigorna sobre um chip com gradiente ember.
 * Referência dos grafismos do manual de ID Visual v4. Apenas decorativo.
 */
export function BrandSymbol({ size = 32, color = "var(--ember)", className }: BrandSymbolProps) {
  return (
    <span
      className={cn("relative inline-flex shrink-0 items-center justify-center rounded-sm", className)}
      aria-hidden="true"
      style={{
        width: size,
        height: size,
        background: "linear-gradient(155deg, color-mix(in srgb, var(--ember) 22%, var(--bg-ink)), var(--bg-ink) 70%)",
        border: "1px solid color-mix(in srgb, var(--ember) 30%, var(--line))",
        boxShadow: "inset 0 0 0 1px color-mix(in srgb, var(--ember) 8%, transparent), 0 0 18px -10px var(--ember-glow)"
      }}
    >
      <svg width={size * 0.55} height={size * 0.55} viewBox="0 0 24 24" fill="none">
        {/* Arco da forja — curva como o grafismo da marca */}
        <path d="M4 18 C 4 10, 10 4, 18 6" stroke={color} strokeWidth="2.2" strokeLinecap="round" fill="none" />
        {/* Faísca — losango */}
        <path d="M18 14 L19.5 16 L18 18 L16.5 16 Z" fill={color} />
        {/* Base da bigorna — traço horizontal */}
        <path d="M5 20 L13 20" stroke={color} strokeWidth="2" strokeLinecap="round" opacity="0.6" />
      </svg>
    </span>
  );
}
