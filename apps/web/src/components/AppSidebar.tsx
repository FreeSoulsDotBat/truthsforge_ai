import { Database, FileText, FolderTree, LoaderCircle, MessageSquare, Plus, Users, X } from "lucide-react";
import type { ReactNode } from "react";

import type { DashboardView } from "../app/ui-state";
import { isModeling3DChat } from "../features/modeling-3d/chat-domain";
import { ChatModeling3DBadge } from "../features/modeling-3d/components";
import { HistorySection } from "../features/sidebar/history-section";
import { ProjectExplorerSection } from "../features/sidebar/project-explorer-section";
import { cn } from "../lib/utils";
import type { ChatSession, ProjectFolder, ProjectRecord } from "../types/api";
import { Avatar } from "./ui/Avatar";
import { BrandSymbol } from "./ui/BrandSymbol";
import { Button } from "./ui/Button";
import { Mono } from "./ui/Mono";
import { Pulse, StatusDot } from "./ui/StatusDot";

export interface AppSidebarProps {
  mobileMenuOpen: boolean;
  onCloseMobile: () => void;
  onNewChat: () => void;
  isCreatingNewChat: boolean;
  activeView: DashboardView;
  onSelectView: (view: DashboardView) => void;
  projects: ProjectRecord[];
  folders: ProjectFolder[];
  explorerSessions: ChatSession[];
  historySessions: ChatSession[];
  activeSessionId: string | null;
  projectExplorerCollapsed: boolean;
  projectExplorerExpanded: Record<string, boolean>;
  onToggleProjectExplorerCollapsed: () => void;
  onToggleProjectExplorerExpanded: (key: string) => void;
  historyCollapsed: boolean;
  deletingSessionId: string | null;
  historyDisabled: boolean;
  onToggleHistoryCollapsed: () => void;
  onSelectSession: (sessionId: string) => void;
  onCreateChat: (projectId: string, folderId: string | null) => void;
  onCreateFolder: (projectId: string, parentId: string | null) => void;
  onDeleteFolder: (folderId: string) => void;
  onMoveSession: (sessionId: string, projectId: string, folderId: string | null) => void;
  onDeleteSession: (session: ChatSession) => void;
  /** Estado de conexão da plataforma (rodapé JUDITE). */
  online: boolean;
  /** Modelo ativo do agente (rodapé JUDITE). */
  agentModelLabel: string;
}

