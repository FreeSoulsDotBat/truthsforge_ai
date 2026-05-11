import {
  Bot,
  ExternalLink,
  FileText,
  FolderTree,
  Image as ImageIcon,
  LayoutGrid,
  Library,
  List,
  LoaderCircle,
  Plus,
  RefreshCw,
  Save,
  Settings2,
  Trash2,
  Users
} from "lucide-react";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import type { Dispatch, SetStateAction } from "react";
import { useEffect, useMemo, useRef, useState } from "react";

import type { ProviderCatalogState } from "../../app/ui-state";
import { AgentLLMNumberInput, AgentLLMSelect, Field, InfoTip, SubFieldLabel } from "../../components/app-form";
import { EmptyPanel, InfoRow, PanelTitle, SearchIcon } from "../../components/app-panels";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { defaultLLMConfig, agentRequiredFieldsComplete } from "../agents/agent-domain";
import {
  fileContentUrl,
  isChatGPTInformationalFileName,
  isImagePlatformFile,
  metadataValue,
  platformFileLabel
} from "../files/file-domain";
import { projectDisplayName } from "../projects/project-domain";
import { api } from "../../lib/api";
import { csvToList, formatBytes } from "../../shared/utils/common";
import type {
  Agent,
  AgentLLMConfig,
  AgentUpsert,
  ChatGPTImportJob,
  ChatGPTImportSummary,
  DocumentRecord,
  DocumentSearchResult,
  KnowledgeBase,
  KnowledgeBaseDocument,
  KnowledgeBaseUpsert,
  ModelingCapabilities,
  ModelingExecutionMode,
  ModelingPlan,
  ModelingSoftware,
  PlatformFile,
  PlatformFileUpdate,
  ProjectFolder,
  ProjectRecord,
  ProjectUpsert,
  ProviderModel,
  ProviderName
} from "../../types/api";

