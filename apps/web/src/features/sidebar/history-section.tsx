import { ChevronDown, ChevronRight, LoaderCircle, Trash2 } from "lucide-react";
import type { ReactNode } from "react";

import type { ChatSession } from "../../types/api";

type HistorySectionProps = {
  sessions: ChatSession[];
  activeSessionId: string | null;
  collapsed: boolean;
  deletingSessionId: string | null;
  disabled?: boolean;
  renderSessionBadge?: (session: ChatSession) => ReactNode;
  onToggleCollapsed: () => void;
  onSelectSession: (sessionId: string) => void;
  onDeleteSession: (session: ChatSession) => void;
};

export function HistorySection({
  sessions,
  activeSessionId,
  collapsed,
  deletingSessionId,
  disabled = false,
  renderSessionBadge,
  onToggleCollapsed,
  onSelectSession,
  onDeleteSession
}: HistorySectionProps) {
  return (
    <div className="space-y-2">
      <button
        type="button"
        className="flex w-full items-center justify-between text-xs uppercase text-forge-muted"
        onClick={onToggleCollapsed}
      >
        <span>Histórico (geral)</span>
        <span className="inline-flex items-center gap-1">
          {sessions.length}
          {collapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
        </span>
      </button>
      {!collapsed && (
        <div className="space-y-1 pr-1">
          {sessions.map((session) => (
            <div key={session.id} className="group flex items-center gap-1">
              <button
                className={[
                  "min-w-0 flex-1 rounded-md px-3 py-2 text-left text-sm transition",
                  session.id === activeSessionId
                    ? "bg-[#202722] text-forge-text"
                    : "text-forge-muted hover:bg-[#181b1e]"
                ].join(" ")}
                onClick={() => onSelectSession(session.id)}
              >
                <span className="flex min-w-0 items-center gap-2">
                  {renderSessionBadge?.(session)}
                  <span className="block truncate">{session.title}</span>
                </span>
              </button>
              <button
                type="button"
                className={[
                  "inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-forge-line text-forge-muted transition",
                  "hover:border-forge-red/60 hover:bg-[#261315] hover:text-forge-red",
                  "opacity-0 group-hover:opacity-100 focus:opacity-100",
                  deletingSessionId === session.id ? "cursor-wait opacity-100" : ""
                ].join(" ")}
                onClick={(event) => {
                  event.stopPropagation();
                  onDeleteSession(session);
                }}
                disabled={disabled || deletingSessionId === session.id}
                aria-label={`Excluir chat ${session.title}`}
                title={`Excluir chat ${session.title}`}
              >
                {deletingSessionId === session.id ? (
                  <LoaderCircle size={14} className="animate-spin" />
                ) : (
                  <Trash2 size={14} />
                )}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
