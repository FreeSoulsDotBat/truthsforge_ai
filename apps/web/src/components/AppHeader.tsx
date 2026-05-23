import { Menu, Wifi } from "lucide-react";

import type { DashboardView } from "../app/ui-state";
import { ChatModeling3DBadge } from "../features/modeling-3d/components";
import { Badge } from "./ui/Badge";
import { Button } from "./ui/Button";
import { Mono } from "./ui/Mono";

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

const VIEW_EYEBROW: Record<Exclude<DashboardView, "chat">, string> = {
  agents: "agentes · dashboard",
  projects: "projetos · contexto",
  knowledge: "bases · conhecimento",
  files: "arquivos · plataforma"
};

/**
 * Top app bar (re-skin v4 "Hearth"): mobile-menu toggle, um eyebrow mono + título
 * em display (uppercase) + subtítulo, e os selos de modelo + conexão. Extraído do
 * App.tsx; presentacional. É o cabeçalho de todas as views (chat + dashboards).
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
  const eyebrow = activeView === "chat" ? "conversa" : VIEW_EYEBROW[activeView];
  return (
    <header className="flex h-16 items-center justify-between border-b border-forge-line-soft bg-forge-ink/95 px-4 sm:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <Button
          variant="icon"
          className="h-9 w-9 md:hidden"
          onClick={onOpenMobileMenu}
          aria-label="Abrir menu"
          title="Abrir menu"
        >
          <Menu size={18} />
        </Button>
        <div className="min-w-0">
          <Mono size={9.5} className="block truncate uppercase tracking-[0.16em] text-forge-faint">
            {eyebrow}
          </Mono>
          <h2 className="flex min-w-0 items-center gap-2 truncate font-display text-[15px] uppercase leading-tight tracking-[0.01em] text-forge-text">
            {isModeling3D && <ChatModeling3DBadge />}
            <span className="truncate">{title}</span>
          </h2>
          <p className="truncate text-[11px] text-forge-muted">{subtitle}</p>
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
