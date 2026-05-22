import { Menu, Wifi } from "lucide-react";

import type { DashboardView } from "../app/ui-state";
import { ChatModeling3DBadge } from "../features/modeling-3d/components";
import { Badge } from "./ui/Badge";
import { Button } from "./ui/Button";

export interface AppHeaderProps {
  activeView: DashboardView;
  isModeling3D: boolean;
  chatTitle: string;
  chatSubtitle: string;
  agentModelLabel: string;
  online: boolean;
  onOpenMobileMenu: () => void;
}

const VIEW_TITLES: Record<Exclude<DashboardView, "chat">, string> = {
  agents: "Dashboard de agentes",
  projects: "Projetos e contexto",
  knowledge: "Bases de conhecimento",
  files: "Arquivos da plataforma"
};

const VIEW_SUBTITLES: Record<Exclude<DashboardView, "chat">, string> = {
  agents: "JUDITE, especialistas e configuração de LLM por agente",
  projects: "Estruture projetos, pastas e escopo de recuperação",
  knowledge: "Coleções curadas para RAG e agentes",
  files: "Uploads, imports e arquivos gerados"
};

/**
 * Top app bar: mobile-menu toggle, the view title/subtitle and the model +
 * online badges. Extracted from App.tsx (architecture-map "monólitos de
 * borda"); presentational.
 */
export function AppHeader({
  activeView,
  isModeling3D,
  chatTitle,
  chatSubtitle,
  agentModelLabel,
  online,
  onOpenMobileMenu
}: AppHeaderProps) {
  const title = activeView === "chat" ? chatTitle : VIEW_TITLES[activeView];
  const subtitle = activeView === "chat" ? chatSubtitle : VIEW_SUBTITLES[activeView];
  return (
    <header className="flex h-16 items-center justify-between border-b border-forge-line bg-[#0c0d0f]/95 px-4">
      <div className="flex min-w-0 items-center gap-3">
        <Button
          className="h-9 w-9 px-0 md:hidden"
          onClick={onOpenMobileMenu}
          aria-label="Abrir menu"
          title="Abrir menu"
        >
          <Menu size={18} />
        </Button>
        <div className="min-w-0">
          <h2 className="flex min-w-0 items-center gap-2 truncate text-base font-semibold">
            {isModeling3D && <ChatModeling3DBadge />}
            <span className="truncate">{title}</span>
          </h2>
          <p className="truncate text-xs text-forge-muted">{subtitle}</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Badge className="hidden max-w-[260px] truncate md:inline-flex">{agentModelLabel}</Badge>
        <Badge className={online ? "border-forge-green text-forge-green" : "border-forge-red text-forge-red"}>
          <Wifi size={13} />
          {online ? "Online" : "Offline"}
        </Badge>
      </div>
    </header>
  );
}