export function AgentDashboard({
  agents,
  projects,
  knowledgeBases,
  generalProjectId,
  activeAgent,
  supportAgentIds,
  agentDraft,
  editingAgentId,
  providerCatalogs,
  providerCatalogState,
  providerCatalogErrors,
  onSelectAgent,
  onCreateAgent,
  onSetAgentDraft,
  onSaveAgent,
  onSetActiveAgentId,
  onToggleSupportAgent,
  onLoadProviderModels
}: {
  agents: Agent[];
  projects: ProjectRecord[];
  knowledgeBases: KnowledgeBase[];
  generalProjectId: string;
  activeAgent?: Agent;
  supportAgentIds: string[];
  agentDraft: AgentUpsert;
  editingAgentId: string | null;
  providerCatalogs: Partial<Record<ProviderName, ProviderModel[]>>;
  providerCatalogState: Partial<Record<ProviderName, ProviderCatalogState>>;
  providerCatalogErrors: Partial<Record<ProviderName, string>>;
  onSelectAgent: (agent: Agent) => void;
  onCreateAgent: () => void;
  onSetAgentDraft: Dispatch<SetStateAction<AgentUpsert>>;
  onSaveAgent: () => void;
  onSetActiveAgentId: (agentId: string) => void;
  onToggleSupportAgent: (agentId: string, enabled: boolean) => void;
  onLoadProviderModels: (provider: ProviderName) => void;
}) {
  const provider = agentDraft.llm_config.provider;
  const providerModels = providerCatalogs[provider] ?? [];
  const catalogState = providerCatalogState[provider] ?? "idle";
  const catalogError = providerCatalogErrors[provider];
  const selectedProviderModel = providerModels.find((item) => item.id === agentDraft.llm_config.provider_model_id);
  const selectedPricingKey =
    selectedProviderModel?.input_token_cost_per_million !== undefined &&
    selectedProviderModel.input_token_cost_per_million !== null &&
    selectedProviderModel.output_token_cost_per_million !== undefined &&
    selectedProviderModel.output_token_cost_per_million !== null
      ? [
          selectedProviderModel.provider,
          selectedProviderModel.id,
          selectedProviderModel.input_token_cost_per_million,
          selectedProviderModel.output_token_cost_per_million
        ].join(":")
      : null;
  const lastAutoPricingKeyRef = useRef<string | null>(null);
  const [handoffTriggersDraft, setHandoffTriggersDraft] = useState(agentDraft.handoff_triggers.join(", "));
  const formIsValid = agentRequiredFieldsComplete(agentDraft);
  const selectableAgentProjects = useMemo(
    () =>
      projects.map((project) => ({
        id: project.id,
        label: projectDisplayName(project),
        isGeneral: project.is_general
      })),
    [projects]
  );
  const normalizedAllowedProjectIds = useMemo(() => {
    const knownProjectIds = new Set(selectableAgentProjects.map((project) => project.id));
    const normalized = (agentDraft.allowed_project_ids.length ? agentDraft.allowed_project_ids : [generalProjectId])
      .filter((projectId, index, list) => list.indexOf(projectId) === index)
      .filter((projectId) => knownProjectIds.has(projectId))
      .slice(0, 3);
    return normalized.length ? normalized : [generalProjectId];
  }, [agentDraft.allowed_project_ids, generalProjectId, selectableAgentProjects]);

  useEffect(() => {
    if (normalizedAllowedProjectIds.join("|") === agentDraft.allowed_project_ids.join("|")) return;
    onSetAgentDraft((current) => ({ ...current, allowed_project_ids: normalizedAllowedProjectIds }));
  }, [agentDraft.allowed_project_ids, normalizedAllowedProjectIds, onSetAgentDraft]);

  useEffect(() => {
    if (!selectedProviderModel || !selectedPricingKey) return;
    const inputCost = selectedProviderModel.input_token_cost_per_million;
    const outputCost = selectedProviderModel.output_token_cost_per_million;
    if (inputCost === undefined || inputCost === null || outputCost === undefined || outputCost === null) return;

    const shouldApply =
      lastAutoPricingKeyRef.current !== selectedPricingKey ||
      agentDraft.llm_config.input_token_cost_per_million === null ||
      agentDraft.llm_config.input_token_cost_per_million === undefined ||
      agentDraft.llm_config.output_token_cost_per_million === null ||
      agentDraft.llm_config.output_token_cost_per_million === undefined;

    if (!shouldApply) return;
    lastAutoPricingKeyRef.current = selectedPricingKey;
    onSetAgentDraft((current) => {
      if (current.llm_config.provider_model_id !== selectedProviderModel.id) return current;
      return {
        ...current,
        llm_config: {
          ...current.llm_config,
          input_token_cost_per_million: inputCost,
          output_token_cost_per_million: outputCost
        }
      };
    });
  }, [
    agentDraft.llm_config.input_token_cost_per_million,
    agentDraft.llm_config.output_token_cost_per_million,
    onSetAgentDraft,
    selectedPricingKey,
    selectedProviderModel
  ]);

  function updateLLM(field: keyof AgentLLMConfig, value: AgentLLMConfig[keyof AgentLLMConfig]) {
    onSetAgentDraft((current) => ({
      ...current,
      llm_config: {
        ...current.llm_config,
        [field]: value
      }
    }));
  }

  function resetLLMDefaults() {
    onSetAgentDraft((current) => ({
      ...current,
      llm_config: {
        ...defaultLLMConfig,
        provider: current.llm_config.provider,
        provider_model_id: current.llm_config.provider_model_id,
        display_name: current.llm_config.display_name
      }
    }));
  }

  return (
    <section className="scrollbar-slim min-w-0 flex-1 overflow-y-auto px-4 py-5">
      <div className="mx-auto flex max-w-6xl flex-col gap-4">
        <div className="flex flex-col justify-between gap-3 border-b border-forge-line pb-4 sm:flex-row sm:items-center">
          <div>
            <p className="text-xs uppercase text-forge-muted">Agentes</p>
            <h3 className="text-xl font-semibold">
              {editingAgentId ? agentDraft.name || "Configurar agente" : "Novo agente"}
            </h3>
          </div>
          <div className="flex gap-2">
            <Button className="h-9" onClick={onCreateAgent}>
              <Plus size={16} />
              Novo agente
            </Button>
            <Button
              className="h-9 border-forge-amber/60 bg-[#24211b]"
              onClick={onSaveAgent}
              disabled={!formIsValid}
              title={formIsValid ? "Salvar agente" : "Preencha os campos obrigatórios marcados com *"}
            >
              Salvar agente
            </Button>
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-[260px_minmax(0,1fr)_280px]">
          <section className="space-y-2 rounded-md border border-forge-line bg-[#141615] p-3">
            <PanelTitle icon={<Users size={18} />} title="Biblioteca" />
            <div className="space-y-1">
              {agents.map((agent) => (
                <button
                  key={agent.id}
                  className={[
                    "w-full rounded-md border px-3 py-2 text-left text-sm transition",
                    agent.id === editingAgentId
                      ? "border-forge-amber/60 bg-[#24211b]"
                      : "border-transparent text-forge-muted hover:bg-[#181b1e]"
                  ].join(" ")}
                  onClick={() => onSelectAgent(agent)}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="min-w-0 truncate font-medium">{agent.name}</span>
                    {!agent.enabled && <Badge>off</Badge>}
                  </div>
                  <p className="mt-1 truncate text-xs text-forge-muted">
                    {agent.llm_config?.provider_model_id ?? agent.llm_config?.provider ?? "modelo"}
                  </p>
                </button>
              ))}
            </div>
          </section>

          <section className="space-y-4">
            <div className="rounded-md border border-forge-line bg-[#141615] p-4">
              <PanelTitle icon={<Bot size={18} />} title="Identidade" />
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <Field
                  label="Nome"
                  required
                  tip="Nome curto exibido no seletor do chat e na biblioteca. Exemplos: JUDITE, Pesquisador, Revisor de Código."
                >
                  <SubFieldLabel text="Identificação" className="invisible" />
                  <input
                    value={agentDraft.name}
                    onChange={(event) => onSetAgentDraft((current) => ({ ...current, name: event.target.value }))}
                    placeholder="JUDITE"
                    required
                    className="h-10 w-full rounded-md border border-forge-line bg-[#0e0f0e] px-3 text-sm text-forge-text"
                  />
                </Field>
                <Field
                  label="Atuação"
                  required
                  tip="Define o papel principal do agente. Orquestradores viram porta de entrada do fluxo; especialistas, revisores e ferramentas atuam sob coordenação."
                >
                  <div className="grid grid-cols-2 gap-2">
                    <div className="space-y-1">
                      <SubFieldLabel text="Papel" />
                      <select
                        value={agentDraft.role}
                        onChange={(event) => {
                          const nextRole = event.target.value as Agent["role"];
                          if (nextRole === "orchestrator") setHandoffTriggersDraft("");
                          onSetAgentDraft((current) => ({
                            ...current,
                            role: nextRole,
                            handoff_triggers: nextRole === "orchestrator" ? [] : current.handoff_triggers
                          }));
                        }}
                        className="h-10 min-w-0 rounded-md border border-forge-line bg-[#0e0f0e] px-2 text-sm text-forge-text"
                      >
                        <option value="orchestrator">orquestrador</option>
                        <option value="specialist">especialista</option>
                        <option value="reviewer">revisor</option>
                        <option value="tool">ferramenta</option>
                      </select>
                    </div>
                    <div className="space-y-1">
                      <SubFieldLabel
                        text="Colaboração"
                        tip="Define o comportamento quando o orquestrador envolve este agente. Solo responde como principal; delegado recebe uma tarefa específica do orquestrador, devolve o resultado e a JUDITE sintetiza; revisor valida/critica uma resposta; paralelo responde junto com outros agentes para comparação."
                      />
                      <select
                        value={agentDraft.collaboration_mode}
                        onChange={(event) =>
                          onSetAgentDraft((current) => ({
                            ...current,
                            collaboration_mode: event.target.value as Agent["collaboration_mode"]
                          }))
                        }
                        className="h-10 min-w-0 rounded-md border border-forge-line bg-[#0e0f0e] px-2 text-sm text-forge-text"
                      >
                        <option value="standalone">solo</option>
                        <option value="delegate">delegado</option>
                        <option value="review">revisor</option>
                        <option value="parallel">paralelo</option>
                      </select>
                    </div>
                  </div>
                </Field>
                <Field
                  label="Descrição"
                  className={agentDraft.role === "orchestrator" ? "md:col-span-2" : ""}
                  tip="Resumo operacional para humanos e para a JUDITE entender quando usar este agente. Exemplo: pesquisa mercado, compara fontes e aponta riscos."
                >
                  <textarea
                    value={agentDraft.description}
                    onChange={(event) =>
                      onSetAgentDraft((current) => ({ ...current, description: event.target.value }))
                    }
                    rows={3}
                    placeholder="Especialidade operacional do agente"
                    className="min-h-24 w-full resize-none rounded-md border border-forge-line bg-[#0e0f0e] px-3 py-2 text-sm text-forge-text"
                  />
                </Field>
                {agentDraft.role !== "orchestrator" && (
                  <Field
                    label="Gatilhos"
                    tip="Palavras ou frases separadas por vírgula que indicam quando este agente deve ser considerado. Exemplos: pesquisa, revisão, código, estratégia."
                  >
                    <textarea
                      value={handoffTriggersDraft}
                      onChange={(event) => {
                        setHandoffTriggersDraft(event.target.value);
                        onSetAgentDraft((current) => ({
                          ...current,
                          handoff_triggers: csvToList(event.target.value)
                        }));
                      }}
                      rows={3}
                      placeholder="pesquisa, revisão, código"
                      className="min-h-24 w-full resize-none rounded-md border border-forge-line bg-[#0e0f0e] px-3 py-2 text-sm text-forge-text"
                    />
                  </Field>
                )}
              </div>
              <Field
                label="Prompt do sistema"
                required
                className="mt-3"
                tip="Instruções persistentes do agente: objetivo, tom, método, limites e critérios de qualidade. Exemplo: responda em PT-BR, cite incertezas e peça confirmação antes de ações perigosas."
              >
                <textarea
                  value={agentDraft.system_prompt}
                  onChange={(event) =>
                    onSetAgentDraft((current) => ({ ...current, system_prompt: event.target.value }))
                  }
                  rows={7}
                  placeholder="Instruções centrais do agente"
                  required
                  className="min-h-40 w-full resize-y rounded-md border border-forge-line bg-[#0e0f0e] px-3 py-2 text-sm leading-6 text-forge-text"
                />
              </Field>
              <Field
                label="Projetos permitidos"
                required
                className="mt-3"
                tip="Define quais projetos este agente pode usar como contexto no chat. Você pode habilitar até 3 projetos, incluindo o Geral."
              >
                <div className="grid gap-2 md:grid-cols-2">
                  {selectableAgentProjects.map((project) => {
                    const checked = normalizedAllowedProjectIds.includes(project.id);
                    const maxReached = normalizedAllowedProjectIds.length >= 3;
                    return (
                      <label
                        key={project.id}
                        className={[
                          "flex cursor-pointer items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm transition",
                          checked ? "border-forge-amber/60 bg-[#24211b]" : "border-forge-line bg-[#0e0f0e]",
                          !checked && maxReached ? "opacity-60" : ""
                        ].join(" ")}
                      >
                        <span className="inline-flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={checked}
                            disabled={!checked && maxReached}
                            onChange={(event) =>
                              onSetAgentDraft((current) => {
                                const currentIds = current.allowed_project_ids.length
                                  ? current.allowed_project_ids
                                  : [generalProjectId];
                                const nextIds = event.target.checked
                                  ? [...currentIds, project.id]
                                  : currentIds.filter((projectId) => projectId !== project.id);
                                const normalizedNext = nextIds
                                  .filter((projectId, index, list) => list.indexOf(projectId) === index)
                                  .slice(0, 3);
                                return {
                                  ...current,
                                  allowed_project_ids: normalizedNext.length ? normalizedNext : [generalProjectId]
                                };
                              })
                            }
                          />
                          <span>{project.label}</span>
                        </span>
                        {project.isGeneral && <Badge>geral</Badge>}
                      </label>
                    );
                  })}
                </div>
                <p className="mt-2 text-xs text-forge-muted">
                  Selecionados: {normalizedAllowedProjectIds.length} de 3.
                </p>
              </Field>
              <Field
                label="Bases do agente"
                className="mt-3"
                tip="Bases que acompanham este agente independentemente do projeto atual. Use para conhecimento permanente da especialidade dele."
              >
                <div className="grid gap-2 md:grid-cols-2">
                  {knowledgeBases.map((knowledgeBase) => {
                    const checked = agentDraft.knowledge_base_ids.includes(knowledgeBase.id);
                    return (
                      <label
                        key={knowledgeBase.id}
                        className={[
                          "flex cursor-pointer items-start justify-between gap-2 rounded-md border px-3 py-2 text-sm transition",
                          checked ? "border-forge-amber/60 bg-[#24211b]" : "border-forge-line bg-[#0e0f0e]"
                        ].join(" ")}
                      >
                        <span className="inline-flex min-w-0 items-start gap-2">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={(event) =>
                              onSetAgentDraft((current) => ({
                                ...current,
                                knowledge_base_ids: event.target.checked
                                  ? [...new Set([...current.knowledge_base_ids, knowledgeBase.id])]
                                  : current.knowledge_base_ids.filter((item) => item !== knowledgeBase.id)
                              }))
                            }
                          />
                          <span className="min-w-0">
                            <span className="block truncate">{knowledgeBase.name}</span>
                            <span className="mt-1 block line-clamp-2 text-xs text-forge-muted">
                              {knowledgeBase.scope || knowledgeBase.description || "Sem escopo definido."}
                            </span>
                          </span>
                        </span>
                        {!knowledgeBase.enabled && <Badge>off</Badge>}
                      </label>
                    );
                  })}
                  {!knowledgeBases.length && <EmptyPanel text="Crie bases na aba Bases para anexar ao agente." />}
                </div>
              </Field>
              <label className="mt-3 flex items-center gap-2 text-sm text-forge-muted">
                <input
                  type="checkbox"
                  checked={agentDraft.enabled}
                  onChange={(event) => onSetAgentDraft((current) => ({ ...current, enabled: event.target.checked }))}
                />
                <span>agente habilitado</span>
                <InfoTip text="Quando desligado, o agente continua salvo, mas não aparece nas opções normais de chat e não pode ser escolhido como apoio no modo multiagente." />
              </label>
            </div>

            <div className="rounded-md border border-forge-line bg-[#141615] p-4">
              <div className="flex items-center justify-between gap-3 border-b border-forge-line pb-2">
                <span className="flex items-center gap-2 text-sm font-semibold">
                  <Settings2 size={18} />
                  Modelo do agente
                  <InfoTip text="Configuração usada pelo agente quando ele chama um LLM. Modelo é obrigatório para chamadas reais; custos são necessários para o Cost Governor controlar orçamento." />
                </span>
                <Button className="h-8 text-xs" onClick={resetLLMDefaults}>
                  Restaurar padrões
                </Button>
              </div>
              <div className="mt-3 flex flex-wrap gap-2 text-xs text-forge-muted">
                <Badge>padrão novo: OpenAI</Badge>
                <Badge>temp 1</Badge>
                <Badge>top_p 1</Badge>
                <Badge>máx. 2048</Badge>
                <Badge>tools auto</Badge>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <Field
                  label="Provedor"
                  required
                  tip="Fornecedor que executa o modelo do agente. O MVP suporta OpenAI, Anthropic e Google."
                >
                  <select
                    value={provider}
                    onChange={(event) => {
                      const nextProvider = event.target.value as ProviderName;
                      onSetAgentDraft((current) => ({
                        ...current,
                        llm_config: {
                          ...defaultLLMConfig,
                          provider: nextProvider
                        }
                      }));
                    }}
                    className="h-10 w-full rounded-md border border-forge-line bg-[#0e0f0e] px-2 text-sm text-forge-text"
                  >
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic</option>
                    <option value="google">Google Gemini</option>
                  </select>
                </Field>
                <Field
                  label="Modelo"
                  required
                  tip="ID real do modelo no provedor. Use o botão de atualizar para buscar modelos disponíveis e evitar erro de digitação."
                >
                  <div className="flex gap-2">
                    <select
                      value={agentDraft.llm_config.provider_model_id ?? ""}
                      onChange={(event) => {
                        const selected = providerModels.find((item) => item.id === event.target.value);
                        onSetAgentDraft((current) => ({
                          ...current,
                          llm_config: {
                            ...current.llm_config,
                            provider_model_id: event.target.value || null,
                            display_name: selected?.display_name ?? null,
                            temperature: selected?.default_temperature ?? current.llm_config.temperature,
                            top_p: selected?.default_top_p ?? current.llm_config.top_p,
                            top_k: selected?.default_top_k ?? current.llm_config.top_k,
                            input_token_cost_per_million:
                              selected?.input_token_cost_per_million ?? current.llm_config.input_token_cost_per_million,
                            output_token_cost_per_million:
                              selected?.output_token_cost_per_million ??
                              current.llm_config.output_token_cost_per_million
                          }
                        }));
                      }}
                      className="h-10 min-w-0 flex-1 rounded-md border border-forge-line bg-[#0e0f0e] px-2 text-sm text-forge-text"
                    >
                      <option value="">{providerModels.length ? "Selecione" : "Buscar modelos"}</option>
                      {providerModels.map((providerModel) => (
                        <option key={providerModel.id} value={providerModel.id}>
                          {providerModel.display_name}
                        </option>
                      ))}
                    </select>
                    <Button
                      className="h-10 px-3"
                      onClick={() => onLoadProviderModels(provider)}
                      disabled={catalogState === "loading"}
                      aria-label={`Buscar modelos ${provider}`}
                      title={`Buscar modelos ${provider}`}
                    >
                      <RefreshCw size={16} />
                    </Button>
                  </div>
                  {catalogError && <p className="mt-2 text-xs text-forge-red">{catalogError}</p>}
                </Field>
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-4">
                <AgentLLMNumberInput
                  label="Temperatura"
                  field="temperature"
                  value={agentDraft.llm_config.temperature ?? ""}
                  tip="Controla criatividade/variação. 0 é mais determinístico; 1 é equilibrado; valores altos podem ficar mais soltos."
                  onChange={updateLLM}
                />
                <AgentLLMNumberInput
                  label="Top P"
                  field="top_p"
                  value={agentDraft.llm_config.top_p ?? ""}
                  tip="Limita a amostragem por probabilidade acumulada. Use 1 como padrão; reduza se quiser respostas mais previsíveis."
                  onChange={updateLLM}
                />
                <AgentLLMNumberInput
                  label="Top K"
                  field="top_k"
                  value={agentDraft.llm_config.top_k ?? ""}
                  tip="Limita a quantidade de tokens candidatos. É mais comum em Google/Anthropic; deixe vazio se o provedor/modelo não usar."
                  onChange={updateLLM}
                />
                <AgentLLMNumberInput
                  label="Máx. saída"
                  field="max_output_tokens"
                  value={agentDraft.llm_config.max_output_tokens ?? ""}
                  tip="Limite máximo de tokens de resposta. Use 2048 para respostas normais e 4096+ para sínteses longas."
                  required
                  onChange={updateLLM}
                />
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-4">
                <AgentLLMSelect
                  label="Raciocínio"
                  field="reasoning_effort"
                  value={agentDraft.llm_config.reasoning_effort ?? ""}
                  options={["", "none", "minimal", "low", "medium", "high", "xhigh"]}
                  tip="Esforço de raciocínio quando o modelo suportar. Medium é bom padrão; high/xhigh pode aumentar latência e custo."
                  onChange={updateLLM}
                />
                <AgentLLMNumberInput
                  label="Budget raciocínio"
                  field="reasoning_budget_tokens"
                  value={agentDraft.llm_config.reasoning_budget_tokens ?? ""}
                  tip="Orçamento explícito de tokens de pensamento para provedores que aceitam esse parâmetro. Deixe vazio no padrão."
                  onChange={updateLLM}
                />
                <AgentLLMSelect
                  label="Verbosidade"
                  field="verbosity"
                  value={agentDraft.llm_config.verbosity ?? ""}
                  options={["", "low", "medium", "high"]}
                  tip="Controla quão detalhada a resposta tende a ser quando o modelo suporta. Medium é o padrão equilibrado."
                  onChange={updateLLM}
                />
                <AgentLLMSelect
                  label="Resposta"
                  field="response_format"
                  value={agentDraft.llm_config.response_format}
                  options={["text", "json"]}
                  tip="Formato esperado da resposta. Use text para chat normal e json para saídas estruturadas consumidas por ferramentas."
                  required
                  onChange={updateLLM}
                />
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-4">
                <AgentLLMSelect
                  label="Ferramentas"
                  field="tool_choice"
                  value={agentDraft.llm_config.tool_choice}
                  options={["auto", "none", "required"]}
                  tip="Define uso de ferramentas: auto deixa o modelo decidir, none bloqueia ferramentas, required força uso quando disponível."
                  required
                  onChange={updateLLM}
                />
                <AgentLLMNumberInput
                  label="Presence penalty"
                  field="presence_penalty"
                  value={agentDraft.llm_config.presence_penalty ?? ""}
                  tip="Penaliza repetição de tópicos já mencionados. Normalmente deixe vazio ou 0; valores altos podem dispersar a resposta."
                  onChange={updateLLM}
                />
                <AgentLLMNumberInput
                  label="Frequency penalty"
                  field="frequency_penalty"
                  value={agentDraft.llm_config.frequency_penalty ?? ""}
                  tip="Penaliza repetição literal de palavras/tokens. Normalmente deixe vazio ou 0."
                  onChange={updateLLM}
                />
                <AgentLLMNumberInput
                  label="Seed"
                  field="seed"
                  value={agentDraft.llm_config.seed ?? ""}
                  tip="Semente para tentar reproduzir saídas quando o provedor suportar. Deixe vazio para uso normal."
                  onChange={updateLLM}
                />
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                <AgentLLMNumberInput
                  label="US$/M input"
                  field="input_token_cost_per_million"
                  value={agentDraft.llm_config.input_token_cost_per_million ?? ""}
                  tip="Preço em dólar por 1 milhão de tokens de entrada. Necessário para o Cost Governor estimar gastos."
                  required
                  onChange={updateLLM}
                />
                <AgentLLMNumberInput
                  label="US$/M output"
                  field="output_token_cost_per_million"
                  value={agentDraft.llm_config.output_token_cost_per_million ?? ""}
                  tip="Preço em dólar por 1 milhão de tokens de saída. Tokens de raciocínio e summaries contam como saída quando cobrados pelo provedor."
                  required
                  onChange={updateLLM}
                />
                <Field
                  label="Stop sequences"
                  tip="Sequências separadas por vírgula que interrompem a geração. Exemplo: END, STOP. Deixe vazio na maioria dos agentes."
                >
                  <input
                    value={agentDraft.llm_config.stop_sequences.join(", ")}
                    onChange={(event) => updateLLM("stop_sequences", csvToList(event.target.value))}
                    placeholder="END, STOP"
                    className="h-10 w-full rounded-md border border-forge-line bg-[#0e0f0e] px-3 text-sm text-forge-text"
                  />
                </Field>
              </div>
              {selectedPricingKey && (
                <div className="mt-2 flex flex-wrap gap-2 text-xs text-forge-muted">
                  <Badge>preço auto</Badge>
                  {selectedProviderModel?.pricing_source && (
                    <Badge className="max-w-full truncate">
                      {selectedProviderModel.pricing_source.replace(/^https?:\/\//, "")}
                    </Badge>
                  )}
                </div>
              )}
              <label className="mt-3 flex items-center gap-2 text-sm text-forge-muted">
                <input
                  type="checkbox"
                  checked={agentDraft.llm_config.parallel_tool_calls}
                  onChange={(event) => updateLLM("parallel_tool_calls", event.target.checked)}
                />
                chamadas paralelas de ferramentas
              </label>
            </div>
          </section>

          <section className="space-y-3 rounded-md border border-forge-line bg-[#141615] p-3">
            <PanelTitle icon={<Users size={18} />} title="Multiagente" />
            <Field label="Agente principal">
              <select
                value={activeAgent?.id ?? ""}
                onChange={(event) => onSetActiveAgentId(event.target.value)}
                className="h-10 w-full rounded-md border border-forge-line bg-[#0e0f0e] px-2 text-sm text-forge-text"
              >
                {agents
                  .filter((agent) => agent.enabled)
                  .map((agent) => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name}
                    </option>
                  ))}
              </select>
            </Field>
            <div className="space-y-2">
              {agents
                .filter((agent) => agent.id !== activeAgent?.id)
                .map((agent) => (
                  <label
                    key={agent.id}
                    className="flex items-center gap-2 rounded-md border border-forge-line bg-[#0e0f0e] px-3 py-2 text-sm text-forge-muted"
                  >
                    <input
                      type="checkbox"
                      checked={supportAgentIds.includes(agent.id)}
                      onChange={(event) => onToggleSupportAgent(agent.id, event.target.checked)}
                    />
                    <span className="min-w-0 flex-1 truncate">{agent.name}</span>
                    <Badge>{agent.role}</Badge>
                  </label>
                ))}
              {!agents.length && <EmptyPanel text="Nenhum agente criado." />}
            </div>
          </section>
        </div>
      </div>
    </section>
  );
}

