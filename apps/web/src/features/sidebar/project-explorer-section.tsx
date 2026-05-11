import { ChevronDown, ChevronRight, FolderOpen, Plus, Trash2 } from "lucide-react";
import { useMemo } from "react";

import { buildProjectChatTree, type ProjectChatTreeNode } from "./project-chat-tree";
import type { ChatSession, ProjectFolder, ProjectRecord } from "../../types/api";

type ProjectExplorerSectionProps = {
  projects: ProjectRecord[];
  folders: ProjectFolder[];
  sessions: ChatSession[];
  activeSessionId: string | null;
  collapsed: boolean;
  expandedKeys: Record<string, boolean>;
  onToggleCollapsed: () => void;
  onToggleExpanded: (key: string) => void;
  onSelectSession: (sessionId: string) => void;
  onCreateChat: (projectId: string, folderId: string | null) => void;
  onCreateFolder: (projectId: string, parentId: string | null) => void;
  onDeleteFolder: (folderId: string) => void;
  onMoveSession: (sessionId: string, projectId: string, folderId: string | null) => void;
};

type FolderNodeProps = {
  node: ProjectChatTreeNode;
  projectId: string;
  activeSessionId: string | null;
  expandedKeys: Record<string, boolean>;
  folderOptions: Array<{ id: string | null; label: string }>;
  onToggleExpanded: (key: string) => void;
  onSelectSession: (sessionId: string) => void;
  onCreateChat: (projectId: string, folderId: string | null) => void;
  onCreateFolder: (projectId: string, parentId: string | null) => void;
  onDeleteFolder: (folderId: string) => void;
  onMoveSession: (sessionId: string, projectId: string, folderId: string | null) => void;
};

