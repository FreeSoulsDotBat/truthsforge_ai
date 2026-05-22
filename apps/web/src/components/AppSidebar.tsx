import { Database, FileText, FolderTree, LoaderCircle, MessageSquare, Sparkles, Users, X } from "lucide-react";

import type { DashboardView } from "../app/ui-state";
import { isModeling3DChat } from "../features/modeling-3d/chat-domain";
import { ChatModeling3DBadge } from "../features/modeling-3d/components";
import { HistorySection } from "../features/sidebar/history-section";
import { ProjectExplorerSection } from "../features/sidebar/project-explorer-section";
import type { ChatSession, ProjectFolder, ProjectRecord } from "../types/api";
import { DashboardNavButton, Metric } from "./app-panels";
import { Button } from "./ui/Button";

export interface AppSidebarProps {
  mobileMenuOpen: boolean;
  onCloseMobile: () => void;
  onNewChat: () => void;
  isCreatingNewChat: boolean;
  activeView: DashboardView;
  onSelectView: (view: DashboardView) => void;
  sessionsCount: number;
  promptsCount: number;
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
}

/**
 * Left navigation sidebar (header, new-chat, dashboard nav, metrics, project
 * explorer + history). Extracted from App.tsx (architecture-map finding
 * "monólitos de borda"). Presentational: App composes the callbacks.
 */
export function AppSidebar({
  mobileMenuOpen,
  onCloseMobile,
  onNewChat,
  isCreatingNewChat,
  activeView,
  onSelectView,
  sessionsCount,
  promptsCount,
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
  onDeleteSession
}: AppSidebarProps) {
  const sessionBadge = (session: ChatSession) => (isModeling3DChat(session) ? <ChatModeling3DBadge compact /> : null);

  return (
    <aside
      className={[
        "fixed inset-y-0 left-0 z-30 w-[286px] border-r border-forge-line bg-[#101111] transition-transform md:static md:translate-x-0",
        mobileMenuOpen ? "translate-x-0" : "-translate-x-full"
      ].join(" ")}
    >
      <div className="flex h-16 items-center justify-between border-b border-forge-line px-4">
        <div>
          <p className="text-sm text-forge-muted">Truth's Forge AI</p>
          <h1 className="flex items-center gap-2 text-lg font-semibold">
            <Sparkles size={18} className="text-forge-amber" />
            JUDITE
          </h1>
        </div>
        <Button className="h-9 w-9 px-0 md:hidden" onClick={onCloseMobile} aria-label="Fechar menu" title="Fechar menu">
          <X size={18} />
        </Button>
      </div>

      <div className="scrollbar-slim h-[calc(100vh-64px)] space-y-4 overflow-y-auto p-4 pb-8">
        <Button
          className="w-full justify-start border-forge-amber/50 bg-[#171717] text-forge-text hover:border-forge-amber hover:bg-[#211d16]"
          onClick={onNewChat}
          disabled={isCreatingNewChat}
          aria-label="Novo chat"
          title="Novo chat"
        >
          {isCreatingNewChat ? <LoaderCircle size={15} className="animate-spin" /> : <MessageSquare size={15} />}
          {isCreatingNewChat ? "Criando..." : "Novo chat"}
        </Button>

        <div className="flex flex-col gap-1 rounded-md border border-forge-line bg-[#0e0f0e] p-1">
          <DashboardNavButton
            active={activeView === "chat"}
            icon={<MessageSquare size={15} />}
            label="Chat"
            onClick={() => onSelectView("chat")}
          />
          <DashboardNavButton
            active={activeView === "agents"}
            icon={<Users size={15} />}
            label="Agentes"
            onClick={() => onSelectView("agents")}
          />
          <DashboardNavButton
            active={activeView === "projects"}
            icon={<FolderTree size={15} />}
            label="Projetos"
            onClick={() => onSelectView("projects")}
          />
          <DashboardNavButton
            active={activeView === "knowledge"}
            icon={<Database size={15} />}
            label="Bases"
            onClick={() => onSelectView("knowledge")}
          />
          <DashboardNavButton
            active={activeView === "files"}
            icon={<FileText size={15} />}
            label="Arquivos"
            onClick={() => onSelectView("files")}
          />
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs">
          <Metric label="Chats" value={sessionsCount} />
          <Metric label="Prompts" value={promptsCount} />
        </div>

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
    </aside>
  );
}
