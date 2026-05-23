import { cn } from "../../lib/utils";

interface StatusDotProps {
  /** Cor CSS (token). Padrão ember. */
  color?: string;
  size?: number;
  /** Anel de brilho ao redor (estado ativo/streaming). */
  pulse?: boolean;
  className?: string;
}

/** Ponto de status sólido com brilho opcional. */
export function StatusDot({ color = "var(--ember)", size = 7, pulse = false, className }: StatusDotProps) {
  return (
    <span
      className={cn("inline-block shrink-0 rounded-full", className)}
      style={{
        width: size,
        height: size,
        background: color,
        boxShadow: pulse ? `0 0 0 4px color-mix(in srgb, ${color} 30%, transparent)` : undefined
      }}
    />
  );
}

interface PulseProps {
  color?: string;
  size?: number;
  className?: string;
}

/** Ponto pulsante (anima `tfPulse`, definida em styles.css) — atividade contínua. */
export function Pulse({ color = "var(--ember)", size = 6, className }: PulseProps) {
  return (
    <span className={cn("relative inline-flex shrink-0", className)} style={{ width: size, height: size }}>
      <span
        className="absolute inset-0 rounded-full"
        style={{ background: color, animation: "tfPulse 2s infinite ease-in-out" }}
      />
      <span className="relative rounded-full" style={{ width: size, height: size, background: color }} />
    </span>
  );
}
