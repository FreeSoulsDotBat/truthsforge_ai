import {
  Activity,
  Database,
  ExternalLink,
  FileText,
  Gauge,
  KeyRound,
  Library,
  Server,
  Settings2,
  ShieldCheck,
  Users,
  X
} from "lucide-react";
import { useState } from "react";
import type { Dispatch, ReactNode, SetStateAction } from "react";

import { infraLinks } from "../../../app/constants";
import type { Panel } from "../../../app/ui-state";
import { EmptyPanel, InfoRow, PanelTitle } from "../../../components/app-panels";
import { Badge } from "../../../components/ui/Badge";
import { Button } from "../../../components/ui/Button";
import { Mono } from "../../../components/ui/Mono";
import { api } from "../../../lib/api";
import { cn } from "../../../lib/utils";
import type {
  AuditEvent,
  CostPolicy,
  CostUsage,
  DocumentRecord,
  DocumentSearchResult,
  ModelingSoftware,
  Prompt,
  ProviderName,
  ProviderSecretStatus,
  ServerStatus
} from "../../../types/api";
import { Modeling3DSettingsSection } from "../../modeling-3d/settings";
import { ChatExecutionModes } from "./ChatExecutionModes";

export interface ChatRightPanelProps {
  activePanel: Panel;
  onSelectPanel: (panel: Panel) => void;
  reasoningSummaryUnavailable: boolean;
  status: ServerStatus | null;
  costUsage: CostUsage | null;
  costPolicy: CostPolicy | null;
  agentsCount: number;
  prompts: Prompt[];
  documents: DocumentRecord[];
  auditEvents: AuditEvent[];
  documentTitle: string;
  onSetDocumentTitle: (value: string) => void;
  documentContent: string;
  onSetDocumentContent: (value: string) => void;
  documentQuery: string;
  onSetDocumentQuery: (value: string) => void;
  documentResults: DocumentSearchResult[];
  isIndexingDocument: boolean;
  onIndexTextDocument: () => void;
  onSearchDocuments: () => void;
  setDraft: Dispatch<SetStateAction<string>>;
  providerStatuses: ProviderSecretStatus[];
  providerDrafts: Record<string, string>;
  onSetProviderDrafts: Dispatch<SetStateAction<Record<string, string>>>;
  providerEditMode: Record<string, boolean>;
  onSetProviderEditMode: Dispatch<SetStateAction<Record<string, boolean>>>;
  onSaveProviderKey: (provider: ProviderName) => void;
  onClearProviderKey: (provider: ProviderName) => void;
  modeling3dSoftware: ModelingSoftware;
  onModeling3dSoftwareChange: (software: ModelingSoftware) => void;
  onOpenAgentDashboard: () => void;
}

/**
 * Right context/settings aside (Contexto/Infra/Auditoria/Prompts/Config). Re-skin
 * v4 "Hearth": aside 360px com header (rótulo mono + título display) + um rail
 * `Dock` de 56px à direita com os seletores de painel (frames panel.jsx +
 * sidebar.jsx). Extraído do App.tsx; apresentacional (App é dono do estado).
 */
