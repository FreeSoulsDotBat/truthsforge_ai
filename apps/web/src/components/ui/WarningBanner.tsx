import { Shield } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "../../lib/utils";

interface WarningBannerProps {
  tone?: "ember" | "err";
  title: ReactNode;
  body?: ReactNode;
  /** Override do ícone shield. */
  icon?: ReactNode;
  className?: string;
}

/** Faixa inline persistente pra avisos/erros. Sem botão fechar — some quando resolve. */
export function WarningBanner({ tone = "ember", title, body, icon, className }: WarningBannerProps) {
  const color = tone === "err" ? "var(--err)" : "var(--ember)";
  return (
    <div
      role={tone === "err" ? "alert" : "status"}
      className={cn("flex items-start gap-2.5 rounded-sm border p-3", className)}
      style={{
        background: `color-mix(in srgb, ${color} 10%, var(--bg-card))`,
        borderColor: `color-mix(in srgb, ${color} 45%, transparent)`
      }}
    >
      <span className="mt-0.5 shrink-0" style={{ color }} aria-hidden>
        {icon ?? <Shield size={14} strokeWidth={1.75} />}
      </span>
      <div className="min-w-0 flex-1">
        <div className="text-[12.5px] font-semibold" style={{ color }}>
          {title}
        </div>
        {body && <div className="mt-0.5 text-xs leading-relaxed text-forge-text-soft">{body}</div>}
      </div>
    </div>
  );
}
