import type { ReactNode } from "react";

import { cn } from "../../lib/utils";

export type ToastTone = "ok" | "ember" | "amethyst" | "azure" | "err";

const TONE: Record<ToastTone, { color: string; glow: string }> = {
  ok: { color: "var(--ok)", glow: "rgba(90, 207, 140, 0.25)" },
  ember: { color: "var(--ember)", glow: "var(--ember-glow)" },
  amethyst: { color: "var(--amethyst)", glow: "var(--amethyst-glow)" },
  azure: { color: "var(--azure)", glow: "var(--azure-glow)" },
  err: { color: "var(--err)", glow: "rgba(255, 90, 74, 0.25)" }
};

interface ToastProps {
  tone?: ToastTone;
  icon?: ReactNode;
  title: ReactNode;
  body?: ReactNode;
  /** Texto da ação (renderiza um botão "{action} →"). */
  action?: ReactNode;
  onAction?: () => void;
  className?: string;
}

/** Card de toast (apresentacional). A fila/auto-dismiss fica a cargo do consumidor. */
export function Toast({ tone = "ok", icon, title, body, action, onAction, className }: ToastProps) {
  const { color, glow } = TONE[tone];
  return (
    <div
      role={tone === "err" ? "alert" : "status"}
      className={cn(
        "relative flex gap-3 overflow-hidden rounded border border-forge-line bg-forge-elev p-3.5",
        className
      )}
      style={{ boxShadow: `0 16px 36px -20px ${glow}, 0 1px 0 0 color-mix(in srgb, ${color} 14%, transparent)` }}
    >
      <span
        className="absolute inset-y-0 left-0 w-[3px]"
        style={{ background: color, boxShadow: `0 0 12px ${glow}` }}
      />
      {icon && (
        <span
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[8px]"
          style={{ background: `color-mix(in srgb, ${color} 14%, transparent)`, color }}
        >
          {icon}
        </span>
      )}
      <div className="min-w-0 flex-1">
        <div className="text-[13px] font-medium text-forge-text">{title}</div>
        {body && <div className="mt-0.5 text-xs leading-relaxed text-forge-muted">{body}</div>}
      </div>
      {action && (
        <button
          type="button"
          onClick={onAction}
          className="self-center whitespace-nowrap font-mono text-[11px] tracking-[0.04em]"
          style={{ color }}
        >
          {action} →
        </button>
      )}
    </div>
  );
}
