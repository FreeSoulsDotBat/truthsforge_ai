import { Check, ChevronRight, EllipsisVertical } from "lucide-react";
import type { MutableRefObject } from "react";

import { useAppStore } from "../../../app/store";
import { Button } from "../../../components/ui/Button";
import { projectDisplayName } from "../../projects/project-domain";
import type { Agent, ProjectRecord } from "../../../types/api";

export interface ShortcutMenuProps {
  menuRef: MutableRefObject<HTMLDivElement | null>;
  agents: Agent[];
  activeAgent: Agent | null;
  availableContextProjects: ProjectRecord[];
  activeProjectId: string | undefined;
  onSelectAgent: (agentId: string) => void;
  onSelectProject: (project: ProjectRecord) => void;
  onEditKnowledgeBases: () => void;
}

/**
 * Quick-shortcut dropdown of the chat composer (switch agent / switch project
 * scope). Extracted from App.tsx (architecture-map "monólitos de borda");
 * presentational, with the multi-setter selections composed by App.
 */
export function ShortcutMenu({
  menuRef,
  agents,
  activeAgent,
  availableContextProjects,
  activeProjectId,
  onSelectAgent,
  onSelectProject,
  onEditKnowledgeBases
}: ShortcutMenuProps) {
  const open = useAppStore((state) => state.shortcutMenuOpen);
  const submenu = useAppStore((state) => state.shortcutSubmenu);
  const setShortcutMenuOpen = useAppStore((state) => state.setShortcutMenuOpen);
  const onSelectSubmenu = useAppStore((state) => state.setShortcutSubmenu);
  const onToggleOpen = () => {
    if (open) {
      setShortcutMenuOpen(false);
      onSelectSubmenu(null);
    } else {
      setShortcutMenuOpen(true);
      onSelectSubmenu("agent");
    }
  };
  return (
    <div className="relative" ref={menuRef}>
      <Button className="h-8 w-8 px-0" onClick={onToggleOpen} aria-label="Menu rápido" title="Menu rápido">
        <EllipsisVertical size={15} />
      </Button>
      {open && (
        <div
          className="absolute right-0 z-50 w-[460px] rounded-md border border-forge-line bg-forge-panel p-1 shadow-2xl"
          style={{ top: "auto", bottom: "calc(100% + 4px)" }}
        >
          <div className="grid grid-cols-[170px_minmax(0,1fr)]">
            <div className="space-y-1 pr-1">
              <button
                type="button"
                className={[
                  "flex h-8 w-full items-center justify-between rounded px-2 text-xs transition",
                  submenu === "agent"
                    ? "bg-forge-hover text-forge-text"
                    : "text-forge-muted hover:bg-forge-hover hover:text-forge-text"
                ].join(" ")}
                onClick={() => onSelectSubmenu("agent")}
              >
                <span>Agente</span>
                <ChevronRight size={13} />
              </button>
              <button
                type="button"
                className={[
                  "flex h-8 w-full items-center justify-between rounded px-2 text-xs transition",
                  submenu === "scope"
                    ? "bg-forge-hover text-forge-text"
                    : "text-forge-muted hover:bg-forge-hover hover:text-forge-text"
                ].join(" ")}
                onClick={() => onSelectSubmenu("scope")}
              >
                <span>Projeto</span>
                <ChevronRight size={13} />
              </button>
            </div>

            <div className="scrollbar-slim max-h-[55vh] overflow-y-auto border-l border-forge-line pl-2">
              {submenu === "agent" && (
                <div className="space-y-1">
                  {agents
                    .filter((agent) => agent.enabled)
                    .map((agent) => (
                      <button
                        key={agent.id}
                        type="button"
                        className="flex h-8 w-full items-center justify-between rounded px-2 text-xs text-forge-muted transition hover:bg-forge-hover hover:text-forge-text"
                        onClick={() => onSelectAgent(agent.id)}
                      >
                        <span className="truncate">{agent.name}</span>
                        {activeAgent?.id === agent.id && <Check size={13} className="text-forge-amber" />}
                      </button>
                    ))}
                </div>
              )}

              {submenu === "scope" && (
                <div className="space-y-1">
                  {availableContextProjects.map((project) => (
                    <button
                      key={project.id}
                      type="button"
                      className="flex h-8 w-full items-center justify-between rounded px-2 text-xs text-forge-muted transition hover:bg-forge-hover hover:text-forge-text"
                      onClick={() => onSelectProject(project)}
                    >
                      <span className="truncate">{projectDisplayName(project)}</span>
                      {activeProjectId === project.id && <Check size={13} className="text-forge-amber" />}
                    </button>
                  ))}
                  <div className="px-2 pt-1 text-[11px] text-forge-muted">
                    A conversa usa um projeto por vez. As pastas citadas com @ filtram a busca.
                  </div>
                  <button
                    type="button"
                    className="mt-1 flex h-8 w-full items-center justify-between rounded px-2 text-xs text-forge-muted transition hover:bg-forge-hover hover:text-forge-text"
                    onClick={onEditKnowledgeBases}
                  >
                    <span>Editar bases de conhecimento atreladas</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
