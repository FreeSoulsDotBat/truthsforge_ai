import { cn } from "../../lib/utils";
import { Mono } from "./Mono";

interface SliderProps {
  value: number;
  onChange?: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  label?: string;
  /** Sufixo exibido ao lado do valor (ex.: "%"). */
  unit?: string;
  disabled?: boolean;
  className?: string;
}

/** Range nativo com trilho ember (accent-color) + linha de label/valor opcional. */
export function Slider({
  value,
  onChange,
  min = 0,
  max = 100,
  step = 1,
  label,
  unit = "%",
  disabled = false,
  className
}: SliderProps) {
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {label && (
        <div className="flex justify-between">
          <Mono size={10} className="uppercase tracking-[0.12em] text-forge-faint">
            {label}
          </Mono>
          <Mono size={11} className="text-forge-text">
            {value}
            {unit}
          </Mono>
        </div>
      )}
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        aria-label={label}
        onChange={(event) => onChange?.(Number(event.target.value))}
        className="h-1.5 w-full cursor-pointer rounded-full bg-forge-ink-deep accent-[var(--ember)] disabled:cursor-not-allowed disabled:opacity-50"
      />
    </div>
  );
}
