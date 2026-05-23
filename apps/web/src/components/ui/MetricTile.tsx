import { cn } from "../../lib/utils";
import { Mono } from "./Mono";

interface MetricTileProps {
  label: string;
  value: number | string;
  tone?: "text" | "ember" | "azure";
  className?: string;
}

const TONE_COLOR: Record<NonNullable<MetricTileProps["tone"]>, string> = {
  text: "var(--text)",
  ember: "var(--ember)",
  azure: "var(--azure)"
};

/** Tile de métrica densa (valor em display, label mono). Hero stats usam Stat. */
export function MetricTile({ label, value, tone = "text", className }: MetricTileProps) {
  return (
    <div
      aria-label={`${label}: ${value}`}
      className={cn("rounded-md border border-forge-line-soft bg-forge-panel px-2.5 py-2", className)}
    >
      <Mono size={10} className="uppercase tracking-[0.1em] text-forge-muted" aria-hidden>
        {label}
      </Mono>
      <div className="mt-0.5 font-display text-lg tracking-[0.005em]" style={{ color: TONE_COLOR[tone] }} aria-hidden>
        {value}
      </div>
    </div>
  );
}
