import {
  Activity,
  Bot,
  Check,
  ChevronRight,
  Database,
  EllipsisVertical,
  ExternalLink,
  FileText,
  FolderTree,
  Gauge,
  KeyRound,
  Library,
  LoaderCircle,
  Menu,
  MessageSquare,
  Plus,
  Send,
  Server,
  Settings2,
  ShieldCheck,
  Sparkles,
  Users,
  Wifi,
  X
} from "lucide-react";
import type { FormEvent } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useShallow } from "zustand/react/shallow";

import { useChatScopeSync } from "./app/hooks/use-chat-scope-sync";
import { useKnowledgeScopeSync, type ProjectsStatus } from "./app/hooks/use-knowledge-scope-sync";
import { useOutsidePointerClose } from "./app/hooks/use-outside-pointer-close";
import { infraLinks, quickActions } from "./app/constants";
import { appDataQueryKey, fetchAppDataSnapshot } from "./app/queries/app-data";
import { useAppStore } from "./app/store";
import type { LoadState, ProviderCatalogState } from "./app/ui-state";
import { MessageBubble } from "./components/app-chat";
import {
  ContextChip,
  DashboardNavButton,
  DuplicateFileModal,
  EmptyPanel,
  ExecutionMenuItem,
  InfoRow,
  Metric,
  PanelButton,
  PanelStack,
  PanelTitle
} from "./components/app-panels";
import { Badge } from "./components/ui/Badge";
import { Button } from "./components/ui/Button";
import { api, streamChat } from "./lib/api";
import {
  agentRequiredFieldsComplete,
  createEmptyAgentDraft,
  llmConfigFromAgent,
  normalizeLLMConfig
} from "./features/agents/agent-domain";
import {
  type ChatMessageAttachment,
  initialAssistantStatus,
  localAssistantMessage,
  withModelingPlan,
  withReasoningSummary,
  withRuntimeStatus
} from "./features/chat/chat-domain";
import {
  fileContentUrl,
  platformFileLabel,
  type DuplicateFileDestination,
  type PendingDuplicateFile
} from "./features/files/file-domain";
import {
  createDefaultProjectDraft,
  projectDisplayName,
  sortFoldersForUi,
  sortProjectsForUi
} from "./features/projects/project-domain";
import { ContextKnowledgeBasesModal } from "./features/chat/context-knowledge-bases-modal";
import {
  AgentDashboard,
  FilesDashboard,
  KnowledgeDashboard,
  ProjectsDashboard
} from "./features/dashboard/dashboard-sections";
import {
  ChatModeling3DBadge,
  EnableModeling3DDialog,
  ModelingDiagnosticsModal
} from "./features/modeling-3d/components";
import { isModeling3DChat } from "./features/modeling-3d/chat-domain";
import { useModeling3dChat } from "./features/modeling-3d/hooks";
import { useModeling3DStore } from "./features/modeling-3d/store";
import { Modeling3DSettingsSection } from "./features/modeling-3d/settings";
import { HistorySection } from "./features/sidebar/history-section";
import { ProjectExplorerSection } from "./features/sidebar/project-explorer-section";
import { csvToList, delay, sortSessionsByNewest } from "./shared/utils/common";
import type {
  Agent,
  AgentUpsert,
  AuditEvent,
  ChatGPTImportJob,
  ChatGPTImportSummary,
  ChatMessage,
  ChatSession,
  CostPolicy,
  CostUsage,
  DocumentRecord,
  KnowledgeBase,
  KnowledgeBaseDocument,
  KnowledgeBaseUpsert,
  DocumentSearchResult,
  ModelConfig,
  ModelingPlan,
  PlatformFile,
  PlatformFileIndexingStatus,
  PlatformFileUpdate,
  ProjectFolder,
  ProjectRecord,
  ProjectUpsert,
  ProviderModel,
  ProviderName,
  ProviderSecretStatus,
  Prompt,
  ServerStatus
} from "./types/api";

type SessionLazyMeta = {
  hasMore: boolean;
  loadingOlder: boolean;
};

type MentionMatch = {
  start: number;
  end: number;
  query: string;
};

type MentionOption = {
  key: string;
  label: string;
  token: string;
};

const CONTEXT_MODAL_SEEN_PROJECTS_STORAGE_KEY = "truths_forge.context_modal_seen_projects.v1";
const FRONTEND_DUPLICATE_HASH_LIMIT_BYTES = 100 * 1024 * 1024;
const DOCUMENT_SNAPSHOT_PAGE_SIZE = 80;

function normalizeMentionPart(value: string): string {
  return value.trim().replace(/ /g, "_");
}

function loadSeenContextModalProjectIds(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(CONTEXT_MODAL_SEEN_PROJECTS_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((value): value is string => typeof value === "string" && value.trim().length > 0);
  } catch {
    return [];
  }
}

function findMentionMatch(input: string, cursor: number): MentionMatch | null {
  const boundedCursor = Math.max(0, Math.min(cursor, input.length));
  const beforeCursor = input.slice(0, boundedCursor);
  const atIndex = beforeCursor.lastIndexOf("@");
  if (atIndex < 0) return null;
  if (atIndex > 0 && /[\w./-]/.test(beforeCursor[atIndex - 1] ?? "")) {
    return null;
  }
  const mentionRaw = beforeCursor.slice(atIndex + 1);
  if (/[^A-Za-z0-9_./-]/.test(mentionRaw)) return null;
  return {
    start: atIndex,
    end: boundedCursor,
    query: mentionRaw.toLowerCase()
  };
}

function mergeUniqueMessages(older: ChatMessage[], newer: ChatMessage[]): ChatMessage[] {
  const seen = new Set<string>();
  const merged: ChatMessage[] = [];
  for (const message of [...older, ...newer]) {
    if (seen.has(message.id)) continue;
    seen.add(message.id);
    merged.push(message);
  }
  return merged;
}

function sessionHasEmptyDraft(session: ChatSession): boolean {
  const metadata = session.metadata as Record<string, unknown> | undefined;
  if (metadata?.is_empty_draft === true) return true;
  if ((session.messages?.length ?? 0) > 0) return false;
  const normalizedTitle = session.title.trim().toLowerCase();
  return normalizedTitle === "novo chat" || normalizedTitle === "new chat";
}

function createChatAttachmentPreview(platformFile: PlatformFile): ChatMessageAttachment {
  return {
    id: platformFile.id,
    file_id: platformFile.id,
    filename: platformFile.filename,
    original_filename: platformFile.original_filename,
    content_type: platformFile.content_type,
    size_bytes: platformFile.size_bytes,
    url: fileContentUrl(platformFile.id)
  };
}

