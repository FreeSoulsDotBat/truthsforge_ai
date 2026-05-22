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
import type { Dispatch, SetStateAction } from "react";

import { infraLinks } from "../../../app/constants";
import type { Panel } from "../../../app/ui-state";
import { EmptyPanel, InfoRow, PanelButton, PanelStack, PanelTitle } from "../../../components/app-panels";
import { Badge } from "../../../components/ui/Badge";
import { Button } from "../../../components/ui/Button";
import { api } from "../../../lib/api";
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

export interface ChatRightPanelProps {
  activePanel: Panel;
  onSelectPanel: (panel: Panel) => void;
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
 * Right context/settings panel (Contexto/Infra/Auditoria/Prompts/Config tabs).
 * Extracted from App.tsx (architecture-map finding "monólitos de borda").
 * Presentational: App owns the state and passes setters/handlers.
 */
export function ChatRightPanel({
  activePanel,
  onSelectPanel,
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
  return (
    <aside className="hidden w-[360px] shrink-0 border-l border-forge-line bg-[#101111] p-4 lg:block">
      <div className="mb-4 grid grid-cols-5 gap-1 rounded-md border border-forge-line bg-[#0e0f0e] p-1">
        <PanelButton
          label="Contexto"
          active={activePanel === "contexto"}
          icon={<Activity size={15} />}
          onClick={() => onSelectPanel("contexto")}
        />
        <PanelButton
          label="Infra"
          active={activePanel === "infra"}
          icon={<Server size={15} />}
          onClick={() => onSelectPanel("infra")}
        />
        <PanelButton
          label="Auditoria"
          active={activePanel === "auditoria"}
          icon={<ShieldCheck size={15} />}
          onClick={() => onSelectPanel("auditoria")}
        />
        <PanelButton
          label="Prompts"
          active={activePanel === "prompts"}
          icon={<Library size={15} />}
          onClick={() => onSelectPanel("prompts")}
        />
        <PanelButton
          label="Configurações"
          active={activePanel === "config"}
          icon={<Settings2 size={15} />}
          onClick={() => onSelectPanel("config")}
        />
      </div>

      {activePanel === "contexto" && (
        <PanelStack>
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
            className="h-9 rounded-md border border-forge-line bg-[#0e0f0e] px-3 text-sm text-forge-text"
          />
          <textarea
            value={documentContent}
            onChange={(event) => onSetDocumentContent(event.target.value)}
            placeholder="Texto ou Markdown"
            rows={5}
            className="min-h-28 resize-none rounded-md border border-forge-line bg-[#0e0f0e] px-3 py-2 text-sm text-forge-text"
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
              className="h-9 min-w-0 flex-1 rounded-md border border-forge-line bg-[#0e0f0e] px-3 text-sm text-forge-text"
            />
            <Button className="h-9" onClick={onSearchDocuments} disabled={!documentQuery.trim()}>
              Buscar
            </Button>
          </div>
          {documentResults.map((result) => (
            <button
              key={`${result.document_id}:${String(result.metadata.chunk_index ?? "0")}`}
              className="rounded-md border border-forge-line bg-[#171716] p-3 text-left text-sm transition hover:border-forge-amber/60"
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
        </PanelStack>
      )}

      {activePanel === "infra" && (
        <PanelStack>
          <PanelTitle icon={<Server size={18} />} title="Infra" />
          {infraLinks.map((link) => (
            <a
              key={link.href}
              href={link.href}
              target="_blank"
              rel="noreferrer"
              className="rounded-md border border-forge-line bg-[#171716] p-3 text-sm text-forge-text no-underline transition hover:border-forge-amber/60"
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
        </PanelStack>
      )}

      {activePanel === "auditoria" && (
        <PanelStack>
          <PanelTitle icon={<ShieldCheck size={18} />} title="Auditoria" />
          {auditEvents.slice(0, 8).map((event) => (
            <div key={event.id} className="rounded-md border border-forge-line bg-[#171716] p-3 text-sm">
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
        </PanelStack>
      )}

      {activePanel === "prompts" && (
        <PanelStack>
          <PanelTitle icon={<Library size={18} />} title="Prompts" />
          {prompts.map((prompt) => (
            <button
              key={prompt.id}
              className="rounded-md border border-forge-line bg-[#171716] p-3 text-left text-sm transition hover:border-forge-amber/60"
              onClick={() => setDraft(prompt.template)}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{prompt.title}</span>
                {prompt.favorite && <Badge>favorito</Badge>}
              </div>
              <p className="mt-2 line-clamp-3 text-xs text-forge-muted">{prompt.template}</p>
            </button>
          ))}
        </PanelStack>
      )}

      {activePanel === "config" && (
        <PanelStack>
          <Modeling3DSettingsSection software={modeling3dSoftware} onSoftwareChange={onModeling3dSoftwareChange} />
          <PanelTitle icon={<KeyRound size={18} />} title="Provedores" />
          {providerStatuses.map((provider) => (
            <div key={provider.provider} className="rounded-md border border-forge-line bg-[#171716] p-3">
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
                    className="min-w-0 flex-1 rounded-md border border-forge-line bg-[#0e0f0e] px-3 text-sm text-forge-text"
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
        </PanelStack>
      )}
    </aside>
  );
}