/** Item de navegação principal: botão acessível com o visual do NavItem v4. */
function NavButton({
  active,
  icon,
  label,
  onClick
}: {
  active: boolean;
  icon: ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={cn(
        "relative flex h-[34px] w-full items-center gap-2.5 rounded-sm px-2.5 text-left text-[13px] transition-colors",
        active
          ? "bg-forge-panel font-medium text-forge-text"
          : "text-forge-muted hover:bg-forge-hover hover:text-forge-text"
      )}
    >
      {active && <span className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-forge-amber" />}
      <span className={active ? "text-forge-amber" : "text-forge-muted"}>{icon}</span>
      <span className="flex-1">{label}</span>
    </button>
  );
}

/**
 * Left navigation sidebar (brandmark, new-chat, primary nav, project explorer +
 * history, JUDITE footer). Re-skin da identidade visual v4 "Hearth": 248px,
 * fundo `--bg-ink`, marca da forja no topo e status real da JUDITE no rodapé.
 * Apresentacional: App compõe os callbacks.
 */
export function AppSidebar({
  mobileMenuOpen,
  onCloseMobile,
  onNewChat,
  isCreatingNewChat,
  activeView,
  onSelectView,
  projects,
  folders,
  explorerSessions,
  historySessions,
  activeSessionId,
  projectExplorerCollapsed,
  projectExplorerExpanded,
  onToggleProjectExplorerCollapsed,
  onToggleProjectExplorerExpanded,
  historyCollapsed,
  deletingSessionId,
  historyDisabled,
  onToggleHistoryCollapsed,
  onSelectSession,
  onCreateChat,
  onCreateFolder,
  onDeleteFolder,
  onMoveSession,
  onDeleteSession,
  online,
  agentModelLabel
}: AppSidebarProps) {
  const sessionBadge = (session: ChatSession) => (isModeling3DChat(session) ? <ChatModeling3DBadge compact /> : null);

  return (
    <aside
      className={cn(
        "fixed inset-y-0 left-0 z-30 flex w-[248px] flex-col border-r border-forge-line-soft bg-forge-ink-deep transition-transform md:static md:translate-x-0",
        mobileMenuOpen ? "translate-x-0" : "-translate-x-full"
      )}
    >
      <div className="flex items-center gap-3 px-4 pb-4 pt-5">
        <BrandSymbol size={32} />
        <div className="leading-[0.9]">
          <div className="font-display text-[15px] font-normal uppercase tracking-[0.04em] text-forge-text">
            Truth’s
          </div>
          <div className="mt-0.5 font-display text-[15px] font-normal uppercase tracking-[0.04em] text-forge-amber">
            Forge
          </div>
        </div>
        <Button
          variant="icon"
          className="ml-auto h-8 w-8 md:hidden"
          onClick={onCloseMobile}
          aria-label="Fechar menu"
          title="Fechar menu"
        >
          <X size={16} />
        </Button>
      </div>

      <div className="space-y-1 px-3">
        <button
          type="button"
          onClick={onNewChat}
          disabled={isCreatingNewChat}
          aria-label="Novo chat"
          title="Novo chat"
          className="flex h-[38px] w-full items-center gap-2.5 rounded-[10px] px-3 text-left text-[13px] font-medium text-forge-text transition disabled:opacity-60"
          style={{
            background: "color-mix(in srgb, var(--ember) 14%, var(--bg-card))",
            border: "1px solid color-mix(in srgb, var(--ember) 25%, transparent)",
            boxShadow:
              "inset 0 1px 0 color-mix(in srgb, var(--ember) 10%, transparent), 0 8px 24px -16px var(--ember-glow)"
          }}
        >
          {isCreatingNewChat ? (
            <LoaderCircle size={14} className="animate-spin text-forge-amber" />
          ) : (
            <Plus size={14} className="text-forge-amber" />
          )}
          <span className="flex-1">{isCreatingNewChat ? "Criando..." : "Novo chat"}</span>
        </button>

        <nav className="flex flex-col gap-0.5 pt-1">
          <NavButton
            active={activeView === "chat"}
            icon={<MessageSquare size={15} />}
            label="Chat"
            onClick={() => onSelectView("chat")}
          />
          <NavButton
            active={activeView === "agents"}
            icon={<Users size={15} />}
            label="Agentes"
            onClick={() => onSelectView("agents")}
          />
          <NavButton
            active={activeView === "projects"}
            icon={<FolderTree size={15} />}
            label="Projetos"
            onClick={() => onSelectView("projects")}
          />
          <NavButton
            active={activeView === "knowledge"}
            icon={<Database size={15} />}
            label="Bases"
            onClick={() => onSelectView("knowledge")}
          />
          <NavButton
            active={activeView === "files"}
            icon={<FileText size={15} />}
            label="Arquivos"
            onClick={() => onSelectView("files")}
          />
        </nav>
      </div>

      <div className="scrollbar-slim mt-3 flex-1 space-y-4 overflow-y-auto px-3 pb-6">
        <ProjectExplorerSection
          projects={projects}
          folders={folders}
          sessions={explorerSessions}
          activeSessionId={activeSessionId}
          collapsed={projectExplorerCollapsed}
          expandedKeys={projectExplorerExpanded}
          onToggleCollapsed={onToggleProjectExplorerCollapsed}
          onToggleExpanded={onToggleProjectExplorerExpanded}
          onSelectSession={onSelectSession}
          onCreateChat={onCreateChat}
          onCreateFolder={onCreateFolder}
          onDeleteFolder={onDeleteFolder}
          onMoveSession={onMoveSession}
          renderSessionBadge={sessionBadge}
        />

        <HistorySection
          sessions={historySessions}
          activeSessionId={activeSessionId}
          collapsed={historyCollapsed}
          deletingSessionId={deletingSessionId}
          disabled={historyDisabled}
          onToggleCollapsed={onToggleHistoryCollapsed}
          onSelectSession={onSelectSession}
          onDeleteSession={onDeleteSession}
          renderSessionBadge={sessionBadge}
        />
      </div>

      <div className="border-t border-forge-line-soft px-3.5 py-3">
        <div className="flex items-center gap-2.5">
          <Avatar kind="judite" size={24} />
          <div className="min-w-0 flex-1 leading-tight">
            <div className="text-[12px] text-forge-text">JUDITE</div>
            <div className="flex items-center gap-1.5">
              {online ? <Pulse color="var(--ok)" size={5} /> : <StatusDot color="var(--faint)" size={5} />}
              <Mono size={9.5} className="min-w-0 truncate">
                {online ? `online · ${agentModelLabel}` : "offline"}
              </Mono>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