async function sha256BrowserFile(file: File): Promise<string | null> {
  if (!globalThis.crypto?.subtle || file.size > FRONTEND_DUPLICATE_HASH_LIMIT_BYTES) {
    return null;
  }
  const digest = await globalThis.crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function createDefaultKnowledgeBaseDraft(): KnowledgeBaseUpsert {
  return {
    name: "",
    description: "",
    scope: "",
    color: "#f0b84d",
    tags: [],
    max_documents_per_query: 8,
    max_chunks_per_document: 3,
    enabled: true,
    metadata: {}
  };
}

function App() {
  const CHAT_MESSAGE_PAGE_SIZE = 80;
  const {
    activeView,
    activePanel,
    activeSessionId,
    activeAgentId,
    supportAgentIds,
    selectedKnowledgeProjectId,
    selectedKnowledgeFolderId,
    chatProjectId,
    chatProjectScopeMode,
    reasoningOverride,
    deepResearch,
    deepResearchMaxToolCalls,
    responseMode,
    imageModelId,
    reasoningSummary,
    multiAgentMode,
    shortcutMenuOpen,
    shortcutSubmenu,
    executionMenuOpen,
    mobileMenuOpen,
    setActiveView,
    setActivePanel,
    setActiveSessionId,
    setActiveAgentId,
    setSupportAgentIds,
    setSelectedKnowledgeProjectId,
    setSelectedKnowledgeFolderId,
    setChatProjectId,
    setChatProjectScopeMode,
    setReasoningOverride,
    setDeepResearch,
    setDeepResearchMaxToolCalls,
    setResponseMode,
    setImageModelId,
    setReasoningSummary,
    setMultiAgentMode,
    setShortcutMenuOpen,
    setShortcutSubmenu,
    setExecutionMenuOpen,
    setMobileMenuOpen
  } = useAppStore(
    useShallow((state) => ({
      activeView: state.activeView,
      activePanel: state.activePanel,
      activeSessionId: state.activeSessionId,
      activeAgentId: state.activeAgentId,
      supportAgentIds: state.supportAgentIds,
      selectedKnowledgeProjectId: state.selectedKnowledgeProjectId,
      selectedKnowledgeFolderId: state.selectedKnowledgeFolderId,
      chatProjectId: state.chatProjectId,
      chatProjectScopeMode: state.chatProjectScopeMode,
      reasoningOverride: state.reasoningOverride,
      deepResearch: state.deepResearch,
      deepResearchMaxToolCalls: state.deepResearchMaxToolCalls,
      responseMode: state.responseMode,
      imageModelId: state.imageModelId,
      reasoningSummary: state.reasoningSummary,
      multiAgentMode: state.multiAgentMode,
      shortcutMenuOpen: state.shortcutMenuOpen,
      shortcutSubmenu: state.shortcutSubmenu,
      executionMenuOpen: state.executionMenuOpen,
      mobileMenuOpen: state.mobileMenuOpen,
      setActiveView: state.setActiveView,
      setActivePanel: state.setActivePanel,
      setActiveSessionId: state.setActiveSessionId,
      setActiveAgentId: state.setActiveAgentId,
      setSupportAgentIds: state.setSupportAgentIds,
      setSelectedKnowledgeProjectId: state.setSelectedKnowledgeProjectId,
      setSelectedKnowledgeFolderId: state.setSelectedKnowledgeFolderId,
      setChatProjectId: state.setChatProjectId,
      setChatProjectScopeMode: state.setChatProjectScopeMode,
      setReasoningOverride: state.setReasoningOverride,
      setDeepResearch: state.setDeepResearch,
      setDeepResearchMaxToolCalls: state.setDeepResearchMaxToolCalls,
      setResponseMode: state.setResponseMode,
      setImageModelId: state.setImageModelId,
      setReasoningSummary: state.setReasoningSummary,
      setMultiAgentMode: state.setMultiAgentMode,
      setShortcutMenuOpen: state.setShortcutMenuOpen,
      setShortcutSubmenu: state.setShortcutSubmenu,
      setExecutionMenuOpen: state.setExecutionMenuOpen,
      setMobileMenuOpen: state.setMobileMenuOpen
    }))
  );
  const {
    nextChatIs3D,
    software: modeling3dSoftware,
    setNextChatIs3D: setModeling3dEnabled,
    setSoftware: setModeling3dSoftware,
    resetForNewChat: resetModeling3dForNewChat,
    chatContext: modeling3dChatContext
  } = useModeling3dChat();
  const modelingDiagnosticsOpen = useModeling3DStore((state) => state.diagnosticsOpen);
  const setModelingDiagnosticsOpen = useModeling3DStore((state) => state.setDiagnosticsOpen);
  const modelingEnableDialogOpen = useModeling3DStore((state) => state.enableDialogOpen);
  const setModelingEnableDialogOpen = useModeling3DStore((state) => state.setEnableDialogOpen);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [status, setStatus] = useState<ServerStatus | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [knowledgeBaseDocuments, setKnowledgeBaseDocuments] = useState<KnowledgeBaseDocument[]>([]);
  const [platformFiles, setPlatformFiles] = useState<PlatformFile[]>([]);
  const [fileIndexingStatus, setFileIndexingStatus] = useState<PlatformFileIndexingStatus | null>(null);
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [projectFolders, setProjectFolders] = useState<ProjectFolder[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [costPolicy, setCostPolicy] = useState<CostPolicy | null>(null);
  const [costUsage, setCostUsage] = useState<CostUsage | null>(null);
  const [providerStatuses, setProviderStatuses] = useState<ProviderSecretStatus[]>([]);
  const [editingAgentId, setEditingAgentId] = useState<string | null>(null);
  const [agentDraft, setAgentDraft] = useState<AgentUpsert>(() => createEmptyAgentDraft());
  const [agentEditorKey, setAgentEditorKey] = useState(0);
  const [draft, setDraft] = useState("");
  const [draftCursor, setDraftCursor] = useState(0);
  const [activeMention, setActiveMention] = useState<MentionMatch | null>(null);
  const [providerDrafts, setProviderDrafts] = useState<Record<string, string>>({});
  const [providerEditMode, setProviderEditMode] = useState<Record<string, boolean>>({});
  const [providerCatalogs, setProviderCatalogs] = useState<Partial<Record<ProviderName, ProviderModel[]>>>({});
  const [providerCatalogState, setProviderCatalogState] = useState<Partial<Record<ProviderName, ProviderCatalogState>>>(
    {}
  );
  const [providerCatalogErrors, setProviderCatalogErrors] = useState<Partial<Record<ProviderName, string>>>({});
  const [documentTitle, setDocumentTitle] = useState("");
  const [documentContent, setDocumentContent] = useState("");
  const [documentTags, setDocumentTags] = useState("");
  const [documentPinned, setDocumentPinned] = useState(false);
  const [documentQuery, setDocumentQuery] = useState("");
  const [documentResults, setDocumentResults] = useState<DocumentSearchResult[]>([]);
  const [selectedKnowledgeBaseId, setSelectedKnowledgeBaseId] = useState<string | null>(null);
  const [knowledgeBaseDraft, setKnowledgeBaseDraft] = useState<KnowledgeBaseUpsert>(() =>
    createDefaultKnowledgeBaseDraft()
  );
  const [chatGPTImportJob, setChatGPTImportJob] = useState<ChatGPTImportJob | null>(null);
  const [chatGPTImportResult, setChatGPTImportResult] = useState<ChatGPTImportSummary | null>(null);
  const [projectDraft, setProjectDraft] = useState<ProjectUpsert>(() => createDefaultProjectDraft());
  const [folderDraftName, setFolderDraftName] = useState("");
  const [folderDraftParentId, setFolderDraftParentId] = useState<string | null>(null);
  const [projectsStatus, setProjectsStatus] = useState<ProjectsStatus>({ type: "idle", message: "" });
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const [attachedPlatformFileIds, setAttachedPlatformFileIds] = useState<string[]>([]);
  const [attachedDocumentIds, setAttachedDocumentIds] = useState<string[]>([]);
  const [duplicateQueue, setDuplicateQueue] = useState<PendingDuplicateFile[]>([]);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const draftInputRef = useRef<HTMLTextAreaElement | null>(null);
  const pendingCursorRef = useRef<number | null>(null);
  const shortcutMenuRef = useRef<HTMLDivElement | null>(null);
  const executionMenuRef = useRef<HTMLDivElement | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isIndexingDocument, setIsIndexingDocument] = useState(false);
  const [isImportingChatGPT, setIsImportingChatGPT] = useState(false);
  const [deletingSessionId, setDeletingSessionId] = useState<string | null>(null);
  const fetchedSessionDetailsRef = useRef<Set<string>>(new Set());
  const [sessionLazyState, setSessionLazyState] = useState<Record<string, SessionLazyMeta>>({});
  const [historyCollapsed, setHistoryCollapsed] = useState(false);
  const [projectExplorerCollapsed, setProjectExplorerCollapsed] = useState(false);
  const [projectExplorerExpanded, setProjectExplorerExpanded] = useState<Record<string, boolean>>({});
  const [chatContextProjectIds, setChatContextProjectIds] = useState<string[]>([]);
  const [chatContextDocumentIds, setChatContextDocumentIds] = useState<string[]>([]);
  const [chatContextKnowledgeBaseIds, setChatContextKnowledgeBaseIds] = useState<string[]>([]);
  const [contextDocsModalOpen, setContextDocsModalOpen] = useState(false);
  const [contextModalSeenProjectIds, setContextModalSeenProjectIds] =
    useState<string[]>(loadSeenContextModalProjectIds);
  const [isCreatingNewChat, setIsCreatingNewChat] = useState(false);
  const [isCreatingProjectChat, setIsCreatingProjectChat] = useState(false);
  const chatScrollRef = useRef<HTMLDivElement | null>(null);
  const chatLoadOlderRef = useRef<HTMLDivElement | null>(null);
  const chatStickToBottomRef = useRef(true);
  const queryClient = useQueryClient();
  const appDataQuery = useQuery({
    queryKey: appDataQueryKey,
    queryFn: fetchAppDataSnapshot,
    staleTime: 30_000,
    retry: 1,
    refetchOnWindowFocus: false
  });

  const refreshAppDataQuery = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: appDataQueryKey });
  }, [queryClient]);

  const mergeSessionSummaries = useCallback((summaries: ChatSession[]) => {
    setSessions((current) => {
      const currentById = new Map(current.map((session) => [session.id, session]));
      const merged = summaries.map((summary) => {
        const existing = currentById.get(summary.id);
        return existing?.messages.length
          ? { ...summary, messages: existing.messages }
          : { ...summary, messages: summary.messages ?? [] };
      });
      return sortSessionsByNewest(merged);
    });
  }, []);

  const refreshSessionSummaries = useCallback(async () => {
    const summaries = await api.sessions(false);
    mergeSessionSummaries(summaries);
  }, [mergeSessionSummaries]);

  const loadSessionPage = useCallback(
    async (sessionId: string, messageOffset = 0, prepend = false) => {
      const page = await api.session(sessionId, CHAT_MESSAGE_PAGE_SIZE, messageOffset);
      const incomingMessages = page.messages ?? [];
      setSessions((current) => {
        const existing = current.find((session) => session.id === page.id);
        const mergedMessages = prepend
          ? mergeUniqueMessages(incomingMessages, existing?.messages ?? [])
          : incomingMessages;
        const updatedSession = {
          ...(existing ?? page),
          ...page,
          messages: mergedMessages
        };
        const updated = existing
          ? current.map((session) => (session.id === page.id ? updatedSession : session))
          : [updatedSession, ...current];
        return sortSessionsByNewest(updated);
      });
      setSessionLazyState((current) => ({
        ...current,
        [sessionId]: {
          hasMore: incomingMessages.length === CHAT_MESSAGE_PAGE_SIZE,
          loadingOlder: false
        }
      }));
    },
    [CHAT_MESSAGE_PAGE_SIZE]
  );

  const loadOlderMessages = useCallback(
    async (sessionId: string, loadedCount: number) => {
      const lazy = sessionLazyState[sessionId];
      if (!lazy?.hasMore || lazy.loadingOlder) return;
      setSessionLazyState((current) => ({
        ...current,
        [sessionId]: {
          hasMore: current[sessionId]?.hasMore ?? true,
          loadingOlder: true
        }
      }));
      const container = chatScrollRef.current;
      const previousHeight = container?.scrollHeight ?? 0;
      const previousTop = container?.scrollTop ?? 0;
      try {
        await loadSessionPage(sessionId, loadedCount, true);
      } finally {
        requestAnimationFrame(() => {
          const currentContainer = chatScrollRef.current;
          if (!currentContainer) return;
          const heightDelta = currentContainer.scrollHeight - previousHeight;
          currentContainer.scrollTop = Math.max(0, previousTop + heightDelta);
        });
        setSessionLazyState((current) => ({
          ...current,
          [sessionId]: {
            hasMore: current[sessionId]?.hasMore ?? false,
            loadingOlder: false
          }
        }));
      }
    },
    [loadSessionPage, sessionLazyState]
  );

  const handleChatScroll = useCallback(() => {
    const container = chatScrollRef.current;
    if (!container) return;
    const remaining = container.scrollHeight - (container.scrollTop + container.clientHeight);
    chatStickToBottomRef.current = remaining <= 120;
  }, []);

  useEffect(() => {
    if (appDataQuery.isPending) {
      setLoadState("loading");
      return;
    }
    if (appDataQuery.isError) {
      setLoadState("offline");
      return;
    }
    if (appDataQuery.data) {
      setLoadState("ready");
    }
  }, [appDataQuery.data, appDataQuery.isError, appDataQuery.isPending]);

  useEffect(() => {
    const data = appDataQuery.data;
    if (!data) return;
    const {
      serverStatus,
      chatSessions,
      modelList,
      agentList,
      promptList,
      documentList,
      knowledgeBaseList,
      knowledgeBaseDocumentList,
      fileList,
      fileIndexingStatus: nextFileIndexingStatus,
      projectList,
      folderList,
      auditList,
      policy,
      usage,
      providerList
    } = data;
    const sortedChatSessions = sortSessionsByNewest(chatSessions);
    setStatus(serverStatus);
    mergeSessionSummaries(sortedChatSessions);
    setModels(modelList);
    setAgents(agentList);
    setPrompts(promptList);
    setDocuments(documentList);
    setKnowledgeBases(knowledgeBaseList);
    setKnowledgeBaseDocuments(knowledgeBaseDocumentList);
    setPlatformFiles(fileList);
    setFileIndexingStatus(nextFileIndexingStatus);
    setProjects(sortProjectsForUi(projectList));
    setProjectFolders(sortFoldersForUi(folderList));
    setAuditEvents(auditList);
    setCostPolicy(policy);
    setCostUsage(usage);
    setProviderStatuses(providerList);
    setActiveSessionId((current) =>
      current && sortedChatSessions.some((session) => session.id === current)
        ? current
        : (sortedChatSessions[0]?.id ?? null)
    );
    setActiveAgentId((current) =>
      current && agentList.some((agent) => agent.id === current)
        ? current
        : (agentList.find((agent) => agent.name === "JUDITE")?.id ?? agentList[0]?.id ?? null)
    );
    setSupportAgentIds((current) => current.filter((agentId) => agentList.some((agent) => agent.id === agentId)));
    const generalProjectId = projectList.find((project) => project.is_general)?.id ?? projectList[0]?.id ?? null;
    setSelectedKnowledgeProjectId((current) =>
      current && projectList.some((project) => project.id === current) ? current : generalProjectId
    );
    setSelectedKnowledgeFolderId((current) =>
      current && folderList.some((folder) => folder.id === current) ? current : null
    );
    setSelectedKnowledgeBaseId((current) =>
      current && knowledgeBaseList.some((knowledgeBase) => knowledgeBase.id === current)
        ? current
        : (knowledgeBaseList[0]?.id ?? null)
    );
    const validPersistedProjectId =
      chatProjectId && projectList.some((project) => project.id === chatProjectId) ? chatProjectId : null;
    const selectedSessionForScope =
      sortedChatSessions.find((session) => session.id === (activeSessionId ?? sortedChatSessions[0]?.id ?? "")) ?? null;
    const sessionProjectId =
      selectedSessionForScope?.project_id &&
      projectList.some((project) => project.id === selectedSessionForScope.project_id)
        ? selectedSessionForScope.project_id
        : null;
    const resolvedChatProjectId = validPersistedProjectId ?? sessionProjectId ?? null;
    setChatProjectId(resolvedChatProjectId);
    setChatProjectScopeMode((current) => {
      if (!resolvedChatProjectId) return "global_only";
      return current === "project_only" || current === "project_plus_global" ? current : "project_only";
    });
    setFolderDraftParentId((current) =>
      current && folderList.some((folder) => folder.id === current) ? current : null
    );
  }, [
    activeSessionId,
    appDataQuery.data,
    chatProjectId,
    mergeSessionSummaries,
    setActiveAgentId,
    setActiveSessionId,
    setChatProjectId,
    setChatProjectScopeMode,
    setSelectedKnowledgeFolderId,
    setSelectedKnowledgeProjectId,
    setSupportAgentIds
  ]);

  useEffect(() => {
    if (loadState !== "ready") return;
    let active = true;
    let intervalId: ReturnType<typeof setInterval> | null = null;

    const refreshIndexingStatus = async () => {
      try {
        const nextStatus = await api.fileIndexingStatus();
        if (!active) return;
        setFileIndexingStatus(nextStatus);
        if (nextStatus.backlog_files > 0) {
          const nextDocumentsPage = await api.documentsPage({ limit: DOCUMENT_SNAPSHOT_PAGE_SIZE, offset: 0 });
          if (!active) return;
          setDocuments(nextDocumentsPage.items);
        }
      } catch (error) {
        console.error(error);
      }
    };

    void refreshIndexingStatus();
    intervalId = setInterval(() => {
      void refreshIndexingStatus();
    }, 8000);

    return () => {
      active = false;
      if (intervalId) clearInterval(intervalId);
    };
  }, [loadState]);

  useEffect(() => {
    if (!activeSessionId) return;
    const activeSummary = sessions.find((session) => session.id === activeSessionId);
    if (!activeSummary) return;
    if (activeSummary.messages.length > 0) return;
    if (fetchedSessionDetailsRef.current.has(activeSessionId)) return;
    fetchedSessionDetailsRef.current.add(activeSessionId);
    chatStickToBottomRef.current = true;
    void loadSessionPage(activeSessionId).finally(() => {
      fetchedSessionDetailsRef.current.delete(activeSessionId);
    });
  }, [activeSessionId, loadSessionPage, sessions]);

  const activeSession = useMemo(
    () => sessions.find((session) => session.id === activeSessionId) ?? null,
    [activeSessionId, sessions]
  );
  const activeSessionIsModeling3D = isModeling3DChat(activeSession);
  const modeling3dEnabled = nextChatIs3D || activeSessionIsModeling3D;
  const activeModelingPlanId = activeSession?.modeling_plan_id ?? null;
  const platformFilesById = useMemo(
    () =>
      Object.fromEntries(platformFiles.map((platformFile) => [platformFile.id, platformFile])) as Record<
        string,
        PlatformFile
      >,
    [platformFiles]
  );
  const activeSessionLazy = activeSessionId ? sessionLazyState[activeSessionId] : undefined;
  const activeMessageSignature = useMemo(() => {
    if (!activeSession?.messages.length) return "empty";
    const lastMessage = activeSession.messages[activeSession.messages.length - 1];
    return `${activeSession.id}:${activeSession.messages.length}:${lastMessage?.id ?? ""}:${lastMessage?.content.length ?? 0}`;
  }, [activeSession]);
  const sortedSessions = useMemo(() => sortSessionsByNewest(sessions), [sessions]);

  useEffect(() => {
    chatStickToBottomRef.current = true;
  }, [activeSessionId]);

  useEffect(() => {
    if (activeView !== "chat") return;
    if (!activeSessionId) return;
    if (!chatStickToBottomRef.current) return;
    const frame = requestAnimationFrame(() => {
      const container = chatScrollRef.current;
      if (!container) return;
      container.scrollTop = container.scrollHeight;
    });
    return () => cancelAnimationFrame(frame);
  }, [activeMessageSignature, activeSessionId, activeView]);

  useEffect(() => {
    if (activeView !== "chat") return;
    if (!activeSession || !activeSessionLazy?.hasMore || activeSessionLazy.loadingOlder) return;
    const sentinel = chatLoadOlderRef.current;
    const root = chatScrollRef.current;
    if (!sentinel || !root) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        void loadOlderMessages(activeSession.id, activeSession.messages.length);
      },
      {
        root,
        rootMargin: "220px 0px 0px 0px",
        threshold: 0
      }
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [activeSession, activeSessionLazy, activeView, loadOlderMessages]);

  const judite = agents.find((agent) => agent.name === "JUDITE");
  const activeAgent = agents.find((agent) => agent.id === activeAgentId) ?? judite ?? agents[0];
  const supportAgents = agents.filter((agent) => supportAgentIds.includes(agent.id) && agent.id !== activeAgent?.id);
  const activeAgentBaseModel = models.find((model) => model.id === activeAgent?.model_id);
  const activeAgentProvider = activeAgent?.llm_config?.provider ?? activeAgentBaseModel?.provider ?? "openai";
  const activeAgentInputCost =
    activeAgent?.llm_config?.input_token_cost_per_million ?? activeAgentBaseModel?.input_token_cost_per_million ?? null;
  const activeAgentOutputCost =
    activeAgent?.llm_config?.output_token_cost_per_million ??
    activeAgentBaseModel?.output_token_cost_per_million ??
    null;
  const activeAgentPricingConfigured =
    activeAgentInputCost !== null &&
    activeAgentInputCost > 0 &&
    activeAgentOutputCost !== null &&
    activeAgentOutputCost > 0;
  const reasoningSummaryUnavailable =
    activeAgentProvider !== "openai" || deepResearch || responseMode === "image" || modeling3dEnabled;
  const activeAgentModelLabel =
    activeAgent?.llm_config?.provider_model_id ??
    activeAgentBaseModel?.provider_model_id ??
    activeAgentBaseModel?.display_name ??
    "modelo do agente";
  const deepResearchModel = models.find((model) => model.capabilities.includes("deep_research"));
  const deepResearchPricingMissing =
    deepResearch &&
    (!deepResearchModel?.input_token_cost_per_million ||
      deepResearchModel.input_token_cost_per_million <= 0 ||
      !deepResearchModel.output_token_cost_per_million ||
      deepResearchModel.output_token_cost_per_million <= 0);
  const imageCapableModels = models.filter((model) => model.enabled && model.capabilities.includes("image_generation"));
  const selectedImageModel = imageCapableModels.find((model) => model.id === imageModelId) ?? null;
  const defaultImageModel =
    imageCapableModels.find((model) => model.provider === activeAgentProvider) ?? imageCapableModels[0] ?? null;
  const effectiveImageModel = selectedImageModel ?? defaultImageModel;
  const imageModelMissing = responseMode === "image" && !effectiveImageModel;
  const reasoningSummaryPricingMissing = reasoningSummary && !activeAgentPricingConfigured;
  const generalProject = projects.find((project) => project.is_general) ?? projects[0] ?? null;
  const generalProjectId = generalProject?.id ?? "project_general";
  const nonGeneralProjects = projects.filter((project) => !project.is_general);
  const generalHistorySessions = sortedSessions.filter((session) => session.project_id === generalProjectId);
  const projectExplorerSessions = sortedSessions.filter((session) => session.project_id !== generalProjectId);
  const selectedKnowledgeProject =
    projects.find((project) => project.id === selectedKnowledgeProjectId) ??
    (selectedKnowledgeProjectId ? (generalProject ?? null) : null);
  const foldersBySelectedProject = projectFolders.filter(
    (folder) => folder.project_id === selectedKnowledgeProject?.id
  );
  const selectedKnowledgeFolder =
    foldersBySelectedProject.find((folder) => folder.id === selectedKnowledgeFolderId) ?? null;
  const selectedKnowledgeBase = selectedKnowledgeBaseId
    ? (knowledgeBases.find((knowledgeBase) => knowledgeBase.id === selectedKnowledgeBaseId) ?? null)
    : null;
  const selectedKnowledgeBaseItemIdList = useMemo(
    () =>
      knowledgeBaseDocuments
        .filter((item) => item.knowledge_base_id === selectedKnowledgeBase?.id)
        .map((item) => item.document_id)
        .filter((documentId): documentId is string => Boolean(documentId)),
    [knowledgeBaseDocuments, selectedKnowledgeBase?.id]
  );
  const selectedKnowledgeBaseItemIds = new Set(selectedKnowledgeBaseItemIdList);
  const selectedKnowledgeBaseDocuments = documents.filter(
    (document) => document.id && selectedKnowledgeBaseItemIds.has(document.id)
  );
  const runtimeSupportAgents = multiAgentMode ? supportAgents : [];
  const pendingDuplicateFile = duplicateQueue[0] ?? null;
  const activeSessionProjectId = activeSession?.project_id ?? chatProjectId ?? generalProjectId;
  const activeSessionFolderId = activeSession?.folder_id ?? null;
  const activeAgentAllowedProjectIds = activeAgent?.allowed_project_ids?.length
    ? activeAgent.allowed_project_ids
    : [generalProjectId];
  const availableContextProjects = projects.filter((project) => activeAgentAllowedProjectIds.includes(project.id));
  const mentionOptions = useMemo<MentionOption[]>(() => {
    const allowedProjectIds = new Set(availableContextProjects.map((project) => project.id));
    const projectById = new Map(availableContextProjects.map((project) => [project.id, project]));
    const options = projectFolders
      .filter((folder) => allowedProjectIds.has(folder.project_id))
      .map((folder) => {
        const project = projectById.get(folder.project_id);
        if (!project) return null;
        const projectLabel = projectDisplayName(project);
        const token = `${normalizeMentionPart(projectLabel)}/${normalizeMentionPart(folder.path)}`;
        return {
          key: `${project.id}:${folder.id}`,
          label: `${projectLabel} / ${folder.path}`,
          token
        } satisfies MentionOption;
      })
      .filter((option): option is MentionOption => option !== null);
    return options.sort((left, right) => left.label.localeCompare(right.label, "pt-BR", { sensitivity: "base" }));
  }, [availableContextProjects, projectFolders]);
  const normalizedContextProjectIds = (chatContextProjectIds.length ? chatContextProjectIds : [activeSessionProjectId])
    .filter((projectId, index, list) => list.indexOf(projectId) === index)
    .filter((projectId) => availableContextProjects.some((project) => project.id === projectId))
    .slice(0, 1);
  const activeProject = projects.find((project) => project.id === normalizedContextProjectIds[0]) ?? generalProject;
  const projectKnowledgeBaseIds = activeProject?.context?.knowledge_base_ids ?? [];
  const agentKnowledgeBaseIds = activeAgent?.knowledge_base_ids ?? [];
  const allowedRuntimeKnowledgeBaseIds = [...projectKnowledgeBaseIds, ...agentKnowledgeBaseIds]
    .filter((knowledgeBaseId, index, list) => list.indexOf(knowledgeBaseId) === index)
    .filter((knowledgeBaseId) =>
      knowledgeBases.some((knowledgeBase) => knowledgeBase.id === knowledgeBaseId && knowledgeBase.enabled)
    )
    .slice(0, 12);
  const normalizedContextKnowledgeBaseIds = (
    chatContextKnowledgeBaseIds.length ? chatContextKnowledgeBaseIds : allowedRuntimeKnowledgeBaseIds
  )
    .filter((knowledgeBaseId, index, list) => list.indexOf(knowledgeBaseId) === index)
    .filter((knowledgeBaseId) => allowedRuntimeKnowledgeBaseIds.includes(knowledgeBaseId))
    .slice(0, 12);
  const selectedKnowledgeBasesLabel = normalizedContextKnowledgeBaseIds.length
    ? `${normalizedContextKnowledgeBaseIds.length} base(s)`
    : "sem bases";
  const selectedKnowledgeBaseNames = normalizedContextKnowledgeBaseIds
    .map((knowledgeBaseId) => knowledgeBases.find((knowledgeBase) => knowledgeBase.id === knowledgeBaseId)?.name)
    .filter(Boolean)
    .join(", ");
  const selectedContextDocsLabel = selectedKnowledgeBaseNames || selectedKnowledgeBasesLabel;
  const scopeModeLabel = "projeto atual";
  const contextProjectsLabel =
    normalizedContextProjectIds
      .map((projectId) => {
        const project = projects.find((item) => item.id === projectId);
        return project ? projectDisplayName(project) : projectId;
      })
      .join(", ") || "Contexto geral";
  const availableContextDocuments = documents.filter((document) =>
    knowledgeBaseDocuments.some(
      (item) =>
        item.enabled &&
        normalizedContextKnowledgeBaseIds.includes(item.knowledge_base_id) &&
        item.document_id === document.id
    )
  );
  const normalizedContextDocumentIds = chatContextDocumentIds
    .filter((documentId, index, list) => list.indexOf(documentId) === index)
    .filter((documentId) => availableContextDocuments.some((document) => document.id === documentId))
    .slice(0, 20);
  const mentionSuggestions = useMemo(() => {
    if (!activeMention) return [];
    if (!activeMention.query) return mentionOptions.slice(0, 8);
    const query = activeMention.query.toLowerCase();
    return mentionOptions
      .filter((option) => option.token.toLowerCase().includes(query) || option.label.toLowerCase().includes(query))
      .slice(0, 8);
  }, [activeMention, mentionOptions]);
  const executionLabels = [
    modeling3dEnabled ? `MCP 3D (${modeling3dSoftware === "auto" ? "auto" : modeling3dSoftware})` : null,
    reasoningOverride === "long" ? "Raciocínio longo" : null,
    reasoningSummary ? "Resumo oficial" : null,
    deepResearch ? "Pesquisa OpenAI" : null,
    responseMode === "image" ? `Imagem${effectiveImageModel ? ` (${effectiveImageModel.display_name})` : ""}` : null,
    multiAgentMode ? `Multiagente (${runtimeSupportAgents.length})` : null
  ].filter(Boolean) as string[];
  const multiAgentMissingSupport = multiAgentMode && runtimeSupportAgents.length === 0;
  const blockedByExecutionConfig =
    deepResearchPricingMissing || reasoningSummaryPricingMissing || multiAgentMissingSupport || imageModelMissing;
  const sendDisabledReason = deepResearchPricingMissing
    ? "Deep Research exige preço do modelo configurado no Cost Governor."
    : reasoningSummaryPricingMissing
      ? "Resumo oficial exige preço do modelo configurado no Cost Governor."
      : multiAgentMissingSupport
        ? "Ative pelo menos um agente de apoio para usar multiagente."
        : imageModelMissing
          ? "Ative ou selecione um modelo com capacidade de geração de imagem."
          : null;
  const sendDisabled = !draft.trim() || loadState === "offline" || isStreaming || blockedByExecutionConfig;
  const sendButtonTitle = sendDisabledReason
    ? sendDisabledReason
    : loadState === "offline"
      ? "Servidor indisponível."
      : isStreaming
        ? "Aguarde a resposta atual terminar."
        : !draft.trim()
          ? "Digite uma mensagem para enviar."
          : "Enviar";

  useChatScopeSync({
    activeSessionProjectId: activeSession?.project_id ?? null,
    chatProjectId,
    chatProjectScopeMode,
    setChatProjectId,
    setChatProjectScopeMode
  });

  useKnowledgeScopeSync({
    projects,
    projectFolders,
    selectedKnowledgeProjectId,
    selectedKnowledgeFolderId,
    folderDraftParentId,
    setSelectedKnowledgeProjectId,
    setSelectedKnowledgeFolderId,
    setFolderDraftParentId,
    setProjectDraft,
    setProjectsStatus
  });

  useEffect(() => {
    if (reasoningSummary && reasoningSummaryUnavailable) {
      setReasoningSummary(false);
    }
  }, [reasoningSummary, reasoningSummaryUnavailable, setReasoningSummary]);

  useEffect(() => {
    if (!selectedKnowledgeBase) {
      setKnowledgeBaseDraft(createDefaultKnowledgeBaseDraft());
      return;
    }
    setKnowledgeBaseDraft({
      name: selectedKnowledgeBase.name,
      description: selectedKnowledgeBase.description,
      scope: selectedKnowledgeBase.scope,
      color: selectedKnowledgeBase.color,
      tags: selectedKnowledgeBase.tags,
      max_documents_per_query: selectedKnowledgeBase.max_documents_per_query,
      max_chunks_per_document: selectedKnowledgeBase.max_chunks_per_document,
      enabled: selectedKnowledgeBase.enabled,
      metadata: selectedKnowledgeBase.metadata
    });
  }, [selectedKnowledgeBase]);

  useEffect(() => {
    const knownDocumentIds = new Set(documents.map((document) => document.id));
    const missingIds = selectedKnowledgeBaseItemIdList.filter((documentId) => !knownDocumentIds.has(documentId));
    if (!missingIds.length) return;
    let active = true;
    void api.documentsByIds(missingIds).then((nextDocuments) => {
      if (!active || !nextDocuments.length) return;
      setDocuments((current) => {
        const currentIds = new Set(current.map((document) => document.id).filter(Boolean));
        const merged = [...nextDocuments.filter((document) => document.id && !currentIds.has(document.id)), ...current];
        return merged.sort((left, right) => Date.parse(right.updated_at ?? "") - Date.parse(left.updated_at ?? ""));
      });
    });
    return () => {
      active = false;
    };
  }, [documents, selectedKnowledgeBaseItemIdList]);

  useEffect(() => {
    if (!imageCapableModels.length) {
      if (imageModelId !== null) setImageModelId(null);
      return;
    }
    if (imageModelId && imageCapableModels.some((model) => model.id === imageModelId)) {
      return;
    }
    setImageModelId(defaultImageModel?.id ?? imageCapableModels[0]?.id ?? null);
  }, [defaultImageModel, imageCapableModels, imageModelId, setImageModelId]);

  useEffect(() => {
    setActiveMention(findMentionMatch(draft, draftCursor));
  }, [draft, draftCursor]);

  useEffect(() => {
    const pendingCursor = pendingCursorRef.current;
    const input = draftInputRef.current;
    if (pendingCursor === null || !input) return;
    pendingCursorRef.current = null;
    input.focus();
    input.setSelectionRange(pendingCursor, pendingCursor);
    setDraftCursor(pendingCursor);
  }, [draft]);

  useOutsidePointerClose({
    shortcutMenuRef,
    executionMenuRef,
    onCloseShortcutMenu: () => {
      setShortcutMenuOpen(false);
      setShortcutSubmenu(null);
    },
    onCloseExecutionMenu: () => {
      setExecutionMenuOpen(false);
    }
  });

  useEffect(() => {
    if (!activeSession) return;
    const fallbackProjectId = activeSession.project_id ?? generalProjectId;
    const incomingProjectIds =
      activeSession.context_project_ids.length > 0 ? activeSession.context_project_ids : [fallbackProjectId];
    const incomingDocumentIds = activeSession.context_document_ids ?? [];
    const incomingKnowledgeBaseIds = activeSession.context_knowledge_base_ids ?? [];
    setChatContextProjectIds(incomingProjectIds.slice(0, 1));
    setChatContextDocumentIds(incomingDocumentIds.slice(0, 20));
    setChatContextKnowledgeBaseIds(incomingKnowledgeBaseIds);
  }, [activeSession, generalProjectId]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(CONTEXT_MODAL_SEEN_PROJECTS_STORAGE_KEY, JSON.stringify(contextModalSeenProjectIds));
    } catch {
      // Ignore localStorage persistence errors (private mode / quota).
    }
  }, [contextModalSeenProjectIds]);

  useEffect(() => {
    if (activeView !== "chat") return;
    if (!normalizedContextProjectIds.length) return;
    if (contextDocsModalOpen) return;
    const seenSet = new Set(contextModalSeenProjectIds);
    const unseenProjectIds = normalizedContextProjectIds.filter((projectId) => !seenSet.has(projectId));
    if (!unseenProjectIds.length) return;
    setContextModalSeenProjectIds((current) => Array.from(new Set([...current, ...unseenProjectIds])));
    setContextDocsModalOpen(true);
  }, [activeView, contextDocsModalOpen, contextModalSeenProjectIds, normalizedContextProjectIds]);

  const insertFolderMention = useCallback(
    (option: MentionOption) => {
      if (!activeMention) return;
      const prefix = draft.slice(0, activeMention.start);
      const suffix = draft.slice(activeMention.end);
      const mentionText = `@${option.token}`;
      const nextDraft = `${prefix}${mentionText} ${suffix}`;
      const nextCursor = prefix.length + mentionText.length + 1;
      pendingCursorRef.current = nextCursor;
      setDraft(nextDraft);
      setActiveMention(null);
    },
    [activeMention, draft]
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = draft.trim();
    if (!message || isStreaming) return;
    chatStickToBottomRef.current = true;
    setDraft("");
    setIsStreaming(true);

    let sessionId = activeSession?.id;
    const uploadedFileIds: string[] = [...attachedPlatformFileIds];
    let optimisticUser: ChatMessage | null = null;
    let optimisticAssistant: ChatMessage | null = null;
    const modeling3dPayload = activeSessionIsModeling3D
      ? {
          enabled: true,
          mode: "safe_auto" as const,
          software_override:
            activeSession?.modeling_software_preference && activeSession.modeling_software_preference !== "auto"
              ? activeSession.modeling_software_preference
              : modeling3dSoftware === "auto"
                ? null
                : modeling3dSoftware
        }
      : modeling3dChatContext();
    const optimisticStatus = initialAssistantStatus({
      reasoningOverride,
      deepResearch,
      responseMode,
      multiAgentMode,
      reasoningSummary,
      modeling3dEnabled
    });

    try {
      let createdAttachments: PlatformFile[] = [];
      if (attachedFiles.length) {
        createdAttachments = await Promise.all(
          attachedFiles.map(async (file) =>
            api.uploadFile(file, "chat_attachment", {
              project_id: activeSessionProjectId,
              folder_id: activeSessionFolderId,
              session_id: sessionId ?? activeSession?.id ?? null
            })
          )
        );
        uploadedFileIds.push(...createdAttachments.map((platformFile) => platformFile.id));
        setPlatformFiles((current) => [...createdAttachments, ...current]);
      }

      const filesById = new Map(platformFiles.map((platformFile) => [platformFile.id, platformFile]));
      for (const platformFile of createdAttachments) {
        filesById.set(platformFile.id, platformFile);
      }
      const attachedPreviewFiles = uploadedFileIds
        .map((fileId) => filesById.get(fileId))
        .filter((platformFile): platformFile is PlatformFile => !!platformFile);
      const attachedPreviews = attachedPreviewFiles.map((platformFile) => createChatAttachmentPreview(platformFile));

      optimisticUser = {
        id: `user_${Date.now()}`,
        session_id: sessionId ?? "pending",
        role: "user",
        content: message,
        model_id: activeAgentModelLabel,
        metadata: {
          attached_document_ids: attachedDocumentIds,
          attached_file_ids: uploadedFileIds,
          attached_files: attachedPreviews
        },
        created_at: new Date().toISOString()
      };
      optimisticAssistant = localAssistantMessage(sessionId ?? "pending", optimisticStatus, reasoningSummary);

      const optimisticUserMessage = optimisticUser;
      const optimisticAssistantMessage = optimisticAssistant;
      if (sessionId && optimisticUserMessage && optimisticAssistantMessage) {
        setSessions((current) =>
          current.map((session) =>
            session.id === sessionId
              ? {
                  ...session,
                  metadata: {
                    ...((session.metadata ?? {}) as Record<string, unknown>),
                    is_empty_draft: false
                  },
                  messages: [...session.messages, optimisticUserMessage, optimisticAssistantMessage]
                }
              : session
          )
        );
      }

      await streamChat(
        {
          message,
          session_id: sessionId ?? undefined,
          agent_id: activeAgent?.id,
          agent_ids: runtimeSupportAgents.map((agent) => agent.id),
          project_id: chatProjectId,
          folder_id: activeSessionFolderId,
          project_scope_mode: chatProjectScopeMode,
          context_project_ids: normalizedContextProjectIds,
          context_document_ids: normalizedContextDocumentIds,
          context_knowledge_base_ids: normalizedContextKnowledgeBaseIds,
          reasoning_override: reasoningOverride,
          deep_research: deepResearch,
          deep_research_max_tool_calls: deepResearchMaxToolCalls,
          response_mode: responseMode,
          image_model_id: responseMode === "image" ? (effectiveImageModel?.id ?? undefined) : undefined,
          reasoning_summary: reasoningSummary ? "auto" : "off",
          multi_agent_mode: multiAgentMode,
          attached_document_ids: attachedDocumentIds,
          attached_file_ids: uploadedFileIds,
          modeling_3d: modeling3dPayload
        },
        {
          onMeta: (meta) => {
            sessionId = meta.session_id;
            setActiveSessionId(meta.session_id);
            fetchedSessionDetailsRef.current.delete(meta.session_id);
            const resolvedUserMessage: ChatMessage = optimisticUser
              ? { ...optimisticUser, session_id: meta.session_id }
              : {
                  id: `user_${Date.now()}`,
                  session_id: meta.session_id,
                  role: "user",
                  content: message,
                  model_id: activeAgentModelLabel,
                  created_at: new Date().toISOString()
                };
            const resolvedAssistantMessage: ChatMessage = optimisticAssistant
              ? { ...optimisticAssistant, id: meta.message_id, session_id: meta.session_id }
              : {
                  ...localAssistantMessage(meta.session_id, optimisticStatus, reasoningSummary),
                  id: meta.message_id,
                  session_id: meta.session_id
                };
            setSessions((current) => {
              if (current.some((session) => session.id === meta.session_id)) return current;
              return sortSessionsByNewest([
                {
                  id: meta.session_id,
                  title: message.slice(0, 48),
                  model_id: activeAgentModelLabel,
                  agent_id: activeAgent?.id,
                  project_id: activeSessionProjectId,
                  folder_id: activeSessionFolderId,
                  context_project_ids: normalizedContextProjectIds,
                  context_document_ids: normalizedContextDocumentIds,
                  context_knowledge_base_ids: normalizedContextKnowledgeBaseIds,
                  is_modeling_3d: modeling3dPayload.enabled,
                  modeling_software_preference: modeling3dPayload.software_override ?? "auto",
                  modeling_stage: modeling3dPayload.enabled ? "discovery" : null,
                  modeling_plan_id: null,
                  archived: false,
                  metadata: { is_empty_draft: false },
                  created_at: new Date().toISOString(),
                  updated_at: new Date().toISOString(),
                  messages: [resolvedUserMessage, resolvedAssistantMessage]
                },
                ...current
              ]);
            });
          },
          onStatus: (status) => {
            setSessions((current) =>
              current.map((session) => {
                if (session.id !== sessionId) return session;
                const messages = session.messages.map((item, index) =>
                  index === session.messages.length - 1 && item.role === "assistant"
                    ? withRuntimeStatus(item, status)
                    : item
                );
                return { ...session, messages };
              })
            );
          },
          onEvent: (eventName, data) => {
            if (eventName !== "modeling_plan") return;
            const plan = data.plan as ModelingPlan | undefined;
            if (!plan) return;
            setSessions((current) =>
              current.map((session) => {
                if (session.id !== sessionId) return session;
                const messages = session.messages.map((item, index) =>
                  index === session.messages.length - 1 && item.role === "assistant"
                    ? withModelingPlan(item, plan)
                    : item
                );
                return {
                  ...session,
                  is_modeling_3d: true,
                  modeling_software_preference: plan.software_choice,
                  modeling_stage: plan.status === "completed" ? "editing" : "executing",
                  modeling_plan_id: plan.id,
                  messages
                };
              })
            );
          },
          onToken: (token) => {
            setSessions((current) =>
              current.map((session) => {
                if (session.id !== sessionId) return session;
                const messages = session.messages.map((item, index) =>
                  index === session.messages.length - 1 && item.role === "assistant"
                    ? { ...item, content: item.content ? item.content + token : token }
                    : item
                );
                return { ...session, messages };
              })
            );
          },
          onReasoningSummary: (token) => {
            setSessions((current) =>
              current.map((session) => {
                if (session.id !== sessionId) return session;
                const messages = session.messages.map((item, index) =>
                  index === session.messages.length - 1 && item.role === "assistant"
                    ? withReasoningSummary(item, token)
                    : item
                );
                return { ...session, messages };
              })
            );
          },
          onSessionTitle: ({ session_id: titledSessionId, title }) => {
            const normalized = title.trim();
            if (!normalized) return;
            setSessions((current) =>
              sortSessionsByNewest(
                current.map((session) => {
                  if (session.id !== titledSessionId) return session;
                  const metadata = (session.metadata ?? {}) as Record<string, unknown>;
                  return {
                    ...session,
                    title: normalized,
                    metadata: {
                      ...metadata,
                      title_source: session.is_modeling_3d ? "modeling_3d_prompt" : "openai",
                      is_empty_draft: false
                    }
                  };
                })
              )
            );
          },
          onError: (error) => {
            if (error.reason === "context_document_selection_required") {
              setContextDocsModalOpen(true);
            }
            const errorMessage = error.message ?? "Não consegui concluir a chamada ao provedor.";
            const errorStatus = {
              stage: "error",
              label: "Interrompido",
              detail: error.reason ?? errorMessage
            };
            setSessions((current) =>
              current.map((session) => {
                if (session.id !== sessionId) return session;
                const messages = session.messages.map((item, index) =>
                  index === session.messages.length - 1 && item.role === "assistant"
                    ? withRuntimeStatus({ ...item, content: item.content || errorMessage }, errorStatus)
                    : item
                );
                return { ...session, messages };
              })
            );
          },
          onDone: async () => {
            setSessions((current) =>
              current.map((session) => {
                if (session.id !== sessionId) return session;
                const messages = session.messages.map((item, index) =>
                  index === session.messages.length - 1 && item.role === "assistant"
                    ? withRuntimeStatus(item, { stage: "done", label: "Concluído" })
                    : item
                );
                return { ...session, messages };
              })
            );
            await refreshSessionSummaries();
          }
        }
      );
      setAttachedFiles([]);
      setAttachedPlatformFileIds([]);
      setAttachedDocumentIds([]);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Falha inesperada no chat.";
      const fallbackOptimisticUser =
        optimisticUser ??
        ({
          id: `user_${Date.now()}`,
          session_id: sessionId ?? "pending",
          role: "user",
          content: message,
          model_id: activeAgentModelLabel,
          created_at: new Date().toISOString()
        } as ChatMessage);
      const fallbackOptimisticAssistant =
        optimisticAssistant ?? localAssistantMessage(sessionId ?? "pending", optimisticStatus, reasoningSummary);
      const failedAssistant = withRuntimeStatus(
        { ...fallbackOptimisticAssistant, content: `Não consegui enviar a mensagem: ${errorMessage}` },
        { stage: "error", label: "Falha no envio", detail: errorMessage }
      );
      if (sessionId) {
        setSessions((current) =>
          current.map((session) => {
            if (session.id !== sessionId) return session;
            const hasOptimisticAssistant = session.messages.some((item) => item.id === fallbackOptimisticAssistant.id);
            return {
              ...session,
              messages: hasOptimisticAssistant
                ? session.messages.map((item) => (item.id === fallbackOptimisticAssistant.id ? failedAssistant : item))
                : [...session.messages, { ...fallbackOptimisticUser, session_id: session.id }, failedAssistant]
            };
          })
        );
      } else {
        const localSessionId = `local_error_${Date.now()}`;
        setActiveSessionId(localSessionId);
        setSessions((current) =>
          sortSessionsByNewest([
            {
              id: localSessionId,
              title: message.slice(0, 48),
              model_id: activeAgentModelLabel,
              agent_id: activeAgent?.id,
              project_id: activeSessionProjectId,
              folder_id: activeSessionFolderId,
              context_project_ids: normalizedContextProjectIds,
              context_document_ids: normalizedContextDocumentIds,
              context_knowledge_base_ids: normalizedContextKnowledgeBaseIds,
              is_modeling_3d: modeling3dPayload.enabled,
              modeling_software_preference: modeling3dPayload.software_override ?? "auto",
              modeling_stage: modeling3dPayload.enabled ? "discovery" : null,
              modeling_plan_id: null,
              archived: false,
              metadata: { is_empty_draft: false },
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
              messages: [
                { ...fallbackOptimisticUser, session_id: localSessionId },
                { ...failedAssistant, session_id: localSessionId }
              ]
            },
            ...current
          ])
        );
      }
    } finally {
      if (nextChatIs3D && !activeSessionIsModeling3D) {
        setModeling3dEnabled(false);
      }
      setIsStreaming(false);
    }
  }

  async function saveProviderKey(provider: ProviderName) {
    const apiKey = providerDrafts[provider]?.trim();
    if (!apiKey) return;
    const status = await api.saveProviderKey(provider, apiKey);
    setProviderStatuses((current) => current.map((item) => (item.provider === provider ? status : item)));
    setProviderDrafts((current) => ({ ...current, [provider]: "" }));
    setProviderEditMode((current) => ({ ...current, [provider]: false }));
    void refreshAppDataQuery();
  }

  async function clearProviderKey(provider: ProviderName) {
    const status = await api.deleteProviderKey(provider);
    setProviderStatuses((current) => current.map((item) => (item.provider === provider ? status : item)));
    setProviderDrafts((current) => ({ ...current, [provider]: "" }));
    setProviderEditMode((current) => ({ ...current, [provider]: false }));
    void refreshAppDataQuery();
  }

  async function loadProviderModels(provider: ProviderName) {
    setProviderCatalogState((current) => ({ ...current, [provider]: "loading" }));
    setProviderCatalogErrors((current) => ({ ...current, [provider]: "" }));
    try {
      const providerModels = await api.providerModels(provider);
      setProviderCatalogs((current) => ({ ...current, [provider]: providerModels }));
      setProviderCatalogState((current) => ({ ...current, [provider]: "ready" }));
    } catch (error) {
      setProviderCatalogState((current) => ({ ...current, [provider]: "error" }));
      setProviderCatalogErrors((current) => ({
        ...current,
        [provider]: error instanceof Error ? error.message : "Falha ao listar modelos"
      }));
    }
  }

  function editAgent(agent: Agent | null) {
    setAgentEditorKey((current) => current + 1);
    if (agent) {
      setEditingAgentId(agent.id);
      setAgentDraft({
        name: agent.name,
        description: agent.description,
        system_prompt: agent.system_prompt,
        model_id: agent.model_id ?? null,
        llm_config: llmConfigFromAgent(agent, models),
        enabled: agent.enabled,
        role: agent.role,
        collaboration_mode: agent.collaboration_mode,
        handoff_triggers: agent.handoff_triggers,
        tags: agent.tags,
        tools_allowed: agent.tools_allowed,
        allowed_project_ids: agent.allowed_project_ids,
        knowledge_base_ids: agent.knowledge_base_ids ?? []
      });
    } else {
      setEditingAgentId(null);
      setAgentDraft(createEmptyAgentDraft());
    }
    setActiveView("agents");
  }

  async function saveAgent() {
    if (!agentRequiredFieldsComplete(agentDraft)) return;
    const payload: AgentUpsert = {
      ...agentDraft,
      name: agentDraft.name.trim(),
      description: agentDraft.description.trim(),
      system_prompt: agentDraft.system_prompt.trim(),
      llm_config: normalizeLLMConfig(agentDraft.llm_config),
      tags: agentDraft.tags.map((tag) => tag.trim()).filter(Boolean),
      tools_allowed: agentDraft.tools_allowed.map((tool) => tool.trim()).filter(Boolean),
      allowed_project_ids:
        agentDraft.allowed_project_ids.length > 0
          ? agentDraft.allowed_project_ids.filter((projectId, index, list) => list.indexOf(projectId) === index)
          : [generalProjectId],
      knowledge_base_ids: agentDraft.knowledge_base_ids.filter(
        (knowledgeBaseId, index, list) =>
          list.indexOf(knowledgeBaseId) === index &&
          knowledgeBases.some((knowledgeBase) => knowledgeBase.id === knowledgeBaseId)
      ),
      handoff_triggers:
        agentDraft.role === "orchestrator"
          ? []
          : agentDraft.handoff_triggers.map((trigger) => trigger.trim()).filter(Boolean)
    };
    if (!agentRequiredFieldsComplete(payload)) return;
    const saved = editingAgentId ? await api.updateAgent(editingAgentId, payload) : await api.createAgent(payload);
    setAgents((current) => {
      if (current.some((agent) => agent.id === saved.id)) {
        return current.map((agent) => (agent.id === saved.id ? saved : agent));
      }
      return [saved, ...current];
    });
    setActiveAgentId(saved.id);
    setEditingAgentId(saved.id);
    setAgentDraft({
      name: saved.name,
      description: saved.description,
      system_prompt: saved.system_prompt,
      model_id: saved.model_id ?? null,
      llm_config: llmConfigFromAgent(saved, models),
      enabled: saved.enabled,
      role: saved.role,
      collaboration_mode: saved.collaboration_mode,
      handoff_triggers: saved.handoff_triggers,
      tags: saved.tags,
      tools_allowed: saved.tools_allowed,
      allowed_project_ids: saved.allowed_project_ids,
      knowledge_base_ids: saved.knowledge_base_ids ?? []
    });
    void refreshAppDataQuery();
  }

  function selectKnowledgeBase(knowledgeBase: KnowledgeBase) {
    setSelectedKnowledgeBaseId(knowledgeBase.id);
    setKnowledgeBaseDraft({
      name: knowledgeBase.name,
      description: knowledgeBase.description,
      scope: knowledgeBase.scope,
      color: knowledgeBase.color,
      tags: knowledgeBase.tags,
      max_documents_per_query: knowledgeBase.max_documents_per_query,
      max_chunks_per_document: knowledgeBase.max_chunks_per_document,
      enabled: knowledgeBase.enabled,
      metadata: knowledgeBase.metadata
    });
  }

  function startNewKnowledgeBase() {
    setSelectedKnowledgeBaseId(null);
    setKnowledgeBaseDraft(createDefaultKnowledgeBaseDraft());
  }

  async function saveKnowledgeBase() {
    const name = knowledgeBaseDraft.name.trim();
    if (!name) return;
    const payload: KnowledgeBaseUpsert = {
      ...knowledgeBaseDraft,
      name,
      description: knowledgeBaseDraft.description.trim(),
      scope: knowledgeBaseDraft.scope.trim(),
      tags: knowledgeBaseDraft.tags.map((tag) => tag.trim()).filter(Boolean),
      max_documents_per_query: Math.max(1, Math.min(20, knowledgeBaseDraft.max_documents_per_query || 8)),
      max_chunks_per_document: Math.max(1, Math.min(10, knowledgeBaseDraft.max_chunks_per_document || 3)),
      metadata: knowledgeBaseDraft.metadata ?? {}
    };
    const saved =
      selectedKnowledgeBaseId && knowledgeBases.some((knowledgeBase) => knowledgeBase.id === selectedKnowledgeBaseId)
        ? await api.updateKnowledgeBase(selectedKnowledgeBaseId, payload)
        : await api.createKnowledgeBase(payload);
    setKnowledgeBases((current) =>
      current.some((knowledgeBase) => knowledgeBase.id === saved.id)
        ? current.map((knowledgeBase) => (knowledgeBase.id === saved.id ? saved : knowledgeBase))
        : [saved, ...current]
    );
    selectKnowledgeBase(saved);
    void refreshAppDataQuery();
  }

  async function deleteKnowledgeBase(knowledgeBase: KnowledgeBase) {
    const confirmed = window.confirm(
      `Excluir a base "${knowledgeBase.name}"? Os arquivos e documentos continuam na plataforma.`
    );
    if (!confirmed) return;
    const deleted = await api.deleteKnowledgeBase(knowledgeBase.id);
    setKnowledgeBases((current) => current.filter((item) => item.id !== deleted.id));
    setKnowledgeBaseDocuments((current) => current.filter((item) => item.knowledge_base_id !== deleted.id));
    if (selectedKnowledgeBaseId === deleted.id) startNewKnowledgeBase();
    void refreshAppDataQuery();
  }

  async function removeDocumentFromKnowledgeBase(documentId: string) {
    if (!selectedKnowledgeBase) return;
    const removed = await api.removeKnowledgeBaseDocument(selectedKnowledgeBase.id, documentId);
    setKnowledgeBaseDocuments((current) => current.filter((item) => item.id !== removed.id));
    void refreshAppDataQuery();
  }

  async function indexTextDocument() {
    const content = documentContent.trim();
    if (!content || isIndexingDocument) return;
    setIsIndexingDocument(true);
    try {
      const title = documentTitle.trim() || content.slice(0, 42);
      const document = await api.createTextDocument({
        title,
        content,
        source_type: title.toLowerCase().endsWith(".md") ? "markdown" : "txt",
        category_id: null,
        folder_id: null,
        pinned: documentPinned,
        tags: csvToList(documentTags),
        project_id: generalProjectId
      });
      if (selectedKnowledgeBase) {
        const item = await api.addKnowledgeBaseDocument(selectedKnowledgeBase.id, {
          document_id: document.id,
          tags: document.tags,
          enabled: true
        });
        setKnowledgeBaseDocuments((current) => [item, ...current.filter((currentItem) => currentItem.id !== item.id)]);
      }
      setDocuments((current) => [document, ...current.filter((item) => item.id !== document.id)]);
      setDocumentTitle("");
      setDocumentContent("");
      setDocumentTags("");
      setDocumentPinned(false);
      void refreshAppDataQuery();
    } finally {
      setIsIndexingDocument(false);
    }
  }

  async function searchIndexedDocuments() {
    const query = documentQuery.trim();
    if (!query) return;
    const results = await api.searchDocuments({
      query,
      limit: 20,
      knowledge_base_ids: selectedKnowledgeBase ? [selectedKnowledgeBase.id] : []
    });
    setDocumentResults(results);
  }

  async function pollChatGPTImportJob(job: ChatGPTImportJob, sourceFilename: string) {
    let currentJob = job;
    setChatGPTImportJob(currentJob);
    while (currentJob.status === "pending" || currentJob.status === "running") {
      await delay(1500);
      currentJob = await api.chatGPTImportJob(currentJob.id);
      setChatGPTImportJob(currentJob);
    }
    if (currentJob.status === "completed" && currentJob.summary) {
      setChatGPTImportResult(currentJob.summary);
      await refreshAppDataQuery();
    } else {
      setChatGPTImportResult({
        source_filename: sourceFilename,
        conversations_found: currentJob.summary?.conversations_found ?? 0,
        sessions_imported: currentJob.summary?.sessions_imported ?? 0,
        sessions_skipped: currentJob.summary?.sessions_skipped ?? 0,
        messages_imported: currentJob.summary?.messages_imported ?? 0,
        messages_skipped: currentJob.summary?.messages_skipped ?? 0,
        errors: [currentJob.error ?? "Falha ao importar exportação."]
      });
    }
  }

  async function importChatGPTExport(file: File) {
    if (isImportingChatGPT) return;
    setIsImportingChatGPT(true);
    setChatGPTImportJob(null);
    setChatGPTImportResult(null);
    try {
      const job = await api.importChatGPTExport(file);
      await pollChatGPTImportJob(job, file.name);
    } catch (error) {
      setChatGPTImportResult({
        source_filename: file.name,
        conversations_found: 0,
        sessions_imported: 0,
        sessions_skipped: 0,
        messages_imported: 0,
        messages_skipped: 0,
        errors: [error instanceof Error ? error.message : "Falha ao importar exportação."]
      });
    } finally {
      setIsImportingChatGPT(false);
    }
  }

  async function importChatGPTExistingFile(platformFile: PlatformFile) {
    if (isImportingChatGPT) return;
    setIsImportingChatGPT(true);
    setChatGPTImportJob(null);
    setChatGPTImportResult(null);
    try {
      const job = await api.importChatGPTExistingFile(platformFile.id);
      await pollChatGPTImportJob(job, platformFileLabel(platformFile));
    } catch (error) {
      setChatGPTImportResult({
        source_filename: platformFileLabel(platformFile),
        conversations_found: 0,
        sessions_imported: 0,
        sessions_skipped: 0,
        messages_imported: 0,
        messages_skipped: 0,
        errors: [error instanceof Error ? error.message : "Falha ao importar exportação existente."]
      });
    } finally {
      setIsImportingChatGPT(false);
    }
  }

  async function uploadPlatformFiles(
    files: File[],
    options?: {
      source?: PlatformFile["source"];
      projectId?: string | null;
      folderId?: string | null;
      sessionId?: string | null;
    }
  ) {
    const uploaded = await Promise.all(
      files.map((file) =>
        api.uploadFile(file, options?.source ?? "upload", {
          project_id: options?.projectId ?? selectedKnowledgeProject?.id ?? null,
          folder_id: options?.folderId ?? selectedKnowledgeFolder?.id ?? null,
          session_id: options?.sessionId ?? null
        })
      )
    );
    setPlatformFiles((current) => [...uploaded, ...current]);
    void refreshAppDataQuery();
  }

  async function findDuplicateForUpload(file: File): Promise<PlatformFile | null> {
    const checksum = await sha256BrowserFile(file);
    if (!checksum) return null;
    return platformFiles.find((platformFile) => platformFile.checksum_sha256 === checksum) ?? null;
  }

  async function handleIncomingFiles(
    selectedFiles: File[],
    destination: DuplicateFileDestination,
    source: PlatformFile["source"] = "upload"
  ) {
    const filesToSend: File[] = [];
    const duplicates: PendingDuplicateFile[] = [];
    for (const file of selectedFiles) {
      const duplicate = await findDuplicateForUpload(file);
      if (duplicate) {
        duplicates.push({ file, duplicate, destination, source });
      } else {
        filesToSend.push(file);
      }
    }
    if (duplicates.length) {
      setDuplicateQueue((current) => [...current, ...duplicates]);
    }
    if (!filesToSend.length) return;
    if (destination === "chat") {
      setAttachedFiles((current) => [...current, ...filesToSend]);
    } else if (destination === "chatgpt_import") {
      void importChatGPTExport(filesToSend[0]);
    } else {
      void uploadPlatformFiles(filesToSend, {
        source,
        projectId: selectedKnowledgeProject?.id ?? null,
        folderId: selectedKnowledgeFolder?.id ?? null
      });
    }
  }

  function dismissDuplicateModal() {
    setDuplicateQueue((current) => current.slice(1));
  }

  function chooseExistingDuplicate(pending: PendingDuplicateFile) {
    if (pending.destination === "chat") {
      setAttachedPlatformFileIds((current) => [...new Set([...current, pending.duplicate.id])]);
    } else if (pending.destination === "chatgpt_import") {
      void importChatGPTExistingFile(pending.duplicate);
    } else {
      setActiveView("files");
    }
    dismissDuplicateModal();
  }

  function uploadDuplicateCopy(pending: PendingDuplicateFile) {
    if (pending.destination === "chat") {
      setAttachedFiles((current) => [...current, pending.file]);
    } else if (pending.destination === "chatgpt_import") {
      void importChatGPTExport(pending.file);
    } else {
      void uploadPlatformFiles([pending.file], {
        source: pending.source,
        projectId: selectedKnowledgeProject?.id ?? null,
        folderId: selectedKnowledgeFolder?.id ?? null
      });
    }
    dismissDuplicateModal();
  }

  async function updatePlatformFile(fileId: string, payload: PlatformFileUpdate) {
    const updated = await api.updateFile(fileId, payload);
    setPlatformFiles((current) => current.map((platformFile) => (platformFile.id === fileId ? updated : platformFile)));
    void refreshAppDataQuery();
  }

  async function deletePlatformFile(fileId: string) {
    const deleted = await api.deleteFile(fileId);
    setPlatformFiles((current) => current.filter((platformFile) => platformFile.id !== deleted.id));
    setAttachedPlatformFileIds((current) => current.filter((id) => id !== deleted.id));
    void refreshAppDataQuery();
  }

  async function createKnowledgeBaseFromFile(fileId: string) {
    const targetKnowledgeBase = selectedKnowledgeBase ?? knowledgeBases[0] ?? null;
    if (!targetKnowledgeBase) return;
    const document = await api.createDocumentFromFile({
      file_id: fileId,
      category_id: null,
      folder_id: null,
      pinned: false,
      tags: ["arquivo"],
      project_id: generalProjectId
    });
    const item = await api.addKnowledgeBaseDocument(targetKnowledgeBase.id, {
      document_id: document.id,
      tags: document.tags,
      enabled: true
    });
    if (!selectedKnowledgeBase) {
      setSelectedKnowledgeBaseId(targetKnowledgeBase.id);
    }
    setDocuments((current) => [document, ...current.filter((item) => item.id !== document.id)]);
    setKnowledgeBaseDocuments((current) => [item, ...current.filter((currentItem) => currentItem.id !== item.id)]);
    setActiveView("knowledge");
    void refreshAppDataQuery();
  }

  async function saveProject() {
    const name = projectDraft.name.trim();
    if (!name) {
      setProjectsStatus({ type: "error", message: "Informe o nome do projeto." });
      return;
    }
    const payload: ProjectUpsert = {
      ...projectDraft,
      name,
      description: projectDraft.description.trim(),
      context: {
        ...projectDraft.context,
        max_documents: 20
      }
    };
    try {
      const existing = selectedKnowledgeProject;
      const saved = existing ? await api.updateProject(existing.id, payload) : await api.createProject(payload);
      setProjects((current) => {
        const updated = current.some((project) => project.id === saved.id)
          ? current.map((project) => (project.id === saved.id ? saved : project))
          : [saved, ...current];
        return sortProjectsForUi(updated);
      });
      setSelectedKnowledgeProjectId(saved.id);
      setProjectsStatus({
        type: "success",
        message: existing ? "Projeto atualizado." : "Projeto criado com sucesso."
      });
      if (!existing) setProjectDraft(createDefaultProjectDraft());
      void refreshAppDataQuery();
    } catch (error) {
      setProjectsStatus({
        type: "error",
        message: error instanceof Error ? error.message : "Falha ao salvar projeto."
      });
    }
  }

  async function createProjectFolder() {
    if (!selectedKnowledgeProject) {
      setProjectsStatus({ type: "error", message: "Selecione um projeto para criar pastas." });
      return;
    }
    const name = folderDraftName.trim();
    if (!name) {
      setProjectsStatus({ type: "error", message: "Informe o nome da pasta." });
      return;
    }
    try {
      const created = await api.createProjectFolder({
        project_id: selectedKnowledgeProject.id,
        parent_id: folderDraftParentId,
        name
      });
      setProjectFolders((current) =>
        sortFoldersForUi([created, ...current.filter((folder) => folder.id !== created.id)])
      );
      setSelectedKnowledgeFolderId(created.id);
      setFolderDraftName("");
      setFolderDraftParentId(null);
      setProjectsStatus({ type: "success", message: "Pasta criada." });
      void refreshAppDataQuery();
    } catch (error) {
      setProjectsStatus({
        type: "error",
        message: error instanceof Error ? error.message : "Falha ao criar pasta."
      });
    }
  }

  async function saveChatKnowledgeBaseSelection(knowledgeBaseIds: string[]) {
    const normalizedIds = knowledgeBaseIds
      .filter((knowledgeBaseId, index, list) => list.indexOf(knowledgeBaseId) === index)
      .filter((knowledgeBaseId) => allowedRuntimeKnowledgeBaseIds.includes(knowledgeBaseId))
      .slice(0, 12);
    setChatContextKnowledgeBaseIds(normalizedIds);
    if (activeSession?.id) {
      const updated = await api.updateSessionContext(activeSession.id, {
        context_project_ids: normalizedContextProjectIds,
        context_document_ids: [],
        context_knowledge_base_ids: normalizedIds
      });
      setSessions((current) =>
        sortSessionsByNewest(
          current.map((session) =>
            session.id === updated.id ? { ...session, ...updated, messages: session.messages } : session
          )
        )
      );
    }
    setContextDocsModalOpen(false);
  }

  async function createChatInProject(projectId: string, folderId: string | null) {
    if (isCreatingProjectChat) return;
    setActiveView("chat");
    setIsCreatingProjectChat(true);
    try {
      const created = await api.createSession({
        title: "Novo chat",
        agent_id: activeAgent?.id ?? null,
        project_id: projectId,
        folder_id: folderId
      });
      setSessions((current) =>
        sortSessionsByNewest([
          { ...created, messages: created.messages ?? [] },
          ...current.filter((session) => session.id !== created.id)
        ])
      );
      setActiveSessionId(created.id);
      setChatProjectId(projectId);
      setChatProjectScopeMode("project_only");
      setChatContextProjectIds([projectId]);
      setChatContextDocumentIds([]);
      const project = projects.find((item) => item.id === projectId);
      setChatContextKnowledgeBaseIds(project?.context?.knowledge_base_ids ?? []);
      setSessionLazyState((current) => ({
        ...current,
        [created.id]: { hasMore: false, loadingOlder: false }
      }));
    } catch (error) {
      console.error(error);
    } finally {
      setIsCreatingProjectChat(false);
    }
  }

  async function createFolderFromExplorer(projectId: string, parentId: string | null) {
    const name = window.prompt("Nome da nova pasta:");
    if (!name || !name.trim()) return;
    try {
      const created = await api.createProjectFolder({
        project_id: projectId,
        parent_id: parentId,
        name: name.trim()
      });
      setProjectFolders((current) =>
        sortFoldersForUi([created, ...current.filter((folder) => folder.id !== created.id)])
      );
      void refreshAppDataQuery();
    } catch (error) {
      console.error(error);
    }
  }

  async function deleteFolderFromExplorer(folderId: string) {
    const confirmed = window.confirm(
      "Excluir esta pasta e todos os subitens? Todos os chats dentro dela também serão removidos."
    );
    if (!confirmed) return;
    try {
      const result = await api.deleteProjectFolder(folderId);
      const deletedIds = new Set(result.deleted_chat_session_ids);
      if (deletedIds.size > 0) {
        setSessions((current) => current.filter((session) => !deletedIds.has(session.id)));
      }
      setProjectFolders((current) => current.filter((folder) => !result.deleted_folder_ids.includes(folder.id)));
      void refreshAppDataQuery();
    } catch (error) {
      console.error(error);
    }
  }

  async function moveSessionInExplorer(sessionId: string, projectId: string, folderId: string | null) {
    try {
      const moved = await api.moveSession(sessionId, { project_id: projectId, folder_id: folderId });
      setSessions((current) =>
        sortSessionsByNewest(
          current.map((session) =>
            session.id === moved.id ? { ...session, ...moved, messages: session.messages } : session
          )
        )
      );
      void refreshAppDataQuery();
    } catch (error) {
      console.error(error);
    }
  }

  async function startNewChat() {
    if (isCreatingNewChat || isStreaming) return;
    setActiveView("chat");
    setDraft("");
    setAttachedFiles([]);
    setAttachedPlatformFileIds([]);
    setAttachedDocumentIds([]);
    setSupportAgentIds([]);
    setChatProjectId(generalProjectId);
    setChatProjectScopeMode("project_only");
    setChatContextProjectIds([generalProjectId]);
    setChatContextDocumentIds([]);
    setChatContextKnowledgeBaseIds(generalProject?.context?.knowledge_base_ids ?? []);
    setReasoningOverride("default");
    setDeepResearch(false);
    setDeepResearchMaxToolCalls(12);
    setResponseMode("text");
    setImageModelId(null);
    setReasoningSummary(false);
    setMultiAgentMode(false);
    resetModeling3dForNewChat();
    setShortcutMenuOpen(false);
    setShortcutSubmenu(null);
    setExecutionMenuOpen(false);
    setMobileMenuOpen(false);

    const existingDraft = sortSessionsByNewest(sessions).find(
      (session) => sessionHasEmptyDraft(session) && session.project_id === generalProjectId
    );
    if (existingDraft) {
      setActiveSessionId(existingDraft.id);
      setSessionLazyState((current) => ({
        ...current,
        [existingDraft.id]: current[existingDraft.id] ?? { hasMore: false, loadingOlder: false }
      }));
      return;
    }

    setIsCreatingNewChat(true);
    try {
      const created = await api.createSession({
        title: "Novo chat",
        agent_id: activeAgent?.id ?? null,
        project_id: generalProjectId
      });
      setSessions((current) =>
        sortSessionsByNewest([
          { ...created, messages: created.messages ?? [] },
          ...current.filter((session) => session.id !== created.id)
        ])
      );
      setActiveSessionId(created.id);
      setSessionLazyState((current) => ({
        ...current,
        [created.id]: { hasMore: false, loadingOlder: false }
      }));
    } catch {
      setActiveSessionId(null);
    } finally {
      setIsCreatingNewChat(false);
    }
  }

  async function deleteChatSession(session: ChatSession) {
    if (isStreaming || deletingSessionId) return;
    const confirmed = window.confirm(
      `Excluir o chat "${session.title}" e os arquivos relacionados?\n\nEssa ação não pode ser desfeita.`
    );
    if (!confirmed) return;

    setDeletingSessionId(session.id);
    try {
      const result = await api.deleteSession(session.id, true);
      const deletedFileIds = new Set(result.deleted_file_ids);
      let fallbackSessionId: string | null = null;
      setSessions((current) => {
        const remaining = sortSessionsByNewest(current.filter((currentSession) => currentSession.id !== session.id));
        fallbackSessionId = remaining[0]?.id ?? null;
        return remaining;
      });
      setSessionLazyState((current) => {
        const next = { ...current };
        delete next[session.id];
        return next;
      });
      if (activeSessionId === session.id) {
        setActiveSessionId(fallbackSessionId);
        setDraft("");
        setAttachedFiles([]);
        setAttachedPlatformFileIds([]);
        setAttachedDocumentIds([]);
      }
      if (deletedFileIds.size > 0) {
        setPlatformFiles((current) => current.filter((platformFile) => !deletedFileIds.has(platformFile.id)));
        setAttachedPlatformFileIds((current) => current.filter((fileId) => !deletedFileIds.has(fileId)));
      }
      void refreshAppDataQuery();
    } catch (error) {
      console.error(error);
    } finally {
      setDeletingSessionId(null);
    }
  }

  return (
    <div className="flex h-screen overflow-hidden bg-forge-ink text-forge-text">
      {mobileMenuOpen && (
        <button
          className="fixed inset-0 z-20 bg-black/50 md:hidden"
          onClick={() => setMobileMenuOpen(false)}
          aria-label="Fechar menu lateral"
          title="Fechar menu lateral"
        />
      )}
      {pendingDuplicateFile && (
        <DuplicateFileModal
          pending={pendingDuplicateFile}
          onUseExisting={() => chooseExistingDuplicate(pendingDuplicateFile)}
          onSendCopy={() => uploadDuplicateCopy(pendingDuplicateFile)}
          onCancel={dismissDuplicateModal}
        />
      )}
      {contextDocsModalOpen && (
        <ContextKnowledgeBasesModal
          key={`${activeSession?.id ?? "new"}:${normalizedContextProjectIds.join(",")}:${normalizedContextKnowledgeBaseIds.join(",")}`}
          open={contextDocsModalOpen}
          projects={projects}
          knowledgeBases={knowledgeBases.filter((knowledgeBase) =>
            allowedRuntimeKnowledgeBaseIds.includes(knowledgeBase.id)
          )}
          knowledgeBaseDocuments={knowledgeBaseDocuments}
          fileIndexingStatus={fileIndexingStatus}
          selectedProjectIds={normalizedContextProjectIds}
          initialSelectedKnowledgeBaseIds={normalizedContextKnowledgeBaseIds}
          onClose={() => setContextDocsModalOpen(false)}
          onSave={(knowledgeBaseIds) => void saveChatKnowledgeBaseSelection(knowledgeBaseIds)}
        />
      )}
      <EnableModeling3DDialog
        open={modelingEnableDialogOpen}
        software={modeling3dSoftware}
        onClose={() => setModelingEnableDialogOpen(false)}
        onConfirm={() => {
          setModeling3dEnabled(true);
          setModelingEnableDialogOpen(false);
          setExecutionMenuOpen(false);
        }}
        onSoftwareChange={setModeling3dSoftware}
      />
      {modelingDiagnosticsOpen && (
        <ModelingDiagnosticsModal
          open={modelingDiagnosticsOpen}
          planId={activeModelingPlanId}
          projectId={activeSessionProjectId}
          onClose={() => setModelingDiagnosticsOpen(false)}
        />
      )}

      <aside
        className={[
          "fixed inset-y-0 left-0 z-30 w-[286px] border-r border-forge-line bg-[#101111] transition-transform md:static md:translate-x-0",
          mobileMenuOpen ? "translate-x-0" : "-translate-x-full"
        ].join(" ")}
      >
        <div className="flex h-16 items-center justify-between border-b border-forge-line px-4">
          <div>
            <p className="text-sm text-forge-muted">Truth's Forge AI</p>
            <h1 className="flex items-center gap-2 text-lg font-semibold">
              <Sparkles size={18} className="text-forge-amber" />
              JUDITE
            </h1>
          </div>
          <Button
            className="h-9 w-9 px-0 md:hidden"
            onClick={() => setMobileMenuOpen(false)}
            aria-label="Fechar menu"
            title="Fechar menu"
          >
            <X size={18} />
          </Button>
        </div>

        <div className="scrollbar-slim h-[calc(100vh-64px)] space-y-4 overflow-y-auto p-4 pb-8">
          <Button
            className="w-full justify-start border-forge-amber/50 bg-[#171717] text-forge-text hover:border-forge-amber hover:bg-[#211d16]"
            onClick={() => void startNewChat()}
            disabled={isCreatingNewChat}
            aria-label="Novo chat"
            title="Novo chat"
          >
            {isCreatingNewChat ? <LoaderCircle size={15} className="animate-spin" /> : <MessageSquare size={15} />}
            {isCreatingNewChat ? "Criando..." : "Novo chat"}
          </Button>

          <div className="flex flex-col gap-1 rounded-md border border-forge-line bg-[#0e0f0e] p-1">
            <DashboardNavButton
              active={activeView === "chat"}
              icon={<MessageSquare size={15} />}
              label="Chat"
              onClick={() => {
                setActiveView("chat");
                setMobileMenuOpen(false);
              }}
            />
            <DashboardNavButton
              active={activeView === "agents"}
              icon={<Users size={15} />}
              label="Agentes"
              onClick={() => {
                if (!editingAgentId) editAgent(activeAgent ?? null);
                setActiveView("agents");
              }}
            />
            <DashboardNavButton
              active={activeView === "projects"}
              icon={<FolderTree size={15} />}
              label="Projetos"
              onClick={() => {
                setActiveView("projects");
                setMobileMenuOpen(false);
              }}
            />
            <DashboardNavButton
              active={activeView === "knowledge"}
              icon={<Database size={15} />}
              label="Bases"
              onClick={() => {
                setActiveView("knowledge");
                setMobileMenuOpen(false);
              }}
            />
            <DashboardNavButton
              active={activeView === "files"}
              icon={<FileText size={15} />}
              label="Arquivos"
              onClick={() => {
                setActiveView("files");
                setMobileMenuOpen(false);
              }}
            />
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs">
            <Metric label="Chats" value={sessions.length} />
            <Metric label="Prompts" value={prompts.length} />
          </div>

          <ProjectExplorerSection
            projects={nonGeneralProjects}
            folders={projectFolders}
            sessions={projectExplorerSessions}
            activeSessionId={activeSessionId}
            collapsed={projectExplorerCollapsed}
            expandedKeys={projectExplorerExpanded}
            onToggleCollapsed={() => setProjectExplorerCollapsed((current) => !current)}
            onToggleExpanded={(key) =>
              setProjectExplorerExpanded((current) => ({ ...current, [key]: !(current[key] ?? true) }))
            }
            onSelectSession={(sessionId) => {
              setActiveSessionId(sessionId);
              setActiveView("chat");
              setMobileMenuOpen(false);
            }}
            onCreateChat={(projectId, folderId) => void createChatInProject(projectId, folderId)}
            onCreateFolder={(projectId, parentId) => void createFolderFromExplorer(projectId, parentId)}
            onDeleteFolder={(folderId) => void deleteFolderFromExplorer(folderId)}
            onMoveSession={(sessionId, projectId, folderId) =>
              void moveSessionInExplorer(sessionId, projectId, folderId)
            }
            renderSessionBadge={(session) => (isModeling3DChat(session) ? <ChatModeling3DBadge compact /> : null)}
          />

          <HistorySection
            sessions={generalHistorySessions}
            activeSessionId={activeSessionId}
            collapsed={historyCollapsed}
            deletingSessionId={deletingSessionId}
            disabled={isStreaming}
            onToggleCollapsed={() => setHistoryCollapsed((current) => !current)}
            onSelectSession={(sessionId) => {
              setActiveSessionId(sessionId);
              setActiveView("chat");
              setMobileMenuOpen(false);
            }}
            onDeleteSession={(session) => void deleteChatSession(session)}
            renderSessionBadge={(session) => (isModeling3DChat(session) ? <ChatModeling3DBadge compact /> : null)}
          />
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 items-center justify-between border-b border-forge-line bg-[#0c0d0f]/95 px-4">
          <div className="flex min-w-0 items-center gap-3">
            <Button
              className="h-9 w-9 px-0 md:hidden"
              onClick={() => setMobileMenuOpen(true)}
              aria-label="Abrir menu"
              title="Abrir menu"
            >
              <Menu size={18} />
            </Button>
            <div className="min-w-0">
              <h2 className="flex min-w-0 items-center gap-2 truncate text-base font-semibold">
                {activeSessionIsModeling3D && <ChatModeling3DBadge />}
                <span className="truncate">
                  {activeView === "chat"
                    ? (activeSession?.title ?? "Novo chat com JUDITE")
                    : activeView === "agents"
                      ? "Dashboard de agentes"
                      : activeView === "projects"
                        ? "Projetos e contexto"
                        : activeView === "knowledge"
                          ? "Bases de conhecimento"
                          : "Arquivos da plataforma"}
                </span>
              </h2>
              <p className="truncate text-xs text-forge-muted">
                {activeView === "chat"
                  ? (activeAgent?.description ?? "Orquestração local-first")
                  : activeView === "agents"
                    ? "JUDITE, especialistas e configuração de LLM por agente"
                    : activeView === "projects"
                      ? "Estruture projetos, pastas e escopo de recuperação"
                      : activeView === "knowledge"
                        ? "Coleções curadas para RAG e agentes"
                        : "Uploads, imports e arquivos gerados"}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge className="hidden max-w-[260px] truncate md:inline-flex">{activeAgentModelLabel}</Badge>
            <Badge
              className={
                loadState === "ready" ? "border-forge-green text-forge-green" : "border-forge-red text-forge-red"
              }
            >
              <Wifi size={13} />
              {loadState === "ready" ? "Online" : "Offline"}
            </Badge>
          </div>
        </header>

        <div className="flex min-h-0 flex-1">
          {activeView === "chat" ? (
            <>
              <section className="flex min-w-0 flex-1 flex-col">
                <div
                  ref={chatScrollRef}
                  onScroll={handleChatScroll}
                  className="scrollbar-slim min-h-0 flex-1 overflow-y-auto px-4 py-5"
                >
                  <div className="mx-auto flex max-w-3xl flex-col gap-4">
                    {!!activeSession?.messages.length && activeSessionLazy?.hasMore && (
                      <div
                        ref={chatLoadOlderRef}
                        className="flex h-7 items-center justify-center text-xs text-forge-muted"
                      >
                        {activeSessionLazy.loadingOlder ? (
                          <span className="inline-flex items-center gap-2">
                            <LoaderCircle size={14} className="animate-spin" />
                            Carregando mensagens antigas...
                          </span>
                        ) : (
                          "Role para cima para carregar mais"
                        )}
                      </div>
                    )}
                    {(activeSession?.messages.length ? activeSession.messages : []).map((message) => (
                      <MessageBubble key={message.id} message={message} platformFilesById={platformFilesById} />
                    ))}

                    {!activeSession?.messages.length && (
                      <div className="mx-auto mt-12 w-full max-w-2xl">
                        <div className="mb-6 text-center">
                          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-md border border-forge-line bg-[#171716]">
                            <Bot size={28} className="text-forge-amber" />
                          </div>
                          <h3 className="text-xl font-semibold">Como posso ajudar agora?</h3>
                          <p className="mt-2 text-sm leading-6 text-forge-muted">
                            Escolha um ponto de partida ou escreva direto para a JUDITE.
                          </p>
                        </div>
                        <div className="grid gap-2 sm:grid-cols-2">
                          {quickActions.map((action) => (
                            <button
                              key={action}
                              className="min-h-12 rounded-md border border-forge-line bg-[#141615] px-3 py-2 text-left text-sm text-forge-text transition hover:border-forge-amber/60 hover:bg-[#1b1d1b]"
                              onClick={() => {
                                if (action.includes("agentes")) {
                                  editAgent(activeAgent ?? null);
                                  return;
                                }
                                setDraft(action);
                              }}
                            >
                              {action}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                <form onSubmit={handleSubmit} className="border-t border-forge-line bg-[#0c0d0f] p-3">
                  <div className="mx-auto max-w-3xl rounded-md border border-forge-line bg-[#171716] p-2">
                    <div className="mb-2 space-y-2 border-b border-forge-line pb-2">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex min-w-0 flex-1 flex-wrap gap-2">
                          <ContextChip label="Agente" value={activeAgent?.name ?? "Sem agente"} />
                          <ContextChip label="Projeto" value={`${contextProjectsLabel} · ${scopeModeLabel}`} />
                          <ContextChip label="Bases" value={selectedContextDocsLabel} />
                          <ContextChip
                            label="Execução"
                            value={executionLabels.length ? executionLabels.join(", ") : "padrão"}
                          />
                          {deepResearch && (
                            <label className="inline-flex h-8 items-center gap-2 rounded-md border border-forge-line bg-[#0e0f0e] px-2 text-xs text-forge-muted">
                              <span>Chamadas</span>
                              <input
                                type="number"
                                min={1}
                                max={100}
                                value={deepResearchMaxToolCalls}
                                onChange={(event) =>
                                  setDeepResearchMaxToolCalls(
                                    Math.max(1, Math.min(100, Number(event.target.value) || 1))
                                  )
                                }
                                className="h-6 w-14 rounded border border-forge-line bg-[#080908] px-2 text-forge-text"
                                aria-label="Limite de chamadas de ferramenta"
                                title="Limite de chamadas de ferramenta"
                              />
                            </label>
                          )}
                          {responseMode === "image" && (
                            <label className="inline-flex h-8 items-center gap-2 rounded-md border border-forge-line bg-[#0e0f0e] px-2 text-xs text-forge-muted">
                              <span>Modelo imagem</span>
                              <select
                                value={effectiveImageModel?.id ?? ""}
                                onChange={(event) => setImageModelId(event.target.value || null)}
                                className="h-6 min-w-44 rounded border border-forge-line bg-[#080908] px-2 text-forge-text"
                                aria-label="Modelo de geração de imagem"
                                title="Modelo de geração de imagem"
                              >
                                {!imageCapableModels.length && <option value="">Sem modelos de imagem</option>}
                                {imageCapableModels.map((model) => (
                                  <option key={model.id} value={model.id}>
                                    {model.display_name}
                                  </option>
                                ))}
                              </select>
                            </label>
                          )}
                          {activeSessionIsModeling3D && (
                            <Button
                              className="h-8 px-2 text-xs"
                              onClick={() => setModelingDiagnosticsOpen(true)}
                              aria-label="Abrir diagnóstico MCP 3D"
                              title="Abrir diagnóstico MCP 3D"
                            >
                              Diagnóstico 3D
                            </Button>
                          )}
                        </div>

                        <div className="flex items-center gap-1">
                          <div className="relative" ref={executionMenuRef}>
                            <Button
                              className="h-8 w-8 px-0"
                              onClick={() => setExecutionMenuOpen((current) => !current)}
                              aria-label="Menu de execução"
                              title="Menu de execução"
                            >
                              <Plus size={15} />
                            </Button>
                            {executionMenuOpen && (
                              <div
                                className="scrollbar-slim absolute right-0 z-50 max-h-[55vh] w-72 overflow-y-auto rounded-md border border-forge-line bg-[#111313] p-1 shadow-2xl"
                                style={{ top: "auto", bottom: "calc(100% + 4px)" }}
                              >
                                <ExecutionMenuItem
                                  label="MCP 3D"
                                  active={modeling3dEnabled}
                                  title="Usa o chat para criar plano estruturado Blender/Fusion via MCP."
                                  onClick={() => {
                                    setModelingEnableDialogOpen(true);
                                    setResponseMode("text");
                                    setDeepResearch(false);
                                    setReasoningSummary(false);
                                    setMultiAgentMode(false);
                                  }}
                                />
                                <ExecutionMenuItem
                                  label="Raciocínio longo"
                                  active={reasoningOverride === "long"}
                                  onClick={() =>
                                    setReasoningOverride((current) => (current === "long" ? "default" : "long"))
                                  }
                                />
                                <ExecutionMenuItem
                                  label="Resumo oficial"
                                  active={reasoningSummary}
                                  disabled={reasoningSummaryUnavailable}
                                  title={
                                    reasoningSummaryUnavailable
                                      ? "Disponível apenas para chat texto com modelo OpenAI."
                                      : "Solicita reasoning.summary=auto."
                                  }
                                  onClick={() => setReasoningSummary((current) => !current)}
                                />
                                <ExecutionMenuItem
                                  label="Pesquisa OpenAI"
                                  active={deepResearch}
                                  onClick={() => {
                                    setDeepResearch((current) => !current);
                                    setResponseMode("text");
                                    setReasoningSummary(false);
                                    if (!activeSessionIsModeling3D) setModeling3dEnabled(false);
                                  }}
                                />
                                <ExecutionMenuItem
                                  label="Imagem"
                                  active={responseMode === "image"}
                                  onClick={() => {
                                    setResponseMode((current) => (current === "image" ? "text" : "image"));
                                    setDeepResearch(false);
                                    setReasoningSummary(false);
                                    if (!activeSessionIsModeling3D) setModeling3dEnabled(false);
                                  }}
                                />
                                <ExecutionMenuItem
                                  label="Multiagente"
                                  active={multiAgentMode}
                                  onClick={() => {
                                    setMultiAgentMode((current) => !current);
                                    if (!activeSessionIsModeling3D) setModeling3dEnabled(false);
                                  }}
                                />
                                <button
                                  type="button"
                                  className="flex h-8 w-full items-center justify-between rounded px-2 text-xs text-forge-muted transition hover:bg-[#1b1f22] hover:text-forge-text"
                                  onClick={() => setContextDocsModalOpen(true)}
                                >
                                  <span>Editar bases de conhecimento atreladas</span>
                                </button>
                                <div className="mx-1 my-1 border-t border-forge-line" />
                                <button
                                  type="button"
                                  className="flex h-8 w-full items-center justify-between rounded px-2 text-xs text-forge-muted transition hover:bg-[#1b1f22] hover:text-forge-text"
                                  onClick={() => fileInputRef.current?.click()}
                                >
                                  <span className="flex items-center gap-2">
                                    <FileText size={14} />
                                    Anexar arquivo
                                  </span>
                                </button>
                              </div>
                            )}
                          </div>

                          <div className="relative" ref={shortcutMenuRef}>
                            <Button
                              className="h-8 w-8 px-0"
                              onClick={() => {
                                if (shortcutMenuOpen) {
                                  setShortcutMenuOpen(false);
                                  setShortcutSubmenu(null);
                                } else {
                                  setShortcutMenuOpen(true);
                                  setShortcutSubmenu("agent");
                                }
                              }}
                              aria-label="Menu rápido"
                              title="Menu rápido"
                            >
                              <EllipsisVertical size={15} />
                            </Button>
                            {shortcutMenuOpen && (
                              <div
                                className="absolute right-0 z-50 w-[460px] rounded-md border border-forge-line bg-[#111313] p-1 shadow-2xl"
                                style={{ top: "auto", bottom: "calc(100% + 4px)" }}
                              >
                                <div className="grid grid-cols-[170px_minmax(0,1fr)]">
                                  <div className="space-y-1 pr-1">
                                    <button
                                      type="button"
                                      className={[
                                        "flex h-8 w-full items-center justify-between rounded px-2 text-xs transition",
                                        shortcutSubmenu === "agent"
                                          ? "bg-[#1b1f22] text-forge-text"
                                          : "text-forge-muted hover:bg-[#1b1f22] hover:text-forge-text"
                                      ].join(" ")}
                                      onClick={() => setShortcutSubmenu("agent")}
                                    >
                                      <span>Agente</span>
                                      <ChevronRight size={13} />
                                    </button>
                                    <button
                                      type="button"
                                      className={[
                                        "flex h-8 w-full items-center justify-between rounded px-2 text-xs transition",
                                        shortcutSubmenu === "scope"
                                          ? "bg-[#1b1f22] text-forge-text"
                                          : "text-forge-muted hover:bg-[#1b1f22] hover:text-forge-text"
                                      ].join(" ")}
                                      onClick={() => setShortcutSubmenu("scope")}
                                    >
                                      <span>Projeto</span>
                                      <ChevronRight size={13} />
                                    </button>
                                  </div>

                                  <div className="scrollbar-slim max-h-[55vh] overflow-y-auto border-l border-forge-line pl-2">
                                    {shortcutSubmenu === "agent" && (
                                      <div className="space-y-1">
                                        {agents
                                          .filter((agent) => agent.enabled)
                                          .map((agent) => (
                                            <button
                                              key={agent.id}
                                              type="button"
                                              className="flex h-8 w-full items-center justify-between rounded px-2 text-xs text-forge-muted transition hover:bg-[#1b1f22] hover:text-forge-text"
                                              onClick={() => {
                                                setActiveAgentId(agent.id);
                                                setShortcutMenuOpen(false);
                                                setShortcutSubmenu(null);
                                              }}
                                            >
                                              <span className="truncate">{agent.name}</span>
                                              {activeAgent?.id === agent.id && (
                                                <Check size={13} className="text-forge-amber" />
                                              )}
                                            </button>
                                          ))}
                                      </div>
                                    )}

                                    {shortcutSubmenu === "scope" && (
                                      <div className="space-y-1">
                                        {availableContextProjects.map((project) => {
                                          const active = normalizedContextProjectIds[0] === project.id;
                                          return (
                                            <button
                                              key={project.id}
                                              type="button"
                                              className="flex h-8 w-full items-center justify-between rounded px-2 text-xs text-forge-muted transition hover:bg-[#1b1f22] hover:text-forge-text"
                                              onClick={() => {
                                                setChatProjectId(project.id);
                                                setChatContextProjectIds([project.id]);
                                                setChatContextKnowledgeBaseIds(
                                                  project.context.knowledge_base_ids ?? []
                                                );
                                                setShortcutMenuOpen(false);
                                                setShortcutSubmenu(null);
                                              }}
                                            >
                                              <span className="truncate">{projectDisplayName(project)}</span>
                                              {active && <Check size={13} className="text-forge-amber" />}
                                            </button>
                                          );
                                        })}
                                        <div className="px-2 pt-1 text-[11px] text-forge-muted">
                                          A conversa usa um projeto por vez. As pastas citadas com @ filtram a busca.
                                        </div>
                                        <button
                                          type="button"
                                          className="mt-1 flex h-8 w-full items-center justify-between rounded px-2 text-xs text-forge-muted transition hover:bg-[#1b1f22] hover:text-forge-text"
                                          onClick={() => setContextDocsModalOpen(true)}
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
                        </div>
                      </div>

                      {blockedByExecutionConfig && (
                        <p className="rounded-md border border-forge-red/50 bg-[#2a1112] px-2 py-1 text-xs text-forge-red">
                          {sendDisabledReason}
                        </p>
                      )}

                      <input
                        ref={fileInputRef}
                        type="file"
                        multiple
                        className="hidden"
                        onChange={(event) => {
                          const selected = Array.from(event.target.files ?? []);
                          if (selected.length) void handleIncomingFiles(selected, "chat", "chat_attachment");
                          event.target.value = "";
                        }}
                      />
                    </div>
                    {(attachedFiles.length > 0 ||
                      attachedPlatformFileIds.length > 0 ||
                      attachedDocumentIds.length > 0) && (
                      <div className="mb-2 flex flex-wrap gap-2 text-xs text-forge-muted">
                        {attachedFiles.map((file, index) => (
                          <button
                            key={`${file.name}:${file.size}:${index}`}
                            type="button"
                            className="inline-flex h-7 items-center gap-1 rounded-md border border-forge-line bg-[#0e0f0e] px-2 text-xs text-forge-muted transition hover:text-forge-text"
                            onClick={() =>
                              setAttachedFiles((current) => current.filter((_, itemIndex) => itemIndex !== index))
                            }
                            title={`Remover ${file.name}`}
                          >
                            <span className="max-w-40 truncate">{file.name}</span>
                            <X size={12} />
                          </button>
                        ))}
                        {attachedPlatformFileIds.map((fileId) => {
                          const platformFile = platformFiles.find((item) => item.id === fileId);
                          return (
                            <button
                              key={fileId}
                              type="button"
                              className="inline-flex h-7 items-center gap-1 rounded-md border border-forge-line bg-[#0e0f0e] px-2 text-xs text-forge-muted transition hover:text-forge-text"
                              onClick={() =>
                                setAttachedPlatformFileIds((current) => current.filter((itemId) => itemId !== fileId))
                              }
                              title={`Remover ${platformFile ? platformFileLabel(platformFile) : "arquivo"}`}
                            >
                              <span className="max-w-40 truncate">
                                {platformFile ? platformFileLabel(platformFile) : "arquivo"}
                              </span>
                              <X size={12} />
                            </button>
                          );
                        })}
                        {attachedDocumentIds.map((documentId) => (
                          <button
                            key={documentId}
                            type="button"
                            className="inline-flex h-7 items-center gap-1 rounded-md border border-forge-line bg-[#0e0f0e] px-2 text-xs text-forge-muted transition hover:text-forge-text"
                            onClick={() =>
                              setAttachedDocumentIds((current) => current.filter((itemId) => itemId !== documentId))
                            }
                            title={`Remover ${documents.find((document) => document.id === documentId)?.title ?? "contexto"}`}
                          >
                            <span className="max-w-40 truncate">
                              {documents.find((document) => document.id === documentId)?.title ?? "contexto"}
                            </span>
                            <X size={12} />
                          </button>
                        ))}
                      </div>
                    )}
                    {activeMention && mentionSuggestions.length > 0 && (
                      <div className="mb-2 rounded-md border border-forge-line bg-[#0f1011] p-1">
                        <div className="px-2 pb-1 pt-0.5 text-[11px] text-forge-muted">Pastas de contexto</div>
                        <div className="max-h-36 space-y-1 overflow-y-auto pr-1">
                          {mentionSuggestions.map((option) => (
                            <button
                              key={option.key}
                              type="button"
                              className="flex w-full items-center justify-between rounded px-2 py-1 text-left text-xs text-forge-muted transition hover:bg-[#1b1f22] hover:text-forge-text"
                              onClick={() => insertFolderMention(option)}
                            >
                              <span className="truncate">{option.label}</span>
                              <span className="ml-2 shrink-0 text-[10px] text-forge-amber">@</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                    <div className="flex items-end gap-2">
                      <textarea
                        ref={draftInputRef}
                        value={draft}
                        onChange={(event) => {
                          setDraft(event.target.value);
                          setDraftCursor(event.target.selectionStart ?? event.target.value.length);
                        }}
                        onClick={(event) => setDraftCursor((event.target as HTMLTextAreaElement).selectionStart ?? 0)}
                        onKeyUp={(event) => setDraftCursor((event.target as HTMLTextAreaElement).selectionStart ?? 0)}
                        rows={1}
                        placeholder={
                          loadState === "offline"
                            ? "Servidor indisponível"
                            : modeling3dEnabled
                              ? "Descreva o modelo 3D para Blender/Fusion via MCP"
                              : "Mensagem para JUDITE"
                        }
                        disabled={loadState === "offline"}
                        className="max-h-32 min-h-10 flex-1 resize-none bg-transparent px-2 py-2 text-sm text-forge-text placeholder:text-forge-muted focus:outline-none"
                      />
                      <span title={sendButtonTitle}>
                        <Button
                          type="submit"
                          className="h-10 w-10 px-0"
                          disabled={sendDisabled}
                          aria-label="Enviar"
                          title={sendButtonTitle}
                        >
                          {isStreaming ? <LoaderCircle size={18} className="animate-spin" /> : <Send size={18} />}
                        </Button>
                      </span>
                    </div>
                  </div>
                </form>
              </section>

              <aside className="hidden w-[360px] shrink-0 border-l border-forge-line bg-[#101111] p-4 lg:block">
                <div className="mb-4 grid grid-cols-5 gap-1 rounded-md border border-forge-line bg-[#0e0f0e] p-1">
                  <PanelButton
                    label="Contexto"
                    active={activePanel === "contexto"}
                    icon={<Activity size={15} />}
                    onClick={() => setActivePanel("contexto")}
                  />
                  <PanelButton
                    label="Infra"
                    active={activePanel === "infra"}
                    icon={<Server size={15} />}
                    onClick={() => setActivePanel("infra")}
                  />
                  <PanelButton
                    label="Auditoria"
                    active={activePanel === "auditoria"}
                    icon={<ShieldCheck size={15} />}
                    onClick={() => setActivePanel("auditoria")}
                  />
                  <PanelButton
                    label="Prompts"
                    active={activePanel === "prompts"}
                    icon={<Library size={15} />}
                    onClick={() => setActivePanel("prompts")}
                  />
                  <PanelButton
                    label="Configurações"
                    active={activePanel === "config"}
                    icon={<Settings2 size={15} />}
                    onClick={() => setActivePanel("config")}
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
                    <InfoRow label="Agentes" value={String(agents.length)} />
                    <InfoRow label="Prompts" value={String(prompts.length)} />
                    <InfoRow label="Documentos" value={String(documents.length)} />
                    <PanelTitle icon={<FileText size={18} />} title="RAG" />
                    <input
                      value={documentTitle}
                      onChange={(event) => setDocumentTitle(event.target.value)}
                      placeholder="Título"
                      className="h-9 rounded-md border border-forge-line bg-[#0e0f0e] px-3 text-sm text-forge-text"
                    />
                    <textarea
                      value={documentContent}
                      onChange={(event) => setDocumentContent(event.target.value)}
                      placeholder="Texto ou Markdown"
                      rows={5}
                      className="min-h-28 resize-none rounded-md border border-forge-line bg-[#0e0f0e] px-3 py-2 text-sm text-forge-text"
                    />
                    <Button
                      className="h-9 w-full"
                      onClick={() => void indexTextDocument()}
                      disabled={!documentContent.trim() || isIndexingDocument}
                    >
                      Indexar texto
                    </Button>
                    <div className="flex gap-2">
                      <input
                        value={documentQuery}
                        onChange={(event) => setDocumentQuery(event.target.value)}
                        placeholder="Buscar contexto"
                        className="h-9 min-w-0 flex-1 rounded-md border border-forge-line bg-[#0e0f0e] px-3 text-sm text-forge-text"
                      />
                      <Button
                        className="h-9"
                        onClick={() => void searchIndexedDocuments()}
                        disabled={!documentQuery.trim()}
                      >
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
                    <Modeling3DSettingsSection software={modeling3dSoftware} onSoftwareChange={setModeling3dSoftware} />
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
                            onClick={() =>
                              setProviderEditMode((current) => ({ ...current, [provider.provider]: true }))
                            }
                          >
                            Remover chave configurada?
                          </Button>
                        ) : (
                          <div className="flex gap-2">
                            <input
                              type="password"
                              value={providerDrafts[provider.provider] ?? ""}
                              onChange={(event) =>
                                setProviderDrafts((current) => ({
                                  ...current,
                                  [provider.provider]: event.target.value
                                }))
                              }
                              placeholder="Nova API key"
                              className="min-w-0 flex-1 rounded-md border border-forge-line bg-[#0e0f0e] px-3 text-sm text-forge-text"
                            />
                            <Button className="h-9" onClick={() => void saveProviderKey(provider.provider)}>
                              Salvar
                            </Button>
                            <Button
                              className="h-9 px-2"
                              onClick={() => void clearProviderKey(provider.provider)}
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
                    <Button className="h-9 w-full justify-start" onClick={() => editAgent(activeAgent ?? null)}>
                      <Users size={16} />
                      Abrir dashboard de agentes
                    </Button>
                  </PanelStack>
                )}
              </aside>
            </>
          ) : activeView === "agents" ? (
            <AgentDashboard
              key={agentEditorKey}
              agents={agents}
              projects={projects}
              knowledgeBases={knowledgeBases}
              generalProjectId={generalProjectId}
              activeAgent={activeAgent}
              supportAgentIds={supportAgentIds}
              agentDraft={agentDraft}
              editingAgentId={editingAgentId}
              providerCatalogs={providerCatalogs}
              providerCatalogState={providerCatalogState}
              providerCatalogErrors={providerCatalogErrors}
              onSelectAgent={(agent) => {
                setActiveAgentId(agent.id);
                editAgent(agent);
              }}
              onCreateAgent={() => editAgent(null)}
              onSetAgentDraft={setAgentDraft}
              onSaveAgent={() => void saveAgent()}
              onSetActiveAgentId={setActiveAgentId}
              onToggleSupportAgent={(agentId, enabled) =>
                setSupportAgentIds((current) =>
                  enabled ? [...new Set([...current, agentId])] : current.filter((id) => id !== agentId)
                )
              }
              onLoadProviderModels={(provider) => void loadProviderModels(provider)}
            />
          ) : activeView === "projects" ? (
            <ProjectsDashboard
              projects={projects}
              folders={projectFolders}
              knowledgeBases={knowledgeBases}
              knowledgeBaseDocuments={knowledgeBaseDocuments}
              selectedProject={selectedKnowledgeProject}
              selectedFolderId={selectedKnowledgeFolderId}
              projectDraft={projectDraft}
              folderDraftName={folderDraftName}
              folderDraftParentId={folderDraftParentId}
              status={projectsStatus}
              onSelectProject={(projectId) => {
                setSelectedKnowledgeProjectId(projectId);
                setSelectedKnowledgeFolderId(null);
              }}
              onSelectFolder={setSelectedKnowledgeFolderId}
              onSetProjectDraft={setProjectDraft}
              onSetFolderDraftName={setFolderDraftName}
              onSetFolderDraftParentId={setFolderDraftParentId}
              onSaveProject={() => void saveProject()}
              onCreateFolder={() => void createProjectFolder()}
            />
          ) : activeView === "files" ? (
            <FilesDashboard
              documents={documents}
              onUploadFiles={(files) => void handleIncomingFiles(files, "library", "upload")}
              onCreateKnowledgeBaseFromFile={(fileId) => void createKnowledgeBaseFromFile(fileId)}
              onUpdateFile={(fileId, payload) => void updatePlatformFile(fileId, payload)}
              onDeleteFile={(fileId) => void deletePlatformFile(fileId)}
            />
          ) : (
            <KnowledgeDashboard
              knowledgeBases={knowledgeBases}
              knowledgeBaseDocuments={knowledgeBaseDocuments}
              selectedKnowledgeBase={selectedKnowledgeBase}
              selectedDocuments={selectedKnowledgeBaseDocuments}
              knowledgeBaseDraft={knowledgeBaseDraft}
              documentTitle={documentTitle}
              documentContent={documentContent}
              documentTags={documentTags}
              documentPinned={documentPinned}
              documentQuery={documentQuery}
              documentResults={documentResults}
              chatGPTImportJob={chatGPTImportJob}
              chatGPTImportResult={chatGPTImportResult}
              isIndexingDocument={isIndexingDocument}
              isImportingChatGPT={isImportingChatGPT}
              onSelectKnowledgeBase={selectKnowledgeBase}
              onSetKnowledgeBaseDraft={setKnowledgeBaseDraft}
              onCreateKnowledgeBase={startNewKnowledgeBase}
              onSaveKnowledgeBase={() => void saveKnowledgeBase()}
              onDeleteKnowledgeBase={(knowledgeBase) => void deleteKnowledgeBase(knowledgeBase)}
              onSetDocumentTitle={setDocumentTitle}
              onSetDocumentContent={setDocumentContent}
              onSetDocumentTags={setDocumentTags}
              onSetDocumentPinned={setDocumentPinned}
              onIndexTextDocument={() => void indexTextDocument()}
              onSetDocumentQuery={setDocumentQuery}
              onSearchDocuments={() => void searchIndexedDocuments()}
              onImportChatGPTExport={(file) => void handleIncomingFiles([file], "chatgpt_import", "chatgpt_import")}
              onUploadPlatformFiles={(files) => void handleIncomingFiles(files, "library", "knowledge_base")}
              onCreateKnowledgeBaseFromFile={(fileId) => void createKnowledgeBaseFromFile(fileId)}
              onRemoveDocumentFromKnowledgeBase={(documentId) => void removeDocumentFromKnowledgeBase(documentId)}
              onUseDocument={(content) => setDraft((current) => `${current}${current ? "\n\n" : ""}${content}`)}
            />
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
