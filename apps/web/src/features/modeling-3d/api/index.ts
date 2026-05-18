import { apiRequest } from "../../../lib/api";
import type {
  ChatAttachmentAnalyzeResponse,
  ModelingCapabilities,
  ModelingModelVersion,
  ModelingPlan,
  ModelingPrintabilityReport,
  ModelingSession,
  ModelingSnapshot,
  ModelingSoftware,
  ModelingToolCall
} from "../../../types/api";

function queryString(params: Record<string, string | number | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== "") search.set(key, String(value));
  }
  const suffix = search.toString();
  return suffix ? `?${suffix}` : "";
}

export const modeling3dApi = {
  capabilities: () => apiRequest<ModelingCapabilities>("/api/3d/capabilities"),
  sessions: () => apiRequest<ModelingSession[]>("/api/3d/sessions"),
  plans: () => apiRequest<ModelingPlan[]>("/api/3d/plans"),
  snapshots: (params: { plan_id?: string; project_id?: string } = {}) =>
    apiRequest<ModelingSnapshot[]>(`/api/3d/snapshots${queryString(params)}`),
  toolCalls: (params: { plan_id?: string; step_id?: string; limit?: number } = {}) =>
    apiRequest<ModelingToolCall[]>(`/api/3d/tool-calls${queryString(params)}`),
  printabilityReports: (params: { plan_id?: string; file_id?: string } = {}) =>
    apiRequest<ModelingPrintabilityReport[]>(`/api/3d/printability-reports${queryString(params)}`),
  modelVersions: (params: { project_id?: string } = {}) =>
    apiRequest<ModelingModelVersion[]>(`/api/3d/model-versions${queryString(params)}`),
  analyzeAttachment: (chatId: string, fileId: string) =>
    apiRequest<ChatAttachmentAnalyzeResponse>(`/api/chat/sessions/${chatId}/attachments/analyze`, {
      method: "POST",
      body: JSON.stringify({ file_id: fileId })
    })
};

export function toModeling3DContext(enabled: boolean, software: ModelingSoftware) {
  return {
    enabled,
    mode: "safe_auto" as const,
    software_override: software === "auto" ? null : software
  };
}