export function ModelingDashboard({ projects }: { projects: ProjectRecord[] }) {
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [prompt, setPrompt] = useState("");
  const [mode, setMode] = useState<ModelingExecutionMode>("approval_required");
  const [softwareOverride, setSoftwareOverride] = useState<ModelingSoftware>("auto");
  const [projectId, setProjectId] = useState<string>("");
  const [isBusy, setIsBusy] = useState(false);
  const [status, setStatus] = useState("");
  const modelingQuery = useQuery({
    queryKey: ["modeling-dashboard"],
    queryFn: async () => {
      const [nextCapabilities, nextPlans] = await Promise.all([api.modelingCapabilities(), api.modelingPlans()]);
      return { capabilities: nextCapabilities, plans: nextPlans };
    },
    staleTime: 15_000
  });
  const capabilities: ModelingCapabilities | null = modelingQuery.data?.capabilities ?? null;
  const plans: ModelingPlan[] = useMemo(() => modelingQuery.data?.plans ?? [], [modelingQuery.data?.plans]);

  const selectedPlan = useMemo(
    () => plans.find((plan) => plan.id === selectedPlanId) ?? plans[0] ?? null,
    [plans, selectedPlanId]
  );

  async function createPlan() {
    if (!prompt.trim()) return;
    setIsBusy(true);
    setStatus("Gerando plano 3D estruturado...");
    try {
      const plan = await api.createModelingPlan({
        prompt,
        mode,
        project_id: projectId || null,
        software_override: softwareOverride === "auto" ? null : softwareOverride
      });
      setSelectedPlanId(plan.id);
      await modelingQuery.refetch();
      setStatus("Plano criado. Revise as etapas antes de executar.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Falha ao criar plano 3D.");
    } finally {
      setIsBusy(false);
    }
  }

  async function approveSelectedPlan() {
    if (!selectedPlan) return;
    setIsBusy(true);
    setStatus("Aprovando plano...");
    try {
      const plan = await api.approveModelingPlan(selectedPlan.id, {
        decision: "approve",
        reason: "Aprovado pela UI do módulo 3D."
      });
      setSelectedPlanId(plan.id);
      await modelingQuery.refetch();
      setStatus("Plano aprovado. A execução ainda passa pelo adapter MCP local/mock.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Falha ao aprovar plano.");
    } finally {
      setIsBusy(false);
    }
  }

  async function executeSelectedPlan() {
    if (!selectedPlan) return;
    setIsBusy(true);
    setStatus("Preparando execução MCP local...");
    try {
      const result = await api.executeModelingPlan(selectedPlan.id);
      setSelectedPlanId(result.plan.id);
      await modelingQuery.refetch();
      setStatus(
        result.blocked_step_ids.length
          ? "Execução parcial: ainda há etapas aguardando aprovação."
          : "Execução mock concluída e auditada."
      );
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Falha ao executar plano.");
    } finally {
      setIsBusy(false);
    }
  }

  async function startAdapterSession(software: Exclude<ModelingSoftware, "auto">) {
    setIsBusy(true);
    setStatus(`Iniciando sessão ${software} em modo mock...`);
    try {
      await api.startModelingSession({
        software,
        project_id: projectId || null,
        force_mock: true
      });
      setStatus(`Sessão ${software} registrada. Instale o adapter desktop para execução real.`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Falha ao iniciar sessão 3D.");
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <section className="scrollbar-slim min-w-0 flex-1 overflow-y-auto px-4 py-5">
      <div className="mx-auto grid max-w-6xl gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-4">
          <div className="rounded-md border border-forge-line bg-[#141615] p-4">
            <div className="flex flex-col justify-between gap-3 border-b border-forge-line pb-3 md:flex-row md:items-center">
              <PanelTitle icon={<LayoutGrid size={18} />} title="Modelagem 3D por MCP" />
              <div className="flex flex-wrap gap-2">
                <Button className="h-9" disabled={isBusy} onClick={() => void startAdapterSession("blender")}>
                  Blender
                </Button>
                <Button className="h-9" disabled={isBusy} onClick={() => void startAdapterSession("fusion")}>
                  Fusion 360
                </Button>
              </div>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <Field label="Projeto">
                <select
                  value={projectId}
                  onChange={(event) => setProjectId(event.target.value)}
                  className="h-10 w-full rounded-md border border-forge-line bg-[#0e0f0e] px-2 text-sm text-forge-text"
                >
                  <option value="">Contexto geral</option>
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {projectDisplayName(project)}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Software">
                <select
                  value={softwareOverride}
                  onChange={(event) => setSoftwareOverride(event.target.value as ModelingSoftware)}
                  className="h-10 w-full rounded-md border border-forge-line bg-[#0e0f0e] px-2 text-sm text-forge-text"
                >
                  <option value="auto">roteamento automático</option>
                  <option value="fusion">Fusion 360</option>
                  <option value="blender">Blender</option>
                </select>
              </Field>
              <Field label="Modo">
                <select
                  value={mode}
                  onChange={(event) => setMode(event.target.value as ModelingExecutionMode)}
                  className="h-10 w-full rounded-md border border-forge-line bg-[#0e0f0e] px-2 text-sm text-forge-text"
                >
                  <option value="plan_only">planejar apenas</option>
                  <option value="approval_required">executar com aprovação</option>
                  <option value="safe_auto">ações seguras automáticas</option>
                </select>
              </Field>
            </div>
            <Field
              label="Prompt de modelagem"
              className="mt-3"
              tip="Descreva a peça, unidade, medidas, tolerâncias, formato desejado e saída esperada. Exemplo: crie um suporte paramétrico de 85x40x20 mm com furo central de 5 mm."
            >
              <textarea
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                rows={5}
                placeholder="Ex: crie um suporte paramétrico para fone com base 85 mm, chanfros suaves e export STL."
                className="min-h-32 w-full resize-y rounded-md border border-forge-line bg-[#0e0f0e] px-3 py-2 text-sm leading-6 text-forge-text"
              />
            </Field>
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
              <p className="text-xs text-forge-muted">
                A primeira versão cria plano auditável e chama adapters MCP em modo mock.
              </p>
              <Button
                className="h-9 border-forge-amber/60 bg-[#24211b]"
                disabled={isBusy || !prompt.trim()}
                onClick={() => void createPlan()}
              >
                {isBusy ? <LoaderCircle size={16} className="animate-spin" /> : <Plus size={16} />}
                Gerar plano
              </Button>
            </div>
            {status && (
              <p className="mt-3 rounded-md border border-forge-line bg-[#0e0f0e] p-2 text-xs text-forge-muted">
                {status}
              </p>
            )}
          </div>

          {selectedPlan && (
            <div className="rounded-md border border-forge-line bg-[#141615] p-4">
              <div className="flex flex-col justify-between gap-3 border-b border-forge-line pb-3 md:flex-row md:items-center">
                <div>
                  <PanelTitle icon={<Settings2 size={18} />} title="Plano selecionado" />
                  <p className="mt-2 text-xs text-forge-muted">{selectedPlan.rationale}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Badge>{selectedPlan.software_choice}</Badge>
                  <Badge>{Math.round(selectedPlan.confidence * 100)}%</Badge>
                  <Badge>{selectedPlan.status}</Badge>
                </div>
              </div>
              <div className="mt-4 space-y-2">
                {selectedPlan.steps.map((step) => (
                  <div key={step.id} className="rounded-md border border-forge-line bg-[#0e0f0e] p-3 text-sm">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h4 className="font-semibold">
                          {step.seq}. {step.title}
                        </h4>
                        <p className="mt-1 text-xs text-forge-muted">{step.tool_name}</p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Badge>{step.risk_level}</Badge>
                        <Badge>{step.approval_required ? "aprovação" : "auto"}</Badge>
                        <Badge>{step.status}</Badge>
                      </div>
                    </div>
                    {typeof step.output_json.message === "string" && (
                      <p className="mt-2 text-xs text-forge-muted">{step.output_json.message}</p>
                    )}
                    {step.error && <p className="mt-2 text-xs text-forge-red">{step.error}</p>}
                  </div>
                ))}
              </div>
              <div className="mt-4 flex flex-wrap justify-end gap-2">
                <Button
                  className="h-9"
                  disabled={isBusy || selectedPlan.status === "completed"}
                  onClick={() => void approveSelectedPlan()}
                >
                  Aprovar plano
                </Button>
                <Button
                  className="h-9 border-forge-amber/60 bg-[#24211b]"
                  disabled={isBusy}
                  onClick={() => void executeSelectedPlan()}
                >
                  Executar MCP
                </Button>
              </div>
            </div>
          )}
        </div>

        <aside className="space-y-4">
          <div className="rounded-md border border-forge-line bg-[#141615] p-3">
            <PanelTitle icon={<RefreshCw size={18} />} title="Adapters MCP" />
            <div className="mt-3 space-y-2">
              {capabilities?.adapters.map((adapter) => (
                <div key={adapter.software} className="rounded-md border border-forge-line bg-[#0e0f0e] p-3 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold">{adapter.software}</span>
                    <Badge>{adapter.transport}</Badge>
                  </div>
                  <p className="mt-2 leading-5 text-forge-muted">{adapter.detail}</p>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {adapter.tools.map((tool) => (
                      <Badge key={tool}>{tool}</Badge>
                    ))}
                  </div>
                </div>
              ))}
              {!capabilities && <EmptyPanel text="Carregando capacidades MCP." />}
            </div>
          </div>

          <div className="rounded-md border border-forge-line bg-[#141615] p-3">
            <PanelTitle icon={<List size={18} />} title="Planos recentes" />
            <div className="mt-3 space-y-2">
              {plans.map((plan) => (
                <button
                  key={plan.id}
                  type="button"
                  className={[
                    "w-full rounded-md border p-3 text-left text-xs transition",
                    selectedPlan?.id === plan.id
                      ? "border-forge-amber/60 bg-[#24211b]"
                      : "border-forge-line bg-[#0e0f0e] hover:border-forge-amber/40"
                  ].join(" ")}
                  onClick={() => setSelectedPlanId(plan.id)}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="line-clamp-1 font-semibold">{plan.prompt}</span>
                    <Badge>{plan.software_choice}</Badge>
                  </div>
                  <p className="mt-2 text-forge-muted">
                    {plan.steps.length} etapas / {plan.status}
                  </p>
                </button>
              ))}
              {!plans.length && <EmptyPanel text="Nenhum plano 3D criado ainda." />}
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}

export function ProjectsDashboard({
  projects,
  folders,
  knowledgeBases,
  knowledgeBaseDocuments,
  selectedProject,
  selectedFolderId,
  projectDraft,
  folderDraftName,
  folderDraftParentId,
  status,
  onSelectProject,
  onSelectFolder,
  onSetProjectDraft,
  onSetFolderDraftName,
  onSetFolderDraftParentId,
  onSaveProject,
  onCreateFolder
}: {
  projects: ProjectRecord[];
  folders: ProjectFolder[];
  knowledgeBases: KnowledgeBase[];
  knowledgeBaseDocuments: KnowledgeBaseDocument[];
  selectedProject: ProjectRecord | null;
  selectedFolderId: string | null;
  projectDraft: ProjectUpsert;
  folderDraftName: string;
  folderDraftParentId: string | null;
  status: { type: "idle" | "error" | "success"; message: string };
  onSelectProject: (projectId: string | null) => void;
  onSelectFolder: (folderId: string | null) => void;
  onSetProjectDraft: Dispatch<SetStateAction<ProjectUpsert>>;
  onSetFolderDraftName: (value: string) => void;
  onSetFolderDraftParentId: (value: string | null) => void;
  onSaveProject: () => void;
  onCreateFolder: () => void;
}) {
  const projectFolders = folders.filter((folder) => folder.project_id === selectedProject?.id);
  const folderById = useMemo(() => new Map(projectFolders.map((folder) => [folder.id, folder])), [projectFolders]);
  const selectedFolder = selectedFolderId ? (folderById.get(selectedFolderId) ?? null) : null;
  const parentFolder = folderDraftParentId ? (folderById.get(folderDraftParentId) ?? null) : null;
  const nextFolderDepth = parentFolder ? parentFolder.depth + 1 : 0;
  const maxDepthReached = nextFolderDepth > 5;
  const generalProject = projects.find((project) => project.is_general) ?? null;
  const customProjects = projects.filter((project) => !project.is_general);

  return (
    <section className="scrollbar-slim min-w-0 flex-1 overflow-y-auto px-4 py-5">
      <div className="mx-auto flex max-w-6xl flex-col gap-4">
        <div className="flex flex-col justify-between gap-3 border-b border-forge-line pb-4 sm:flex-row sm:items-center">
          <div>
            <p className="text-xs uppercase text-forge-muted">Projetos</p>
            <h3 className="text-xl font-semibold">{selectedProject?.name ?? "Novo projeto"}</h3>
          </div>
          <div className="flex items-center gap-2">
            <Badge>max docs: 20</Badge>
            <Button className="h-9 border-forge-amber/60 bg-[#24211b]" onClick={onSaveProject}>
              <Save size={16} />
              {selectedProject
                ? selectedProject.is_general
                  ? "Atualizar contexto geral"
                  : "Atualizar projeto"
                : "Criar projeto"}
            </Button>
          </div>
        </div>

        {status.type !== "idle" && (
          <div
            className={[
              "rounded-md border p-3 text-sm",
              status.type === "error"
                ? "border-forge-red/50 bg-[#2a1112] text-forge-red"
                : "border-forge-green/50 bg-[#11251a] text-forge-green"
            ].join(" ")}
          >
            {status.message}
          </div>
        )}

        <div className="grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)]">
          <section className="space-y-2 rounded-md border border-forge-line bg-[#141615] p-3">
            <PanelTitle icon={<FolderTree size={18} />} title="Projetos" />
            <button
              type="button"
              className={[
                "w-full rounded-md border px-3 py-2 text-left text-sm transition",
                !selectedProject ? "border-forge-amber/60 bg-[#24211b]" : "border-forge-line bg-[#0e0f0e]"
              ].join(" ")}
              onClick={() => onSelectProject(null)}
            >
              Novo projeto
            </button>
            {generalProject && (
              <button
                type="button"
                className={[
                  "w-full rounded-md border px-3 py-2 text-left text-sm transition",
                  selectedProject?.id === generalProject.id
                    ? "border-forge-amber/60 bg-[#24211b]"
                    : "border-forge-line bg-[#0e0f0e] hover:border-forge-amber/40"
                ].join(" ")}
                onClick={() => {
                  onSelectProject(generalProject.id);
                  onSelectFolder(null);
                }}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="min-w-0 truncate font-medium">Contexto geral</span>
                  <Badge>geral</Badge>
                </div>
                <p className="mt-1 line-clamp-2 text-xs text-forge-muted">
                  {generalProject.description || "Chat e arquivos sem projeto específico."}
                </p>
              </button>
            )}
            {customProjects.map((project) => (
              <button
                key={project.id}
                type="button"
                className={[
                  "w-full rounded-md border px-3 py-2 text-left text-sm transition",
                  selectedProject?.id === project.id
                    ? "border-forge-amber/60 bg-[#24211b]"
                    : "border-forge-line bg-[#0e0f0e] hover:border-forge-amber/40"
                ].join(" ")}
                onClick={() => {
                  onSelectProject(project.id);
                  onSelectFolder(null);
                }}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="min-w-0 truncate font-medium">{projectDisplayName(project)}</span>
                </div>
                <p className="mt-1 line-clamp-2 text-xs text-forge-muted">{project.description || "Sem descrição"}</p>
              </button>
            ))}
          </section>

          <section className="space-y-4">
            <div className="rounded-md border border-forge-line bg-[#141615] p-4">
              <PanelTitle icon={<Settings2 size={18} />} title="Projeto selecionado" />
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <Field label="Nome">
                  <input
                    value={projectDraft.name}
                    onChange={(event) => onSetProjectDraft((current) => ({ ...current, name: event.target.value }))}
                    placeholder="Ex: Produto X"
                    className="h-10 w-full rounded-md border border-forge-line bg-[#0e0f0e] px-3 text-sm text-forge-text"
                  />
                </Field>
                <Field label="Cor">
                  <input
                    type="color"
                    value={projectDraft.color}
                    onChange={(event) => onSetProjectDraft((current) => ({ ...current, color: event.target.value }))}
                    className="h-10 w-full rounded-md border border-forge-line bg-[#0e0f0e] p-1"
                    aria-label="Cor do projeto"
                    title="Cor do projeto"
                  />
                </Field>
              </div>
              <Field label="Descrição" className="mt-3">
                <textarea
                  value={projectDraft.description}
                  onChange={(event) =>
                    onSetProjectDraft((current) => ({ ...current, description: event.target.value }))
                  }
                  rows={3}
                  placeholder="Objetivo do projeto, escopo e notas."
                  className="min-h-20 w-full resize-none rounded-md border border-forge-line bg-[#0e0f0e] px-3 py-2 text-sm text-forge-text"
                />
              </Field>
              <Field
                label="Bases atreladas"
                className="mt-3"
                tip="Bases selecionadas alimentam a busca semântica do projeto. Pastas continuam organizando chats; se citadas com @, funcionam como filtro opcional."
              >
                <div className="grid gap-2 md:grid-cols-2">
                  {knowledgeBases.map((knowledgeBase) => {
                    const checked = projectDraft.context.knowledge_base_ids.includes(knowledgeBase.id);
                    const count = knowledgeBaseDocuments.filter(
                      (item) => item.knowledge_base_id === knowledgeBase.id && item.enabled
                    ).length;
                    return (
                      <label
                        key={knowledgeBase.id}
                        className={[
                          "flex cursor-pointer items-start gap-2 rounded-md border px-3 py-2 text-sm transition",
                          checked ? "border-forge-amber/60 bg-[#24211b]" : "border-forge-line bg-[#0e0f0e]"
                        ].join(" ")}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(event) =>
                            onSetProjectDraft((current) => ({
                              ...current,
                              context: {
                                ...current.context,
                                knowledge_base_ids: event.target.checked
                                  ? [...new Set([...current.context.knowledge_base_ids, knowledgeBase.id])]
                                  : current.context.knowledge_base_ids.filter((item) => item !== knowledgeBase.id)
                              }
                            }))
                          }
                        />
                        <span className="min-w-0 flex-1">
                          <span className="flex items-center justify-between gap-2">
                            <span className="truncate font-medium">{knowledgeBase.name}</span>
                            <Badge>{count} docs</Badge>
                          </span>
                          <span className="mt-1 block line-clamp-2 text-xs text-forge-muted">
                            {knowledgeBase.scope || knowledgeBase.description || "Sem escopo definido."}
                          </span>
                        </span>
                      </label>
                    );
                  })}
                  {!knowledgeBases.length && <EmptyPanel text="Crie uma base na aba Bases para atrelar ao projeto." />}
                </div>
              </Field>
            </div>

            <div className="rounded-md border border-forge-line bg-[#141615] p-4">
              <PanelTitle icon={<Library size={18} />} title="Pastas do projeto" />
              {!selectedProject && (
                <p className="mt-3 text-sm text-forge-muted">Selecione um projeto para organizar as pastas.</p>
              )}
              {selectedProject && (
                <>
                  <div className="mt-3 grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
                    <Field label="Nome da pasta">
                      <input
                        value={folderDraftName}
                        onChange={(event) => onSetFolderDraftName(event.target.value)}
                        placeholder="Ex: Requisitos"
                        className="h-10 w-full rounded-md border border-forge-line bg-[#0e0f0e] px-3 text-sm text-forge-text"
                      />
                    </Field>
                    <Field label="Pasta mãe">
                      <select
                        value={folderDraftParentId ?? ""}
                        onChange={(event) => onSetFolderDraftParentId(event.target.value || null)}
                        className="h-10 w-full rounded-md border border-forge-line bg-[#0e0f0e] px-2 text-sm text-forge-text"
                      >
                        <option value="">Raiz</option>
                        {projectFolders.map((folder) => (
                          <option key={folder.id} value={folder.id}>
                            {folder.path}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <div className="flex items-end">
                      <Button
                        className="h-10"
                        onClick={onCreateFolder}
                        disabled={!folderDraftName.trim() || maxDepthReached}
                        title={maxDepthReached ? "Somente 5 subníveis são permitidos por pasta." : "Criar nova pasta"}
                      >
                        <Plus size={16} />
                        Pasta
                      </Button>
                    </div>
                  </div>
                  <p className="mt-2 text-xs text-forge-muted">
                    Nível da nova pasta: {Math.min(nextFolderDepth, 5)} de 5.
                  </p>
                  {maxDepthReached && (
                    <p className="mt-1 text-xs text-forge-red">
                      Limite atingido: apenas 5 subníveis são permitidos nesta árvore.
                    </p>
                  )}
                  <div className="mt-3 max-h-72 space-y-2 overflow-y-auto pr-1">
                    {projectFolders.map((folder) => (
                      <button
                        key={folder.id}
                        type="button"
                        className={[
                          "w-full rounded-md border px-3 py-2 text-left text-sm transition",
                          selectedFolder?.id === folder.id
                            ? "border-forge-amber/60 bg-[#24211b]"
                            : "border-forge-line bg-[#0e0f0e] hover:border-forge-amber/40"
                        ].join(" ")}
                        onClick={() => onSelectFolder(folder.id)}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate font-medium">{folder.path}</span>
                          <Badge>nível {folder.depth}</Badge>
                        </div>
                      </button>
                    ))}
                    {!projectFolders.length && <EmptyPanel text="Nenhuma pasta criada neste projeto." />}
                  </div>
                </>
              )}
            </div>
          </section>
        </div>
      </div>
    </section>
  );
}

export function FilesDashboard({
  documents,
  onUploadFiles,
  onCreateKnowledgeBaseFromFile,
  onUpdateFile,
  onDeleteFile
}: {
  documents: DocumentRecord[];
  onUploadFiles: (files: File[]) => void;
  onCreateKnowledgeBaseFromFile: (fileId: string) => void;
  onUpdateFile: (fileId: string, payload: PlatformFileUpdate) => void;
  onDeleteFile: (fileId: string) => void;
}) {
  const PAGE_SIZE = 60;
  const [viewMode, setViewMode] = useState<"details" | "images">("details");
  const [searchQuery, setSearchQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState<"all" | PlatformFile["source"]>("all");
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const normalizedQuery = searchQuery.trim();
  const filesQuery = useInfiniteQuery({
    queryKey: ["files-dashboard", normalizedQuery.toLowerCase(), sourceFilter] as const,
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      api.filesPage({
        limit: PAGE_SIZE,
        offset: Number(pageParam),
        query: normalizedQuery || undefined,
        source: sourceFilter === "all" ? undefined : sourceFilter
      }),
    getNextPageParam: (lastPage, pages) =>
      lastPage.has_more ? pages.reduce((count, page) => count + page.items.length, 0) : undefined,
    staleTime: 10_000
  });

  const files = useMemo(() => filesQuery.data?.pages.flatMap((page) => page.items) ?? [], [filesQuery.data?.pages]);
  const totalFiles = filesQuery.data?.pages[0]?.total ?? files.length;
  const hasMore = filesQuery.hasNextPage;
  const isLoadingMore = filesQuery.isFetchingNextPage;
  const isLoadingFirstPage = filesQuery.isPending;

  useEffect(() => {
    const sentinel = loadMoreRef.current;
    if (!sentinel || !hasMore || isLoadingMore || isLoadingFirstPage) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        void filesQuery.fetchNextPage();
      },
      { root: null, rootMargin: "240px" }
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [filesQuery, hasMore, isLoadingFirstPage, isLoadingMore]);

  const indexedFileIds = new Set(
    documents.map((document) => (document.metadata?.file_id ? String(document.metadata.file_id) : "")).filter(Boolean)
  );
  const imageFiles = files.filter(isImagePlatformFile);
  const visibleFiles = viewMode === "images" ? imageFiles : files;

  return (
    <section className="scrollbar-slim min-w-0 flex-1 overflow-y-auto px-4 py-5">
      <div className="mx-auto flex max-w-6xl flex-col gap-4">
        <div className="flex flex-col justify-between gap-3 border-b border-forge-line pb-4 sm:flex-row sm:items-center">
          <div>
            <p className="text-xs uppercase text-forge-muted">Arquivos</p>
            <h3 className="text-xl font-semibold">Biblioteca da plataforma</h3>
          </div>
          <div className="flex flex-wrap gap-2">
            <div className="flex h-9 rounded-md border border-forge-line bg-[#0e0f0e] p-1">
              <button
                type="button"
                className={[
                  "flex items-center gap-2 rounded px-2 text-xs transition",
                  viewMode === "details" ? "bg-[#24211b] text-forge-text" : "text-forge-muted hover:text-forge-text"
                ].join(" ")}
                onClick={() => setViewMode("details")}
              >
                <List size={14} />
                Detalhes
              </button>
              <button
                type="button"
                className={[
                  "flex items-center gap-2 rounded px-2 text-xs transition",
                  viewMode === "images" ? "bg-[#24211b] text-forge-text" : "text-forge-muted hover:text-forge-text"
                ].join(" ")}
                onClick={() => setViewMode("images")}
              >
                <LayoutGrid size={14} />
                Imagens
              </button>
            </div>
            <label className="flex h-9 cursor-pointer items-center justify-center gap-2 rounded-md border border-forge-line bg-[#1a1d20] px-3 text-sm font-medium transition hover:bg-[#222a2f]">
              <FileText size={16} />
              <span>Enviar arquivos</span>
              <input
                type="file"
                multiple
                className="hidden"
                onChange={(event) => {
                  const selected = Array.from(event.target.files ?? []);
                  if (selected.length) onUploadFiles(selected);
                  event.target.value = "";
                }}
              />
            </label>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-md border border-forge-line bg-[#141615] p-3">
            <p className="text-xs uppercase text-forge-muted">Total</p>
            <p className="mt-1 text-2xl font-semibold">{totalFiles}</p>
          </div>
          <div className="rounded-md border border-forge-line bg-[#141615] p-3">
            <p className="flex items-center gap-2 text-xs uppercase text-forge-muted">
              <ImageIcon size={14} />
              Imagens
            </p>
            <p className="mt-1 text-2xl font-semibold">{imageFiles.length}</p>
          </div>
          <div className="rounded-md border border-forge-line bg-[#141615] p-3">
            <p className="text-xs uppercase text-forge-muted">Bases</p>
            <p className="mt-1 text-2xl font-semibold">{indexedFileIds.size}</p>
          </div>
        </div>

        <div className="grid gap-2 rounded-md border border-forge-line bg-[#141615] p-3 sm:grid-cols-[minmax(0,1fr)_200px]">
          <input
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder="Buscar arquivo por nome"
            className="h-9 w-full rounded-md border border-forge-line bg-[#0e0f0e] px-3 text-sm text-forge-text"
          />
          <select
            value={sourceFilter}
            onChange={(event) => setSourceFilter(event.target.value as "all" | PlatformFile["source"])}
            className="h-9 w-full rounded-md border border-forge-line bg-[#0e0f0e] px-2 text-sm text-forge-text"
          >
            <option value="all">Todas as origens</option>
            <option value="upload">upload</option>
            <option value="chat_attachment">chat_attachment</option>
            <option value="chatgpt_import">chatgpt_import</option>
            <option value="generated">generated</option>
            <option value="knowledge_base">knowledge_base</option>
          </select>
        </div>

        {viewMode === "images" ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {visibleFiles.map((platformFile) => {
              const isIndexed = indexedFileIds.has(platformFile.id);
              return (
                <div key={platformFile.id} className="overflow-hidden rounded-md border border-forge-line bg-[#141615]">
                  <a
                    href={fileContentUrl(platformFile.id)}
                    target="_blank"
                    rel="noreferrer"
                    className="block aspect-square bg-[#0e0f0e]"
                    title={platformFileLabel(platformFile)}
                  >
                    <img
                      src={fileContentUrl(platformFile.id)}
                      alt={platformFileLabel(platformFile)}
                      loading="lazy"
                      className="h-full w-full object-contain"
                    />
                  </a>
                  <div className="space-y-3 p-3">
                    <div className="min-w-0">
                      <h4 className="truncate text-sm font-semibold">{platformFileLabel(platformFile)}</h4>
                      <p className="mt-1 text-xs text-forge-muted">
                        {formatBytes(platformFile.size_bytes)} · {platformFile.content_type ?? "imagem"}
                      </p>
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <Badge>{isIndexed ? "em base" : platformFile.source}</Badge>
                      <Button
                        className="h-8 text-xs"
                        onClick={() => onCreateKnowledgeBaseFromFile(platformFile.id)}
                        disabled={isIndexed}
                      >
                        Usar como base
                      </Button>
                    </div>
                  </div>
                </div>
              );
            })}
            {!visibleFiles.length && !isLoadingFirstPage && <EmptyPanel text="Nenhuma imagem encontrada." />}
          </div>
        ) : (
          <div className="grid gap-3 lg:grid-cols-2">
            {visibleFiles.map((platformFile) => (
              <FileDetailCard
                key={platformFile.id}
                platformFile={platformFile}
                isIndexed={indexedFileIds.has(platformFile.id)}
                onCreateKnowledgeBaseFromFile={onCreateKnowledgeBaseFromFile}
                onUpdateFile={onUpdateFile}
                onDeleteFile={onDeleteFile}
              />
            ))}
            {!visibleFiles.length && !isLoadingFirstPage && <EmptyPanel text="Nenhum arquivo enviado ainda." />}
          </div>
        )}
        {isLoadingFirstPage && (
          <div className="rounded-md border border-forge-line bg-[#141615] px-3 py-2 text-sm text-forge-muted">
            <span className="inline-flex items-center gap-2">
              <LoaderCircle size={14} className="animate-spin" />
              Carregando arquivos...
            </span>
          </div>
        )}
        {!isLoadingFirstPage && (
          <div ref={loadMoreRef} className="flex min-h-8 items-center justify-center text-xs text-forge-muted">
            {isLoadingMore ? (
              <span className="inline-flex items-center gap-2">
                <LoaderCircle size={14} className="animate-spin" />
                Carregando mais...
              </span>
            ) : hasMore ? (
              "Role para carregar mais"
            ) : (
              "Fim da lista"
            )}
          </div>
        )}
      </div>
    </section>
  );
}

function FileDetailCard({
  platformFile,
  isIndexed,
  onCreateKnowledgeBaseFromFile,
  onUpdateFile,
  onDeleteFile
}: {
  platformFile: PlatformFile;
  isIndexed: boolean;
  onCreateKnowledgeBaseFromFile: (fileId: string) => void;
  onUpdateFile: (fileId: string, payload: PlatformFileUpdate) => void;
  onDeleteFile: (fileId: string) => void;
}) {
  const [filenameDraft, setFilenameDraft] = useState(platformFileLabel(platformFile));
  const [tagsDraft, setTagsDraft] = useState(platformFile.tags.join(", "));
  const [noteDraft, setNoteDraft] = useState(metadataValue(platformFile.metadata, "note"));
  const zipEntry = metadataValue(platformFile.metadata, "zip_entry");

  function save() {
    const metadata = { ...platformFile.metadata };
    if (noteDraft.trim()) {
      metadata.note = noteDraft.trim();
    } else {
      delete metadata.note;
    }
    onUpdateFile(platformFile.id, {
      filename: filenameDraft.trim() || platformFile.filename,
      tags: csvToList(tagsDraft),
      metadata
    });
  }

  return (
    <div className="rounded-md border border-forge-line bg-[#141615] p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h4 className="truncate text-sm font-semibold">{platformFileLabel(platformFile)}</h4>
          <p className="mt-1 text-xs text-forge-muted">
            {formatBytes(platformFile.size_bytes)} · {platformFile.content_type ?? "arquivo"}
          </p>
        </div>
        <Badge>{platformFile.source}</Badge>
      </div>

      {isImagePlatformFile(platformFile) && (
        <a
          href={fileContentUrl(platformFile.id)}
          target="_blank"
          rel="noreferrer"
          className="mt-3 block aspect-[16/9] overflow-hidden rounded border border-forge-line bg-[#0e0f0e]"
        >
          <img
            src={fileContentUrl(platformFile.id)}
            alt={platformFileLabel(platformFile)}
            loading="lazy"
            className="h-full w-full object-contain"
          />
        </a>
      )}

      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <Field label="Nome">
          <input
            value={filenameDraft}
            onChange={(event) => setFilenameDraft(event.target.value)}
            className="h-10 w-full rounded-md border border-forge-line bg-[#0e0f0e] px-3 text-sm text-forge-text"
          />
        </Field>
        <Field label="Tags">
          <input
            value={tagsDraft}
            onChange={(event) => setTagsDraft(event.target.value)}
            placeholder="import, imagem"
            className="h-10 w-full rounded-md border border-forge-line bg-[#0e0f0e] px-3 text-sm text-forge-text"
          />
        </Field>
      </div>

      <Field label="Nota">
        <textarea
          value={noteDraft}
          onChange={(event) => setNoteDraft(event.target.value)}
          rows={2}
          className="min-h-16 w-full resize-none rounded-md border border-forge-line bg-[#0e0f0e] px-3 py-2 text-sm text-forge-text"
        />
      </Field>

      <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-forge-muted">
        <InfoRow label="Status" value={isIndexed ? "em base" : "arquivo bruto"} />
        <InfoRow label="Duplicado" value={platformFile.duplicate_of_id ? "sim" : "não"} />
        {zipEntry && <InfoRow label="ZIP" value={zipEntry} />}
        {platformFile.checksum_sha256 && <InfoRow label="SHA-256" value={platformFile.checksum_sha256.slice(0, 12)} />}
      </div>

      <div className="mt-3 flex flex-wrap justify-end gap-2">
        <Button className="h-8 text-xs" onClick={() => window.open(fileContentUrl(platformFile.id), "_blank")}>
          <ExternalLink size={14} />
          Abrir
        </Button>
        <Button
          className="h-8 text-xs"
          onClick={() => onCreateKnowledgeBaseFromFile(platformFile.id)}
          disabled={isIndexed}
        >
          <Library size={14} />
          Usar como base
        </Button>
        <Button className="h-8 text-xs" onClick={save}>
          <Save size={14} />
          Salvar
        </Button>
        <Button
          className="h-8 text-xs text-forge-red"
          onClick={() => {
            if (window.confirm(`Remover ${platformFileLabel(platformFile)} da biblioteca?`)) {
              onDeleteFile(platformFile.id);
            }
          }}
        >
          <Trash2 size={14} />
          Excluir
        </Button>
      </div>
    </div>
  );
}

export function KnowledgeDashboard({
  knowledgeBases,
  knowledgeBaseDocuments,
  selectedKnowledgeBase,
  selectedDocuments,
  knowledgeBaseDraft,
  documentTitle,
  documentContent,
  documentTags,
  documentPinned,
  documentQuery,
  documentResults,
  chatGPTImportJob,
  chatGPTImportResult,
  isIndexingDocument,
  isImportingChatGPT,
  onSelectKnowledgeBase,
  onSetKnowledgeBaseDraft,
  onCreateKnowledgeBase,
  onSaveKnowledgeBase,
  onDeleteKnowledgeBase,
  onSetDocumentTitle,
  onSetDocumentContent,
  onSetDocumentTags,
  onSetDocumentPinned,
  onIndexTextDocument,
  onSetDocumentQuery,
  onSearchDocuments,
  onImportChatGPTExport,
  onUploadPlatformFiles,
  onCreateKnowledgeBaseFromFile,
  onRemoveDocumentFromKnowledgeBase,
  onUseDocument
}: {
  knowledgeBases: KnowledgeBase[];
  knowledgeBaseDocuments: KnowledgeBaseDocument[];
  selectedKnowledgeBase: KnowledgeBase | null;
  selectedDocuments: DocumentRecord[];
  knowledgeBaseDraft: KnowledgeBaseUpsert;
  documentTitle: string;
  documentContent: string;
  documentTags: string;
  documentPinned: boolean;
  documentQuery: string;
  documentResults: DocumentSearchResult[];
  chatGPTImportJob: ChatGPTImportJob | null;
  chatGPTImportResult: ChatGPTImportSummary | null;
  isIndexingDocument: boolean;
  isImportingChatGPT: boolean;
  onSelectKnowledgeBase: (knowledgeBase: KnowledgeBase) => void;
  onSetKnowledgeBaseDraft: Dispatch<SetStateAction<KnowledgeBaseUpsert>>;
  onCreateKnowledgeBase: () => void;
  onSaveKnowledgeBase: () => void;
  onDeleteKnowledgeBase: (knowledgeBase: KnowledgeBase) => void;
  onSetDocumentTitle: (value: string) => void;
  onSetDocumentContent: (value: string) => void;
  onSetDocumentTags: (value: string) => void;
  onSetDocumentPinned: (value: boolean) => void;
  onIndexTextDocument: () => void;
  onSetDocumentQuery: (value: string) => void;
  onSearchDocuments: () => void;
  onImportChatGPTExport: (file: File) => void;
  onUploadPlatformFiles: (files: File[]) => void;
  onCreateKnowledgeBaseFromFile: (fileId: string) => void;
  onRemoveDocumentFromKnowledgeBase: (documentId: string) => void;
  onUseDocument: (content: string) => void;
}) {
  const PAGE_SIZE = 60;
  const [kbFileSearch, setKbFileSearch] = useState("");
  const [kbSourceFilter, setKbSourceFilter] = useState<"all" | PlatformFile["source"]>("all");
  const knowledgeListRef = useRef<HTMLDivElement | null>(null);
  const knowledgeLoadMoreRef = useRef<HTMLDivElement | null>(null);
  const normalizedKbFileSearch = kbFileSearch.trim();
  const knowledgeFilesQuery = useInfiniteQuery({
    queryKey: ["knowledge-files", normalizedKbFileSearch.toLowerCase(), kbSourceFilter] as const,
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      api.filesPage({
        limit: PAGE_SIZE,
        offset: Number(pageParam),
        query: normalizedKbFileSearch || undefined,
        source: kbSourceFilter === "all" ? undefined : kbSourceFilter
      }),
    getNextPageParam: (lastPage, pages) =>
      lastPage.has_more ? pages.reduce((count, page) => count + page.items.length, 0) : undefined,
    staleTime: 10_000
  });

  const knowledgeFiles = useMemo(
    () =>
      (knowledgeFilesQuery.data?.pages.flatMap((page) => page.items) ?? []).filter(
        (platformFile) =>
          !(platformFile.source === "chatgpt_import" && isChatGPTInformationalFileName(platformFileLabel(platformFile)))
      ),
    [knowledgeFilesQuery.data?.pages]
  );
  const knowledgeHasMore = knowledgeFilesQuery.hasNextPage;
  const knowledgeLoadingMore = knowledgeFilesQuery.isFetchingNextPage;
  const knowledgeLoadingFirstPage = knowledgeFilesQuery.isPending;
  const knowledgeTotal = knowledgeFilesQuery.data?.pages[0]?.total ?? knowledgeFiles.length;

  useEffect(() => {
    const root = knowledgeListRef.current;
    const sentinel = knowledgeLoadMoreRef.current;
    if (!root || !sentinel || !knowledgeHasMore || knowledgeLoadingMore || knowledgeLoadingFirstPage) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        void knowledgeFilesQuery.fetchNextPage();
      },
      { root, rootMargin: "180px" }
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [knowledgeFilesQuery, knowledgeHasMore, knowledgeLoadingFirstPage, knowledgeLoadingMore]);

  const documentCountByBaseId = new Map<string, number>();
  for (const item of knowledgeBaseDocuments) {
    if (!item.enabled) continue;
    documentCountByBaseId.set(item.knowledge_base_id, (documentCountByBaseId.get(item.knowledge_base_id) ?? 0) + 1);
  }
  const orderedPlatformFiles = [...knowledgeFiles].sort((left, right) => {
    const leftTime = Date.parse(left.updated_at || left.created_at || "");
    const rightTime = Date.parse(right.updated_at || right.created_at || "");
    return (Number.isFinite(rightTime) ? rightTime : 0) - (Number.isFinite(leftTime) ? leftTime : 0);
  });
  const filteredKnowledgeFiles = orderedPlatformFiles;

  return (
    <section className="scrollbar-slim min-w-0 flex-1 overflow-y-auto px-4 py-5">
      <div className="mx-auto flex max-w-6xl flex-col gap-4">
        <div className="flex flex-col justify-between gap-3 border-b border-forge-line pb-4 sm:flex-row sm:items-center">
          <div>
            <p className="text-xs uppercase text-forge-muted">Bases</p>
            <h3 className="text-xl font-semibold">Coleções de contexto</h3>
          </div>
          <Badge>{knowledgeBases.length} bases</Badge>
        </div>

        <div className="grid gap-4 xl:grid-cols-[300px_minmax(0,1fr)]">
          <section className="space-y-3">
            <div className="rounded-md border border-forge-line bg-[#141615] p-3">
              <div className="flex items-center justify-between gap-2">
                <PanelTitle icon={<FolderTree size={18} />} title="Biblioteca de bases" />
                <Button className="h-8 text-xs" onClick={onCreateKnowledgeBase}>
                  <Plus size={14} />
                  Nova
                </Button>
              </div>
              <div className="mt-3 space-y-2">
                {knowledgeBases.map((knowledgeBase) => (
                  <button
                    key={knowledgeBase.id}
                    type="button"
                    className={[
                      "w-full rounded-md border p-3 text-left transition",
                      selectedKnowledgeBase?.id === knowledgeBase.id
                        ? "border-forge-amber/60 bg-[#24211b]"
                        : "border-forge-line bg-[#0e0f0e] hover:border-forge-amber/40"
                    ].join(" ")}
                    onClick={() => onSelectKnowledgeBase(knowledgeBase)}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="flex min-w-0 items-center gap-2 font-medium">
                        <span
                          className="h-3 w-3 shrink-0 rounded-sm"
                          style={{ backgroundColor: knowledgeBase.color }}
                        />
                        <span className="truncate">{knowledgeBase.name}</span>
                      </span>
                      <Badge>{documentCountByBaseId.get(knowledgeBase.id) ?? 0}</Badge>
                    </div>
                    <p className="mt-2 line-clamp-2 text-xs text-forge-muted">
                      {knowledgeBase.scope || knowledgeBase.description || "Sem escopo definido."}
                    </p>
                  </button>
                ))}
                {!knowledgeBases.length && <EmptyPanel text="Nenhuma base criada ainda." />}
              </div>
            </div>

            <div className="rounded-md border border-forge-line bg-[#141615] p-3">
              <PanelTitle icon={<FileText size={18} />} title="Importar ChatGPT" />
              <p className="mt-3 text-xs leading-5 text-forge-muted">
                Importe conversations.json ou ZIP exportado, até 5 GB. O histórico fica local.
              </p>
              <label className="mt-3 flex h-10 cursor-pointer items-center justify-center gap-2 rounded-md border border-forge-line bg-[#1a1d20] px-3 text-sm font-medium transition hover:bg-[#222a2f]">
                {isImportingChatGPT ? <LoaderCircle size={16} className="animate-spin" /> : <FileText size={16} />}
                <span>{isImportingChatGPT ? "Importando" : "Selecionar export"}</span>
                <input
                  type="file"
                  accept=".json,.zip,application/json,application/zip"
                  className="hidden"
                  disabled={isImportingChatGPT}
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) onImportChatGPTExport(file);
                    event.target.value = "";
                  }}
                />
              </label>
              {chatGPTImportJob && (
                <div className="mt-3 rounded-md border border-forge-line bg-[#0e0f0e] p-2 text-xs">
                  <div className="flex items-center justify-between gap-3">
                    <p className="min-w-0 truncate font-medium">{chatGPTImportJob.source_filename}</p>
                    <Badge>{chatGPTImportJob.status}</Badge>
                  </div>
                  <div className="mt-2 h-2 overflow-hidden rounded bg-[#1a1d20]">
                    <div
                      className="h-full bg-forge-amber transition-all"
                      style={{ width: `${Math.max(2, chatGPTImportJob.progress_percent)}%` }}
                    />
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-forge-muted">
                    <InfoRow label="Progresso" value={`${chatGPTImportJob.progress_percent.toFixed(1)}%`} />
                    <InfoRow label="Tamanho" value={formatBytes(chatGPTImportJob.file_size_bytes)} />
                  </div>
                  <p className="mt-2 line-clamp-2 text-forge-muted">{chatGPTImportJob.current_step}</p>
                  {chatGPTImportJob.error && (
                    <p className="mt-2 line-clamp-3 text-forge-red">{chatGPTImportJob.error}</p>
                  )}
                </div>
              )}
              {chatGPTImportResult && (
                <div className="mt-3 rounded-md border border-forge-line bg-[#0e0f0e] p-2 text-xs">
                  <p className="truncate font-medium">{chatGPTImportResult.source_filename}</p>
                  <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-forge-muted">
                    <InfoRow label="Conversas" value={String(chatGPTImportResult.conversations_found)} />
                    <InfoRow label="Sessões" value={String(chatGPTImportResult.sessions_imported)} />
                    <InfoRow label="Mensagens" value={String(chatGPTImportResult.messages_imported)} />
                    <InfoRow label="Duplicadas" value={String(chatGPTImportResult.messages_skipped)} />
                  </div>
                  {chatGPTImportResult.errors.length > 0 && (
                    <p className="mt-2 line-clamp-3 text-forge-red">{chatGPTImportResult.errors[0]}</p>
                  )}
                </div>
              )}
            </div>

            <div className="rounded-md border border-forge-line bg-[#141615] p-3">
              <PanelTitle icon={<FileText size={18} />} title="Adicionar de arquivos" />
              <p className="mt-3 text-xs leading-5 text-forge-muted">
                Bases são contextos indexados. Arquivos enviados ficam na biblioteca até você escolher usar como base.
              </p>
              <label className="mt-3 flex h-10 cursor-pointer items-center justify-center gap-2 rounded-md border border-forge-line bg-[#1a1d20] px-3 text-sm font-medium transition hover:bg-[#222a2f]">
                <FileText size={16} />
                <span>Pegar do computador</span>
                <input
                  type="file"
                  multiple
                  className="hidden"
                  onChange={(event) => {
                    const files = Array.from(event.target.files ?? []);
                    if (files.length) onUploadPlatformFiles(files);
                    event.target.value = "";
                  }}
                />
              </label>
              <div className="mt-3 grid gap-2">
                <input
                  value={kbFileSearch}
                  onChange={(event) => setKbFileSearch(event.target.value)}
                  placeholder="Buscar arquivo por nome"
                  className="h-9 w-full rounded-md border border-forge-line bg-[#0e0f0e] px-3 text-sm text-forge-text"
                />
                <select
                  value={kbSourceFilter}
                  onChange={(event) => setKbSourceFilter(event.target.value as "all" | PlatformFile["source"])}
                  className="h-9 w-full rounded-md border border-forge-line bg-[#0e0f0e] px-2 text-sm text-forge-text"
                >
                  <option value="all">Todas as origens</option>
                  <option value="upload">upload</option>
                  <option value="chat_attachment">chat_attachment</option>
                  <option value="chatgpt_import">chatgpt_import</option>
                  <option value="generated">generated</option>
                  <option value="knowledge_base">knowledge_base</option>
                </select>
              </div>
              <div ref={knowledgeListRef} className="scrollbar-slim mt-3 max-h-80 space-y-2 overflow-y-auto pr-1">
                {filteredKnowledgeFiles.map((platformFile) => (
                  <div key={platformFile.id} className="rounded-md border border-forge-line bg-[#0e0f0e] p-2 text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <span className="min-w-0 truncate font-medium">{platformFileLabel(platformFile)}</span>
                      <Badge>{platformFile.source}</Badge>
                    </div>
                    <div className="mt-2 flex items-center justify-between gap-2 text-forge-muted">
                      <span>{formatBytes(platformFile.size_bytes)}</span>
                      <Button className="h-7 text-xs" onClick={() => onCreateKnowledgeBaseFromFile(platformFile.id)}>
                        Adicionar na base
                      </Button>
                    </div>
                  </div>
                ))}
                {!filteredKnowledgeFiles.length && !knowledgeLoadingFirstPage && (
                  <EmptyPanel text="Nenhum arquivo encontrado." />
                )}
                {knowledgeLoadingFirstPage && (
                  <p className="text-center text-xs text-forge-muted">
                    <span className="inline-flex items-center gap-2">
                      <LoaderCircle size={14} className="animate-spin" />
                      Carregando arquivos...
                    </span>
                  </p>
                )}
                <div ref={knowledgeLoadMoreRef} className="py-1 text-center text-[11px] text-forge-muted">
                  {knowledgeLoadingMore ? (
                    <span className="inline-flex items-center gap-2">
                      <LoaderCircle size={14} className="animate-spin" />
                      Carregando mais...
                    </span>
                  ) : knowledgeHasMore ? (
                    "Role para carregar mais"
                  ) : (
                    `Fim da lista (${knowledgeTotal})`
                  )}
                </div>
              </div>
            </div>
          </section>

          <section className="space-y-4">
            <div className="rounded-md border border-forge-line bg-[#141615] p-4">
              <div className="flex items-center justify-between gap-2 border-b border-forge-line pb-2">
                <PanelTitle icon={<Library size={18} />} title={selectedKnowledgeBase?.name || "Nova base"} />
                {selectedKnowledgeBase && (
                  <Button
                    className="h-8 text-xs text-forge-red"
                    onClick={() => onDeleteKnowledgeBase(selectedKnowledgeBase)}
                  >
                    <Trash2 size={14} />
                    Excluir base
                  </Button>
                )}
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <Field label="Nome">
                  <input
                    value={knowledgeBaseDraft.name}
                    onChange={(event) =>
                      onSetKnowledgeBaseDraft((current) => ({ ...current, name: event.target.value }))
                    }
                    placeholder="Ex: Produto, Marca, Pesquisa"
                    className="h-10 w-full rounded-md border border-forge-line bg-[#0e0f0e] px-3 text-sm text-forge-text"
                  />
                </Field>
                <Field label="Cor">
                  <input
                    type="color"
                    value={knowledgeBaseDraft.color}
                    onChange={(event) =>
                      onSetKnowledgeBaseDraft((current) => ({ ...current, color: event.target.value }))
                    }
                    className="h-10 w-full rounded-md border border-forge-line bg-[#0e0f0e] p-1"
                    aria-label="Cor da base"
                    title="Cor da base"
                  />
                </Field>
              </div>
              <Field label="Escopo" className="mt-3">
                <textarea
                  value={knowledgeBaseDraft.scope}
                  onChange={(event) =>
                    onSetKnowledgeBaseDraft((current) => ({ ...current, scope: event.target.value }))
                  }
                  rows={3}
                  placeholder="Explique quando esta base deve ser usada e quais assuntos ela cobre."
                  className="min-h-20 w-full resize-none rounded-md border border-forge-line bg-[#0e0f0e] px-3 py-2 text-sm text-forge-text"
                />
              </Field>
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                <Field label="Tags">
                  <input
                    value={knowledgeBaseDraft.tags.join(", ")}
                    onChange={(event) =>
                      onSetKnowledgeBaseDraft((current) => ({ ...current, tags: csvToList(event.target.value) }))
                    }
                    placeholder="produto, suporte"
                    className="h-10 w-full rounded-md border border-forge-line bg-[#0e0f0e] px-3 text-sm text-forge-text"
                  />
                </Field>
                <Field label="Docs por busca">
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={knowledgeBaseDraft.max_documents_per_query}
                    onChange={(event) =>
                      onSetKnowledgeBaseDraft((current) => ({
                        ...current,
                        max_documents_per_query: Math.max(1, Math.min(20, Number(event.target.value) || 1))
                      }))
                    }
                    className="h-10 w-full rounded-md border border-forge-line bg-[#0e0f0e] px-3 text-sm text-forge-text"
                  />
                </Field>
                <Field label="Chunks por doc">
                  <input
                    type="number"
                    min={1}
                    max={10}
                    value={knowledgeBaseDraft.max_chunks_per_document}
                    onChange={(event) =>
                      onSetKnowledgeBaseDraft((current) => ({
                        ...current,
                        max_chunks_per_document: Math.max(1, Math.min(10, Number(event.target.value) || 1))
                      }))
                    }
                    className="h-10 w-full rounded-md border border-forge-line bg-[#0e0f0e] px-3 text-sm text-forge-text"
                  />
                </Field>
              </div>
              <div className="mt-3 flex items-center justify-between gap-3">
                <label className="flex items-center gap-2 text-sm text-forge-muted">
                  <input
                    type="checkbox"
                    checked={knowledgeBaseDraft.enabled}
                    onChange={(event) =>
                      onSetKnowledgeBaseDraft((current) => ({ ...current, enabled: event.target.checked }))
                    }
                  />
                  base habilitada
                </label>
                <Button className="h-9 border-forge-amber/60 bg-[#24211b]" onClick={onSaveKnowledgeBase}>
                  <Save size={16} />
                  Salvar base
                </Button>
              </div>
            </div>

            <div className="rounded-md border border-forge-line bg-[#141615] p-4">
              <PanelTitle icon={<FileText size={18} />} title="Criar contexto textual" />
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <Field label="Título">
                  <input
                    value={documentTitle}
                    onChange={(event) => onSetDocumentTitle(event.target.value)}
                    placeholder="Nome do contexto"
                    className="h-10 w-full rounded-md border border-forge-line bg-[#0e0f0e] px-3 text-sm text-forge-text"
                  />
                </Field>
                <Field label="Tags">
                  <input
                    value={documentTags}
                    onChange={(event) => onSetDocumentTags(event.target.value)}
                    placeholder="produto, arquitetura"
                    className="h-10 w-full rounded-md border border-forge-line bg-[#0e0f0e] px-3 text-sm text-forge-text"
                  />
                </Field>
              </div>
              <Field label="Conteúdo principal" className="mt-3">
                <textarea
                  value={documentContent}
                  onChange={(event) => onSetDocumentContent(event.target.value)}
                  rows={7}
                  placeholder="Cole texto, Markdown, CSV ou HTML"
                  className="min-h-40 w-full resize-y rounded-md border border-forge-line bg-[#0e0f0e] px-3 py-2 text-sm leading-6 text-forge-text"
                />
              </Field>
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <label className="flex items-center gap-2 text-sm text-forge-muted">
                  <input
                    type="checkbox"
                    checked={documentPinned}
                    onChange={(event) => onSetDocumentPinned(event.target.checked)}
                  />
                  contexto principal
                </label>
                <Button
                  className="h-9"
                  onClick={onIndexTextDocument}
                  disabled={!documentContent.trim() || isIndexingDocument}
                >
                  Indexar bloco
                </Button>
              </div>
            </div>

            <div className="rounded-md border border-forge-line bg-[#141615] p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <PanelTitle icon={<SearchIcon />} title="Busca na base" />
                <div className="flex min-w-0 gap-2">
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
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {documentResults.map((result) => (
                  <button
                    key={`${result.document_id}:${String(result.metadata.chunk_index ?? "0")}`}
                    className="rounded-md border border-forge-line bg-[#0e0f0e] p-3 text-left text-sm transition hover:border-forge-amber/60"
                    onClick={() => onUseDocument(result.content)}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{result.title}</span>
                      <Badge>{result.score.toFixed(2)}</Badge>
                    </div>
                    <p className="mt-2 line-clamp-3 text-xs text-forge-muted">{result.content}</p>
                  </button>
                ))}
                {!documentResults.length && <EmptyPanel text="Nenhum resultado buscado ainda." />}
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              {selectedDocuments.map((document) => (
                <div key={document.id} className="rounded-md border border-forge-line bg-[#141615] p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h4 className="truncate text-sm font-semibold">{document.title}</h4>
                      <p className="mt-1 text-xs text-forge-muted">
                        {document.source_type} / {document.index_status}
                      </p>
                    </div>
                    {document.pinned && <Badge>principal</Badge>}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {document.tags.map((tag) => (
                      <Badge key={tag}>{tag}</Badge>
                    ))}
                    {!document.tags.length && <Badge>sem tags</Badge>}
                  </div>
                  <div className="mt-3 flex justify-end">
                    <Button
                      className="h-8 text-xs text-forge-red"
                      onClick={() => onRemoveDocumentFromKnowledgeBase(document.id)}
                    >
                      <Trash2 size={14} />
                      Remover da base
                    </Button>
                  </div>
                </div>
              ))}
              {!selectedDocuments.length && <EmptyPanel text="Ainda não há documentos nesta base." />}
            </div>
          </section>
        </div>
      </div>
    </section>
  );
}
