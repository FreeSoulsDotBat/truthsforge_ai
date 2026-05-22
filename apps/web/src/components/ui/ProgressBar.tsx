import { cn } from "../../lib/utils";

type ProgressTone = "ember" | "amethyst" | "ok";

const TONE_COLOR: Record<ProgressTone, string> = {
  ember: "var(--ember)",
  amethyst: "var(--amethyst)",
  ok: "var(--ok)"
};

interface ProgressBarProps {
  /** 0–100. Ignorado quando `indeterminate`. */
  value?: number;
  indeterminate?: boolean;
  tone?: ProgressTone;
  /** aria-label obrigatório para leitores de tela (ex.: "Importando…"). */
  label?: string;
  className?: string;
}

/** Barra de progresso linear (4px). Determinada ou shimmer indeterminado. */
export function ProgressBar({ value = 0, indeterminate = false, tone = "ember", label, className }: ProgressBarProps) {
  const color = TONE_COLOR[tone];
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={indeterminate ? undefined : 0}
      aria-valuemax={indeterminate ? undefined : 100}
      aria-valuenow={indeterminate ? undefined : clamped}
      className={cn(
        "relative h-1 w-full overflow-hidden rounded-[2px] border border-forge-line-soft bg-forge-ink-deep",
        className
      )}
    >
      {indeterminate ? (
        <div
          className="absolute inset-0"
          style={{
            background: `linear-gradient(90deg, transparent, ${color}, transparent)`,
            backgroundSize: "200% 100%",
            animation: "tfShimmer 1.6s linear infinite"
          }}
        />
      ) : (
        <div
          className="h-full transition-[width] duration-300 ease-out"
          style={{ width: `${clamped}%`, background: color, boxShadow: `0 0 8px ${color}` }}
        />
      )}
    </div>
  );
}
