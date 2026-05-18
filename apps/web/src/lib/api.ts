import type {
  Agent,
  AgentUpsert,
  AuditEvent,
  ChatModeling3DContext,
  ChatGPTImportJob,
  ChatSession,
  ChatSessionContextUpdate,
  ChatSessionDeleteResult,
  ChatSessionMoveRequest,
  CostPolicy,
  CostUsage,
  DocumentPage,
  DocumentFromFileCreate,
  DocumentRecord,
  DocumentSearchRequest,
  DocumentSearchResult,
  DocumentTextCreate,
  KnowledgeBase,
  KnowledgeBaseDocument,
  KnowledgeBaseDocumentUpsert,
  KnowledgeBaseUpsert,
  ModelConfig,
  ModelUpsert,
  PlatformFile,
  PlatformFileIndexingStatus,
  PlatformFilePage,
  PlatformFileUpdate,
  ProjectFolder,
  ProjectFolderCreate,
  ProjectFolderDeleteResult,
  ProjectRecord,
  ProjectUpsert,
  ProviderModel,
  ProviderName,
  ProviderSecretStatus,
  Prompt,
  ServerStatus
} from "../types/api";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    ...init
  });
  if (!response.ok) {
    const detail = await response
      .json()
      .then((payload) => payload.detail as string | undefined)
      .catch(() => undefined);
    throw new Error(detail ?? `API ${path} returned ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  return apiRequest<T>(path, init);
}

export async function multipartRequest<T>(path: string, body: FormData): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    body
  });
  if (!response.ok) {
    const detail = await response
      .json()
      .then((payload) => payload.detail as string | undefined)
      .catch(() => undefined);
    throw new Error(detail ?? `API ${path} returned ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  baseUrl: API_BASE_URL,
  status: () => request<ServerStatus>("/api/server/status"),
  sessions: (includeMessages = false) =>
    request<ChatSession[]>(`/api/chat/sessions?include_messages=${includeMessages ? "true" : "false"}`),
  createSession: (payload?: {
    title?: string;
    model_id?: string | null;
    agent_id?: string | null;
    project_id?: string | null;
    folder_id?: string | null;
    context_project_ids?: string[];
    context_document_ids?: string[];
    context_knowledge_base_ids?: string[];
    is_modeling_3d?: boolean;
    modeling_software_preference?: "auto" | "blender" | "fusion" | null;
  }) =>
    request<ChatSession>("/api/chat/sessions", {
      method: "POST",
      body: JSON.stringify(payload ?? {})
    }),
  deleteSession: (sessionId: string, deleteFiles = true) =>
    request<ChatSessionDeleteResult>(`/api/chat/sessions/${sessionId}?delete_files=${deleteFiles ? "true" : "false"}`, {
      method: "DELETE"
    }),
  moveSession: (sessionId: string, payload: ChatSessionMoveRequest) =>
    request<ChatSession>(`/api/chat/sessions/${sessionId}/move`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  updateSessionContext: (sessionId: string, payload: ChatSessionContextUpdate) =>
    request<ChatSession>(`/api/chat/sessions/${sessionId}/context`, {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  session: (sessionId: string, messageLimit?: number, messageOffset?: number) => {
    const params = new URLSearchParams();
    if (messageLimit !== undefined) params.set("message_limit", String(messageLimit));
    if (messageOffset !== undefined) params.set("message_offset", String(messageOffset));
    const query = params.toString();
    return request<ChatSession>(`/api/chat/sessions/${sessionId}${query ? `?${query}` : ""}`);
  },
  models: () => request<ModelConfig[]>("/api/models"),
  providerModels: (provider: ProviderName) => request<ProviderModel[]>(`/api/models/providers/${provider}`),
  saveModel: (model: ModelUpsert) =>
    request<ModelConfig>("/api/models", {
      method: "POST",
      body: JSON.stringify(model)
    }),
  agents: () => request<Agent[]>("/api/agents"),
  createAgent: (agent: AgentUpsert) =>
    request<Agent>("/api/agents", {
      method: "POST",
      body: JSON.stringify(agent)
    }),
  updateAgent: (agentId: string, agent: AgentUpsert) =>
    request<Agent>(`/api/agents/${agentId}`, {
      method: "PUT",
      body: JSON.stringify(agent)
    }),
  projects: () => request<ProjectRecord[]>("/api/projects"),
  createProject: (payload: ProjectUpsert) =>
    request<ProjectRecord>("/api/projects", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  updateProject: (projectId: string, payload: ProjectUpsert) =>
    request<ProjectRecord>(`/api/projects/${projectId}`, {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  projectFolders: (projectId?: string) =>
    request<ProjectFolder[]>(`/api/projects/folders${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ""}`),
  createProjectFolder: (payload: ProjectFolderCreate) =>
    request<ProjectFolder>("/api/projects/folders", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  deleteProjectFolder: (folderId: string) =>
    request<ProjectFolderDeleteResult>(`/api/projects/folders/${folderId}`, {
      method: "DELETE"
    }),
  updateProjectFolder: (folderId: string, name: string) =>
    request<ProjectFolder>(`/api/projects/folders/${folderId}`, {
      method: "PUT",
      body: JSON.stringify({ name })
    }),
  prompts: () => request<Prompt[]>("/api/prompts"),
  knowledgeBases: () => request<KnowledgeBase[]>("/api/knowledge-bases"),
  createKnowledgeBase: (payload: KnowledgeBaseUpsert) =>
    request<KnowledgeBase>("/api/knowledge-bases", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  updateKnowledgeBase: (knowledgeBaseId: string, payload: KnowledgeBaseUpsert) =>
    request<KnowledgeBase>(`/api/knowledge-bases/${knowledgeBaseId}`, {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  deleteKnowledgeBase: (knowledgeBaseId: string) =>
    request<KnowledgeBase>(`/api/knowledge-bases/${knowledgeBaseId}`, {
      method: "DELETE"
    }),
  knowledgeBaseDocuments: (knowledgeBaseId: string) =>
    request<KnowledgeBaseDocument[]>(`/api/knowledge-bases/${knowledgeBaseId}/documents`),
  knowledgeBaseDocumentsAll: () => request<KnowledgeBaseDocument[]>("/api/knowledge-bases/documents"),
  addKnowledgeBaseDocument: (knowledgeBaseId: string, payload: KnowledgeBaseDocumentUpsert) =>
    request<KnowledgeBaseDocument>(`/api/knowledge-bases/${knowledgeBaseId}/documents`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  removeKnowledgeBaseDocument: (knowledgeBaseId: string, documentId: string) =>
    request<KnowledgeBaseDocument>(`/api/knowledge-bases/${knowledgeBaseId}/documents/${documentId}`, {
      method: "DELETE"
    }),
  documents: () => request<DocumentRecord[]>("/api/documents"),
  documentsByIds: (ids: string[]) =>
    request<DocumentRecord[]>("/api/documents/batch", {
      method: "POST",
      body: JSON.stringify({ ids })
    }),
  documentsPage: (params?: {
    limit?: number;
    offset?: number;
    query?: string;
    project_id?: string;
    folder_id?: string;
    source_type?: string;
    indexed?: boolean;
  }) => {
    const search = new URLSearchParams();
    if (params?.limit !== undefined) search.set("limit", String(params.limit));
    if (params?.offset !== undefined) search.set("offset", String(params.offset));
    if (params?.query) search.set("query", params.query);
    if (params?.project_id) search.set("project_id", params.project_id);
    if (params?.folder_id) search.set("folder_id", params.folder_id);
    if (params?.source_type) search.set("source_type", params.source_type);
    if (params?.indexed !== undefined) search.set("indexed", String(params.indexed));
    const query = search.toString();
    return request<DocumentPage>(`/api/documents/page${query ? `?${query}` : ""}`);
  },
  files: () => request<PlatformFile[]>("/api/files"),
  fileIndexingStatus: () => request<PlatformFileIndexingStatus>("/api/files/indexing/status"),
  filesPage: (params?: {
    limit?: number;
    offset?: number;
    source?: PlatformFile["source"];
    query?: string;
    project_id?: string;
    folder_id?: string;
  }) => {
    const search = new URLSearchParams();
    if (params?.limit !== undefined) search.set("limit", String(params.limit));
    if (params?.offset !== undefined) search.set("offset", String(params.offset));
    if (params?.source) search.set("source", params.source);
    if (params?.query) search.set("query", params.query);
    if (params?.project_id) search.set("project_id", params.project_id);
    if (params?.folder_id) search.set("folder_id", params.folder_id);
    const query = search.toString();
    return request<PlatformFilePage>(`/api/files/page${query ? `?${query}` : ""}`);
  },
  uploadFile: (
    file: File,
    source: PlatformFile["source"] = "upload",
    options?: { project_id?: string | null; folder_id?: string | null; session_id?: string | null }
  ) => {
    const body = new FormData();
    body.append("file", file);
    const params = new URLSearchParams({ source });
    if (options?.project_id) params.set("project_id", options.project_id);
    if (options?.folder_id) params.set("folder_id", options.folder_id);
    if (options?.session_id) params.set("session_id", options.session_id);
    return multipartRequest<PlatformFile>(`/api/files/upload?${params.toString()}`, body);
  },
  updateFile: (fileId: string, payload: PlatformFileUpdate) =>
    request<PlatformFile>(`/api/files/${fileId}`, {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  deleteFile: (fileId: string) =>
    request<PlatformFile>(`/api/files/${fileId}`, {
      method: "DELETE"
    }),
  createTextDocument: (payload: DocumentTextCreate) =>
    request<DocumentRecord>("/api/documents/text", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  createDocumentFromFile: (payload: DocumentFromFileCreate) =>
    request<DocumentRecord>("/api/documents/from-file", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  searchDocuments: (payload: DocumentSearchRequest) =>
    request<DocumentSearchResult[]>("/api/documents/search", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  auditEvents: () => request<AuditEvent[]>("/api/audit/events"),
  costPolicy: () => request<CostPolicy>("/api/cost/policy"),
  costUsage: () => request<CostUsage>("/api/cost/usage"),
  providerStatuses: () => request<ProviderSecretStatus[]>("/api/settings/providers"),
  importChatGPTExport: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return multipartRequest<ChatGPTImportJob>("/api/imports/chatgpt", body);
  },
  importChatGPTExistingFile: (fileId: string) =>
    request<ChatGPTImportJob>(`/api/imports/chatgpt/from-file/${fileId}`, {
      method: "POST"
    }),
  chatGPTImportJob: (jobId: string) => request<ChatGPTImportJob>(`/api/imports/chatgpt/jobs/${jobId}`),
  chatGPTImportJobs: () => request<ChatGPTImportJob[]>("/api/imports/chatgpt/jobs"),
  saveProviderKey: (provider: ProviderName, apiKey: string) =>
    request<ProviderSecretStatus>(`/api/settings/providers/${provider}/api-key`, {
      method: "PUT",
      body: JSON.stringify({ api_key: apiKey })
    }),
  deleteProviderKey: (provider: ProviderName) =>
    request<ProviderSecretStatus>(`/api/settings/providers/${provider}/api-key`, {
      method: "DELETE"
    })
};

export interface StreamChatPayload {
  message: string;
  session_id?: string;
  model_id?: string;
  agent_id?: string;
  agent_ids?: string[];
  project_id?: string | null;
  folder_id?: string | null;
  project_scope_mode?: "project_only" | "project_plus_global" | "global_only";
  context_project_ids?: string[];
  context_document_ids?: string[];
  context_knowledge_base_ids?: string[];
  reasoning_override?: "default" | "long";
  deep_research?: boolean;
  deep_research_max_tool_calls?: number;
  response_mode?: "text" | "image";
  image_model_id?: string;
  reasoning_summary?: "off" | "auto";
  multi_agent_mode?: boolean;
  attached_document_ids?: string[];
  attached_file_ids?: string[];
  modeling_3d?: ChatModeling3DContext;
}

export interface StreamStatusEvent {
  stage: string;
  label: string;
  detail?: string;
}

export type StreamEventPayload = Record<string, unknown>;

export async function streamChat(
  payload: StreamChatPayload,
  handlers: {
    onMeta?: (data: Record<string, string>) => void;
    onStatus?: (data: StreamStatusEvent) => void;
    onEvent?: (eventName: string, data: StreamEventPayload) => void;
    onSessionTitle?: (data: { session_id: string; title: string }) => void;
    onReasoningSummary?: (token: string) => void;
    onToken: (token: string) => void;
    onError?: (data: Record<string, string>) => void;
    onDone?: () => void;
  }
) {
  const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!response.body) {
    throw new Error(`Chat stream returned ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let sawErrorEvent = false;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";
    for (const event of events) {
      const lines = event.split("\n");
      const eventName = lines
        .find((line) => line.startsWith("event:"))
        ?.replace("event:", "")
        .trim();
      const dataLine = lines.find((line) => line.startsWith("data:"));
      if (!eventName || !dataLine) continue;
      const data = JSON.parse(dataLine.replace("data:", "").trim()) as Record<string, unknown>;
      handlers.onEvent?.(eventName, data);
      const stringData = Object.fromEntries(
        Object.entries(data).map(([key, value]) => [
          key,
          typeof value === "string" ? value : value == null ? "" : JSON.stringify(value)
        ])
      );
      if (eventName === "meta") handlers.onMeta?.(stringData);
      if (eventName === "status") handlers.onStatus?.(data as unknown as StreamStatusEvent);
      if (eventName === "session_title") {
        handlers.onSessionTitle?.({
          session_id: String(data.session_id ?? ""),
          title: String(data.title ?? "")
        });
      }
      if (eventName === "reasoning_summary") handlers.onReasoningSummary?.(String(data.content ?? ""));
      if (eventName === "token") handlers.onToken(String(data.content ?? ""));
      if (eventName === "error") {
        sawErrorEvent = true;
        handlers.onError?.(stringData);
      }
      if (eventName === "done") handlers.onDone?.();
    }
  }

  if (!response.ok && !sawErrorEvent) {
    throw new Error(`Chat stream returned ${response.status}`);
  }
}
