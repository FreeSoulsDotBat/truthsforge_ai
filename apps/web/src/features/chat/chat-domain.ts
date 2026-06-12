import type { StreamStatusEvent } from "../../lib/api";
import type { ChatMessage, ChatModeling3DContext, ChatModelingStage, ChatSession } from "../../types/api";
import type { ModelingPlan, ModelingPlanStatus } from "../modeling-3d/types";

export const DEFAULT_CHAT_TITLES = ["novo chat", "new chat"] as const;

export function normalizeRequiredChatTitle(value: string | null | undefined): string {
  return (value ?? "").trim();
}

export function isDefaultChatTitle(value: string | null | undefined): boolean {
  const normalized = normalizeRequiredChatTitle(value).toLowerCase();
  return !normalized || DEFAULT_CHAT_TITLES.includes(normalized as (typeof DEFAULT_CHAT_TITLES)[number]);
}

export function chatSessionNeedsTitle(session: ChatSession | null): boolean {
  if (!session) return true;
  return isDefaultChatTitle(session.title);
}

export type ChatMessageMetadata = {
  runtime_status?: StreamStatusEvent;
  runtime_statuses?: StreamStatusEvent[];
  reasoning_summary?: string;
  reasoning_summary_enabled?: boolean;
  attached_file_ids?: string[];
  attached_document_ids?: string[];
  attached_files?: ChatMessageAttachment[];
  response_mode?: "modeling_3d" | string;
  modeling_plan_id?: string;
  modeling_plan?: ModelingPlan;
};

export type ChatMessageAttachment = {
  id?: string;
  file_id?: string;
  filename?: string;
  original_filename?: string;
  content_type?: string | null;
  size_bytes?: number;
  url?: string;
};

export const initialAssistantStatus = ({
  reasoningOverride,
  deepResearch,
  responseMode,
  multiAgentMode,
  reasoningSummary,
  modeling3dEnabled
}: {
  reasoningOverride: "default" | "long";
  deepResearch: boolean;
  responseMode: "text" | "image";
  multiAgentMode: boolean;
  reasoningSummary: boolean;
  modeling3dEnabled?: boolean;
}): StreamStatusEvent => {
  if (modeling3dEnabled) {
    return { stage: "modeling_3d", label: "Planejando 3D", detail: "Preparando MCP local." };
  }
  if (deepResearch) {
    return { stage: "deep_research", label: "Preparando pesquisa", detail: "Validando custos e fontes." };
  }
  if (responseMode === "image") {
    return { stage: "image", label: "Preparando imagem", detail: "Organizando briefing visual." };
  }
  if (multiAgentMode) {
    return { stage: "multi_agent", label: "Coordenando agentes", detail: "Montando colaboração." };
  }
  if (reasoningOverride === "long") {
    return { stage: "reasoning", label: "Raciocínio longo", detail: "Aumentando cuidado antes da resposta." };
  }
  if (reasoningSummary) {
    return {
      stage: "reasoning_summary",
      label: "Resumo oficial ativado",
      detail: "Aguardando resumo autorizado do provedor."
    };
  }
  return { stage: "thinking", label: "JUDITE pensando", detail: "Preparando resposta." };
};

export const localAssistantMessage = (
  sessionId: string,
  runtimeStatus: StreamStatusEvent,
  reasoningSummaryEnabled = false
): ChatMessage => ({
  id: `local_${Date.now()}`,
  session_id: sessionId,
  role: "assistant",
  content: "",
  metadata: {
    runtime_status: runtimeStatus,
    runtime_statuses: [runtimeStatus],
    reasoning_summary_enabled: reasoningSummaryEnabled
  },
  created_at: new Date().toISOString()
});

export function messageMetadata(message: ChatMessage): ChatMessageMetadata {
  return (message.metadata ?? {}) as ChatMessageMetadata;
}

export function withRuntimeStatus(message: ChatMessage, status: StreamStatusEvent): ChatMessage {
  const metadata = messageMetadata(message);
  const statuses = metadata.runtime_statuses ?? [];
  const lastStatus = statuses[statuses.length - 1];
  const shouldAppend = lastStatus?.stage !== status.stage;
  return {
    ...message,
    metadata: {
      ...(message.metadata ?? {}),
      runtime_status: status,
      runtime_statuses: shouldAppend ? [...statuses, status] : statuses
    }
  };
}

export function withReasoningSummary(message: ChatMessage, chunk: string): ChatMessage {
  const metadata = messageMetadata(message);
  return {
    ...message,
    metadata: {
      ...(message.metadata ?? {}),
      reasoning_summary: `${metadata.reasoning_summary ?? ""}${chunk}`,
      reasoning_summary_enabled: true
    }
  };
}

export function withModelingPlan(message: ChatMessage, plan: ModelingPlan): ChatMessage {
  // RF-024: o trace_id historicamente só chegava via SSE; payloads REST
  // (approve/execute/getPlan) podiam vir sem ele e apagar o valor já
  // conhecido — o modal de diagnóstico virava no-op após a primeira ação do
  // card. Mesmo com o backend serializando trace_id no REST, preserva o
  // existente como fallback defensivo.
  const previousPlan = messageMetadata(message).modeling_plan;
  const nextPlan =
    plan.trace_id == null && previousPlan?.id === plan.id && previousPlan.trace_id != null
      ? { ...plan, trace_id: previousPlan.trace_id }
      : plan;
  return {
    ...message,
    metadata: {
      ...(message.metadata ?? {}),
      response_mode: "modeling_3d",
      modeling_plan: nextPlan,
      modeling_plan_id: nextPlan.id
    }
  };
}

// Fonte única do mapeamento status do plano → estágio da sessão de chat.
// Usada tanto pelo handler SSE `modeling_plan` quanto pelo reconcile pós-409
// (anti-replay C5) — mantê-los divergentes fazia um 409 com plano `running`
// regredir a UI para a etapa de aprovação durante a execução.
export function modelingStageForPlanStatus(status: ModelingPlanStatus): ChatModelingStage {
  switch (status) {
    case "completed":
      return "editing";
    case "failed":
      return "failed";
    case "rejected":
      return "discovery";
    case "draft":
    case "waiting_approval":
      return "planning";
    case "approved":
    case "running":
      return "executing";
  }
}

export function normalizeStreamExecutionModes({
  reasoningOverride,
  deepResearch,
  responseMode,
  reasoningSummary,
  multiAgentMode,
  modeling3d
}: {
  reasoningOverride: "default" | "long";
  deepResearch: boolean;
  responseMode: "text" | "image";
  reasoningSummary: boolean;
  multiAgentMode: boolean;
  modeling3d: ChatModeling3DContext;
}) {
  if (!modeling3d.enabled) {
    return {
      reasoningOverride,
      deepResearch,
      responseMode,
      reasoningSummary,
      multiAgentMode,
      imageModelEnabled: responseMode === "image",
      modeling3dEnabled: false
    };
  }

  return {
    reasoningOverride: "default" as const,
    deepResearch: false,
    responseMode: "text" as const,
    reasoningSummary: false,
    multiAgentMode: false,
    imageModelEnabled: false,
    modeling3dEnabled: true
  };
}
