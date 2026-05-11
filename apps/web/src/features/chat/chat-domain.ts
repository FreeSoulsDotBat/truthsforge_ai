import type { StreamStatusEvent } from "../../lib/api";
import type { ChatMessage } from "../../types/api";

export type ChatMessageMetadata = {
  runtime_status?: StreamStatusEvent;
  runtime_statuses?: StreamStatusEvent[];
  reasoning_summary?: string;
  reasoning_summary_enabled?: boolean;
  attached_file_ids?: string[];
  attached_document_ids?: string[];
  attached_files?: ChatMessageAttachment[];
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
  reasoningSummary
}: {
  reasoningOverride: "default" | "long";
  deepResearch: boolean;
  responseMode: "text" | "image";
  multiAgentMode: boolean;
  reasoningSummary: boolean;
}): StreamStatusEvent => {
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