export function ChatRightPanel({
  activePanel,
  onSelectPanel,
  reasoningSummaryUnavailable,
  status,
  costUsage,
  costPolicy,
  agentsCount,
  prompts,
  documents,
  auditEvents,
  documentTitle,
  onSetDocumentTitle,
  documentContent,
  onSetDocumentContent,
  documentQuery,
  onSetDocumentQuery,
  documentResults,
  isIndexingDocument,
  onIndexTextDocument,
  onSearchDocuments,
  setDraft,
  providerStatuses,
  providerDrafts,
  onSetProviderDrafts,
  providerEditMode,
  onSetProviderEditMode,
  onSaveProviderKey,
  onClearProviderKey,
  modeling3dSoftware,
  onModeling3dSoftwareChange,
  onOpenAgentDashboard
}: ChatRightPanelProps) {
  const panels: { id: Panel; label: string; title: string; icon: ReactNode }[] = [
    { id: "contexto", label: "painel · contexto", title: "O que JUDITE está olhando", icon: <Activity size={16} /> },
    { id: "infra", label: "painel · infra", title: "Infraestrutura local", icon: <Server size={16} /> },
    { id: "auditoria", label: "painel · auditoria", title: "Auditoria de execução", icon: <ShieldCheck size={16} /> },
    { id: "prompts", label: "painel · prompts", title: "Biblioteca de prompts", icon: <Library size={16} /> },
    { id: "config", label: "painel · configurações", title: "Configurações", icon: <Settings2 size={16} /> }
  ];
  const activeMeta = panels.find((panel) => panel.id === activePanel) ?? panels[0];
  const [asideOpen, setAsideOpen] = useState(true);

  return (
    <>
      {asideOpen && (
        <aside className="hidden w-[360px] shrink-0 flex-col border-l border-forge-line-soft bg-forge-ink-deep lg:flex">
          <div className="border-b border-forge-line-soft px-4 py-4">
            <Mono size={10} className="uppercase tracking-[0.14em] text-forge-faint">
              {activeMeta.label}
            </Mono>
            <h2 className="mt-1.5 font-display text-[19px] uppercase leading-tight tracking-[0.015em] text-forge-text">
              {activeMeta.title}
            </h2>
          </div>
          <div className="scrollbar-slim flex-1 space-y-4 overflow-y-auto px-4 py-4">
            {activePanel === "contexto" && (
              <>
                <ChatExecutionModes reasoningSummaryUnavailable={reasoningSummaryUnavailable} />
                <PanelTitle icon={<Activity size={18} />} title="Contexto" />
                <InfoRow label="API" value={api.baseUrl} />
                <InfoRow label="Vetores" value={status?.vector_store ?? "qdrant"} />
                <InfoRow label="Mobile" value={status?.mobile_access ?? "Tailscale/WireGuard"} />
                <PanelTitle icon={<Gauge size={18} />} title="Custos" />
                <InfoRow label="Mês" value={costUsage?.month ?? "-"} />
                <InfoRow label="Gasto" value={`R$ ${(costUsage?.estimated_spend_brl ?? 0).toFixed(4)}`} />
                <InfoRow
                  label="Livre"
                  value={`R$ ${(costUsage?.remaining_budget_brl ?? costPolicy?.monthly_budget_brl ?? 200).toFixed(2)}`}
                />
                <PanelTitle icon={<Database size={18} />} title="Base" />
                <InfoRow label="Agentes" value={String(agentsCount)} />
                <InfoRow label="Prompts" value={String(prompts.length)} />
                <InfoRow label="Documentos" value={String(documents.length)} />
                <PanelTitle icon={<FileText size={18} />} title="RAG" />
                <input
                  value={documentTitle}
                  onChange={(event) => onSetDocumentTitle(event.target.value)}
                  placeholder="Título"
                  className="h-9 rounded-md border border-forge-line-soft bg-forge-panel px-3 text-sm text-forge-text"
                />
                <textarea
                  value={documentContent}
                  onChange={(event) => onSetDocumentContent(event.target.value)}
                  placeholder="Texto ou Markdown"
                  rows={5}
                  className="min-h-28 resize-none rounded-md border border-forge-line-soft bg-forge-panel px-3 py-2 text-sm text-forge-text"
                />
                <Button
                  className="h-9 w-full"
                  onClick={onIndexTextDocument}
                  disabled={!documentContent.trim() || isIndexingDocument}
                >
                  Indexar texto
                </Button>
                <div className="flex gap-2">
                  <input
                    value={documentQuery}
                    onChange={(event) => onSetDocumentQuery(event.target.value)}
                    placeholder="Buscar contexto"
                    className="h-9 min-w-0 flex-1 rounded-md border border-forge-line-soft bg-forge-panel px-3 text-sm text-forge-text"
                  />
                  <Button className="h-9" onClick={onSearchDocuments} disabled={!documentQuery.trim()}>
                    Buscar
                  </Button>
                </div>
                {documentResults.map((result) => (
                  <button
                    key={`${result.document_id}:${String(result.metadata.chunk_index ?? "0")}`}
                    className="rounded-md border border-forge-line-soft bg-forge-panel p-3 text-left text-sm transition hover:border-forge-amber/60"
                    onClick={() => setDraft((current) => `${current}${current ? "\n\n" : ""}${result.content}`)}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{result.title}</span>
                      <Badge>{result.score.toFixed(2)}</Badge>
                    </div>
                    <p className="mt-2 line-clamp-3 text-xs text-forge-muted">{result.content}</p>
                  </button>
                ))}
                {documents.slice(0, 4).map((document) => (
                  <InfoRow key={document.id} label={document.title} value={document.index_status} />
                ))}
              </>
            )}

            {activePanel === "infra" && (
              <>
                <PanelTitle icon={<Server size={18} />} title="Infra" />
                {infraLinks.map((link) => (
                  <a
                    key={link.href}
                    href={link.href}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-md border border-forge-line-soft bg-forge-panel p-3 text-sm text-forge-text no-underline transition hover:border-forge-amber/60"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium">{link.title}</span>
                      <ExternalLink size={15} className="shrink-0 text-forge-amber" />
                    </div>
                    <p className="mt-2 break-words text-xs text-forge-muted">{link.href}</p>
                    <Badge className="mt-3">{link.detail}</Badge>
                  </a>
                ))}
                <PanelTitle icon={<Database size={18} />} title="Postgres" />
                <InfoRow label="Host Docker" value="postgres" />
                <InfoRow label="Porta Docker" value="5432" />
                <InfoRow label="Database" value="POSTGRES_DB" />
                <InfoRow label="Usuário" value="POSTGRES_USER" />
                <InfoRow label="Senha" value="POSTGRES_PASSWORD" />
              </>
            )}

            {activePanel === "auditoria" && (
              <>
                <PanelTitle icon={<ShieldCheck size={18} />} title="Auditoria" />
                {auditEvents.slice(0, 8).map((event) => (
                  <div key={event.id} className="rounded-md border border-forge-line-soft bg-forge-panel p-3 text-sm">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{event.event_type}</span>
                      <Badge>{event.model_id ?? "modelo"}</Badge>
                    </div>
                    <p className="mt-2 text-xs text-forge-muted">
                      {event.tokens_in} in / {event.tokens_out} out / R$ {event.estimated_cost_brl.toFixed(6)}
                    </p>
                  </div>
                ))}
                {!auditEvents.length && <EmptyPanel text="Nenhum evento registrado ainda." />}
              </>
            )}

            {activePanel === "prompts" && (
              <>
                <PanelTitle icon={<Library size={18} />} title="Prompts" />
                {prompts.map((prompt) => (
                  <button
                    key={prompt.id}
                    className="rounded-md border border-forge-line-soft bg-forge-panel p-3 text-left text-sm transition hover:border-forge-amber/60"
                    onClick={() => setDraft(prompt.template)}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{prompt.title}</span>
                      {prompt.favorite && <Badge>favorito</Badge>}
                    </div>
                    <p className="mt-2 line-clamp-3 text-xs text-forge-muted">{prompt.template}</p>
                  </button>
                ))}
              </>
            )}

            {activePanel === "config" && (
              <>
                <Modeling3DSettingsSection
                  software={modeling3dSoftware}
                  onSoftwareChange={onModeling3dSoftwareChange}
                />
                <PanelTitle icon={<KeyRound size={18} />} title="Provedores" />
                {providerStatuses.map((provider) => (
                  <div key={provider.provider} className="rounded-md border border-forge-line-soft bg-forge-panel p-3">
                    <div className="mb-3 flex items-center justify-between gap-2">
                      <span className="text-sm font-medium">{provider.provider}</span>
                      <Badge className={provider.configured ? "border-forge-green text-forge-green" : ""}>
                        {provider.configured ? provider.source : "pendente"}
                      </Badge>
                    </div>
                    {provider.configured && !providerEditMode[provider.provider] ? (
                      <Button
                        className="h-9 w-full"
                        onClick={() => onSetProviderEditMode((current) => ({ ...current, [provider.provider]: true }))}
                      >
                        Remover chave configurada?
                      </Button>
                    ) : (
                      <div className="flex gap-2">
                        <input
                          type="password"
                          value={providerDrafts[provider.provider] ?? ""}
                          onChange={(event) =>
                            onSetProviderDrafts((current) => ({
                              ...current,
                              [provider.provider]: event.target.value
                            }))
                          }
                          placeholder="Nova API key"
                          className="min-w-0 flex-1 rounded-md border border-forge-line-soft bg-forge-panel px-3 text-sm text-forge-text"
                        />
                        <Button className="h-9" onClick={() => onSaveProviderKey(provider.provider)}>
                          Salvar
                        </Button>
                        <Button
                          className="h-9 px-2"
                          onClick={() => onClearProviderKey(provider.provider)}
                          aria-label={`Remover chave ${provider.provider}`}
                          title={`Remover chave ${provider.provider}`}
                        >
                          <X size={16} />
                        </Button>
                      </div>
                    )}
                  </div>
                ))}
                <PanelTitle icon={<Users size={18} />} title="Modelos por agente" />
                <Button className="h-9 w-full justify-start" onClick={onOpenAgentDashboard}>
                  <Users size={16} />
                  Abrir dashboard de agentes
                </Button>
              </>
            )}
          </div>
        </aside>
      )}
      <nav
        aria-label="Painéis de contexto"
        className="hidden w-14 shrink-0 flex-col items-center gap-1.5 border-l border-forge-line-soft bg-forge-ink-deep py-4 lg:flex"
      >
        {panels.map((panel) => {
          const open = panel.id === activePanel && asideOpen;
          return (
            <button
              key={panel.id}
              type="button"
              aria-label={open ? `Fechar ${panel.title}` : panel.title}
              aria-pressed={open}
              title={open ? "Fechar painel" : panel.label.replace("painel · ", "")}
              onClick={() => {
                if (panel.id === activePanel) {
                  setAsideOpen((current) => !current);
                } else {
                  onSelectPanel(panel.id);
                  setAsideOpen(true);
                }
              }}
              className={cn(
                "flex h-9 w-9 items-center justify-center rounded-[10px] border transition-colors",
                open
                  ? "border-[color-mix(in_srgb,var(--ember)_25%,transparent)] bg-[color-mix(in_srgb,var(--ember)_12%,transparent)] text-forge-amber"
                  : "border-transparent text-forge-muted hover:bg-forge-hover hover:text-forge-text"
              )}
            >
              {panel.icon}
            </button>
          );
        })}
      </nav>
    </>
  );
}