function ChatRow({
  session,
  projectId,
  activeSessionId,
  folderOptions,
  onSelectSession,
  onMoveSession
}: {
  session: ChatSession;
  projectId: string;
  activeSessionId: string | null;
  folderOptions: Array<{ id: string | null; label: string }>;
  onSelectSession: (sessionId: string) => void;
  onMoveSession: (sessionId: string, projectId: string, folderId: string | null) => void;
}) {
  return (
    <div className="space-y-1 rounded-md border border-forge-line/60 bg-[#0c0d0f] p-2">
      <button
        type="button"
        className={[
          "w-full truncate rounded px-2 py-1 text-left text-xs transition",
          session.id === activeSessionId ? "bg-[#202722] text-forge-text" : "text-forge-muted hover:bg-[#181b1e]"
        ].join(" ")}
        onClick={() => onSelectSession(session.id)}
      >
        {session.title}
      </button>
      <select
        className="h-7 w-full rounded border border-forge-line bg-[#0e0f0e] px-2 text-[11px] text-forge-muted"
        value={session.folder_id ?? ""}
        onChange={(event) => onMoveSession(session.id, projectId, event.target.value || null)}
      >
        {folderOptions.map((option) => (
          <option key={option.id ?? "root"} value={option.id ?? ""}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function FolderNode({
  node,
  projectId,
  activeSessionId,
  expandedKeys,
  folderOptions,
  onToggleExpanded,
  onSelectSession,
  onCreateChat,
  onCreateFolder,
  onDeleteFolder,
  onMoveSession
}: FolderNodeProps) {
  const key = `folder:${node.folder.id}`;
  const isExpanded = expandedKeys[key] ?? true;
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2 rounded-md border border-forge-line bg-[#0e0f0e] px-2 py-1.5">
        <button type="button" className="flex min-w-0 items-center gap-1 text-sm" onClick={() => onToggleExpanded(key)}>
          {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          <FolderOpen size={14} className="text-forge-amber" />
          <span className="truncate">{node.folder.name}</span>
        </button>
        <div className="flex items-center gap-1">
          <button
            type="button"
            className="inline-flex h-7 w-7 items-center justify-center rounded border border-forge-line text-forge-muted hover:text-forge-text"
            onClick={() => onCreateChat(projectId, node.folder.id)}
            title="Novo chat nesta pasta"
            aria-label="Novo chat nesta pasta"
          >
            <Plus size={13} />
          </button>
          <button
            type="button"
            className="inline-flex h-7 w-7 items-center justify-center rounded border border-forge-line text-forge-muted hover:text-forge-text"
            onClick={() => onCreateFolder(projectId, node.folder.id)}
            title="Nova subpasta"
            aria-label="Nova subpasta"
          >
            <FolderOpen size={13} />
          </button>
          <button
            type="button"
            className="inline-flex h-7 w-7 items-center justify-center rounded border border-forge-line text-forge-muted hover:border-forge-red/60 hover:text-forge-red"
            onClick={() => onDeleteFolder(node.folder.id)}
            title="Excluir pasta"
            aria-label="Excluir pasta"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>
      {isExpanded && (
        <div className="ml-3 space-y-2 border-l border-forge-line/60 pl-3">
          {node.chats.map((session) => (
            <ChatRow
              key={session.id}
              session={session}
              projectId={projectId}
              activeSessionId={activeSessionId}
              folderOptions={folderOptions}
              onSelectSession={onSelectSession}
              onMoveSession={onMoveSession}
            />
          ))}
          {node.children.map((child) => (
            <FolderNode
              key={child.folder.id}
              node={child}
              projectId={projectId}
              activeSessionId={activeSessionId}
              expandedKeys={expandedKeys}
              folderOptions={folderOptions}
              onToggleExpanded={onToggleExpanded}
              onSelectSession={onSelectSession}
              onCreateChat={onCreateChat}
              onCreateFolder={onCreateFolder}
              onDeleteFolder={onDeleteFolder}
              onMoveSession={onMoveSession}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function ProjectExplorerSection({
  projects,
  folders,
  sessions,
  activeSessionId,
  collapsed,
  expandedKeys,
  onToggleCollapsed,
  onToggleExpanded,
  onSelectSession,
  onCreateChat,
  onCreateFolder,
  onDeleteFolder,
  onMoveSession
}: ProjectExplorerSectionProps) {
  const projectTrees = useMemo(
    () =>
      projects.map((project) => ({
        project,
        tree: buildProjectChatTree(project.id, folders, sessions)
      })),
    [folders, projects, sessions]
  );

  return (
    <div className="space-y-2">
      <button
        type="button"
        className="flex w-full items-center justify-between text-xs uppercase text-forge-muted"
        onClick={onToggleCollapsed}
      >
        <span>Projetos</span>
        <span className="inline-flex items-center gap-1">
          {projects.length}
          {collapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
        </span>
      </button>
      {!collapsed && (
        <div className="space-y-3">
          {projectTrees.map(({ project, tree }) => {
            const projectKey = `project:${project.id}`;
            const projectExpanded = expandedKeys[projectKey] ?? true;
            const folderOptions = [
              { id: null, label: "Raiz" },
              ...folders
                .filter((folder) => folder.project_id === project.id)
                .map((folder) => ({ id: folder.id, label: folder.path }))
            ];
            return (
              <section key={project.id} className="rounded-md border border-forge-line bg-[#0f1011] p-2">
                <div className="flex items-center justify-between gap-2">
                  <button
                    type="button"
                    className="flex min-w-0 items-center gap-1 text-sm font-medium"
                    onClick={() => onToggleExpanded(projectKey)}
                  >
                    {projectExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    <span className="truncate">{project.name}</span>
                  </button>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      className="inline-flex h-7 w-7 items-center justify-center rounded border border-forge-line text-forge-muted hover:text-forge-text"
                      onClick={() => onCreateChat(project.id, null)}
                      title="Novo chat no projeto"
                      aria-label="Novo chat no projeto"
                    >
                      <Plus size={13} />
                    </button>
                    <button
                      type="button"
                      className="inline-flex h-7 w-7 items-center justify-center rounded border border-forge-line text-forge-muted hover:text-forge-text"
                      onClick={() => onCreateFolder(project.id, null)}
                      title="Nova pasta raiz"
                      aria-label="Nova pasta raiz"
                    >
                      <FolderOpen size={13} />
                    </button>
                  </div>
                </div>
                {projectExpanded && (
                  <div className="mt-2 space-y-2">
                    {tree.rootChats.map((session) => (
                      <ChatRow
                        key={session.id}
                        session={session}
                        projectId={project.id}
                        activeSessionId={activeSessionId}
                        folderOptions={folderOptions}
                        onSelectSession={onSelectSession}
                        onMoveSession={onMoveSession}
                      />
                    ))}
                    {tree.roots.map((node) => (
                      <FolderNode
                        key={node.folder.id}
                        node={node}
                        projectId={project.id}
                        activeSessionId={activeSessionId}
                        expandedKeys={expandedKeys}
                        folderOptions={folderOptions}
                        onToggleExpanded={onToggleExpanded}
                        onSelectSession={onSelectSession}
                        onCreateChat={onCreateChat}
                        onCreateFolder={onCreateFolder}
                        onDeleteFolder={onDeleteFolder}
                        onMoveSession={onMoveSession}
                      />
                    ))}
                  </div>
                )}
              </section>
            );
          })}
          {!projectTrees.length && (
            <p className="text-xs text-forge-muted">Crie um projeto para organizar chats por pasta.</p>
          )}
        </div>
      )}
    </div>
  );
}
