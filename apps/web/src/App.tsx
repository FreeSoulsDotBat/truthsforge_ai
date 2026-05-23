import type { FormEvent } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useShallow } from "zustand/react/shallow";

import { useAppDataBootstrap } from "./app/hooks/use-app-data-bootstrap";
import { useDocumentDraft } from "./app/hooks/use-document-draft";
import { useProviderSettings } from "./app/hooks/use-provider-settings";
import { useChatScopeSync } from "./app/hooks/use-chat-scope-sync";
import { useKnowledgeScopeSync, type ProjectsStatus } from "./app/hooks/use-knowledge-scope-sync";
import { useOutsidePointerClose } from "./app/hooks/use-outside-pointer-close";
import { quickActions } from "./app/constants";
import { appDataQueryKey, fetchAppDataSnapshot } from "./app/queries/app-data";
import { useAppStore } from "./app/store";
import type { DashboardView, LoadState } from "./app/ui-state";
import { AppHeader } from "./components/AppHeader";
import { ChatComposerInput } from "./features/chat/components/ChatComposerInput";
import { ChatMessageList } from "./features/chat/components/ChatMessageList";
import { ChatRightPanel } from "./features/chat/components/ChatRightPanel";
import { ComposerAttachments } from "./features/chat/components/ComposerAttachments";
import { ComposerContextChips } from "./features/chat/components/ComposerContextChips";
import { ExecutionMenu } from "./features/chat/components/ExecutionMenu";
import { ShortcutMenu } from "./features/chat/components/ShortcutMenu";
import { DuplicateFileModal } from "./components/app-panels";
import { AppSidebar } from "./components/AppSidebar";
import { api, ChatStreamHttpError, streamChat } from "./lib/api";
import {
  agentRequiredFieldsComplete,
  createEmptyAgentDraft,
  llmConfigFromAgent,
  normalizeLLMConfig
} from "./features/agents/agent-domain";
import {
  initialAssistantStatus,
  normalizeRequiredChatTitle,
  localAssistantMessage,
  messageMetadata,
  normalizeStreamExecutionModes,
  withModelingPlan,
  withReasoningSummary,
  withRuntimeStatus
} from "./features/chat/chat-domain";
import {
  CONTEXT_MODAL_SEEN_PROJECTS_STORAGE_KEY,
  DOCUMENT_SNAPSHOT_PAGE_SIZE,
  createChatAttachmentPreview,
  createDefaultKnowledgeBaseDraft,
  findMentionMatch,
  loadSeenContextModalProjectIds,
  mergeUniqueMessages,
  normalizeMentionPart,
  nowIso,
  optimisticId,
  sessionHasEmptyDraft,
  sha256BrowserFile,
  type MentionOption,
  type SessionLazyMeta
} from "./features/chat/chat-helpers";
import { ChatTitleRequiredDialog } from "./features/chat/components/ChatTitleRequiredDialog";
import { useChatTitleGate } from "./features/chat/hooks/useChatTitleGate";
import {
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
import { EnableModeling3DDialog, ModelingDiagnosticsModal } from "./features/modeling-3d/components";
import { isModeling3DChat } from "./features/modeling-3d/chat-domain";
import { modeling3dApi } from "./features/modeling-3d";
import { useModeling3dChat, useModelingPlanActions } from "./features/modeling-3d/hooks";
import type { ModelingPlanCardActions } from "./components/app-chat";
import { useModeling3DStore } from "./features/modeling-3d/store";
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
  ModelConfig,
  ModelingPlan,
  ModelingPlanEdit,
  PlatformFile,
  PlatformFileIndexingStatus,
  PlatformFileUpdate,
  ProjectFolder,
  ProjectRecord,
  ProjectUpsert,
  ProviderSecretStatus,
  Prompt,
  ServerStatus
} from "./types/api";

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
  const modelingPlanActionsRuntime = useModelingPlanActions();
  const modelingDiagnosticsOpen = useModeling3DStore((state) => state.diagnosticsOpen);
  const setModelingDiagnosticsOpen = useModeling3DStore((state) => state.setDiagnosticsOpen);
  const modelingEnableDialogOpen = useModeling3DStore((state) => state.enableDialogOpen);
  const setModelingEnableDialogOpen = useModeling3DStore((state) => state.setEnableDialogOpen);
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
  const {
    documentTitle,
    setDocumentTitle,
    documentContent,
    setDocumentContent,
    documentTags,
    setDocumentTags,
    documentPinned,
    setDocumentPinned,
    documentQuery,
    setDocumentQuery,
    documentResults,
    setDocumentResults,
    resetDraft: resetDocumentDraft
  } = useDocumentDraft();
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

  const {
    providerDrafts,
    setProviderDrafts,
    providerEditMode,
    setProviderEditMode,
    providerCatalogs,
    providerCatalogState,
    providerCatalogErrors,
    saveProviderKey,
    clearProviderKey,
    loadProviderModels
  } = useProviderSettings({
    onProviderStatus: (provider, status) =>
      setProviderStatuses((current) => current.map((item) => (item.provider === provider ? status : item))),
    refresh: () => void refreshAppDataQuery()
  });

  // Derived during render (no effect): mirrors the bootstrap query status so the
  // React Compiler's `set-state-in-effect` rule has nothing to flag here.
  const loadState: LoadState = appDataQuery.isPending
    ? "loading"
    : appDataQuery.isError
      ? "offline"
      : appDataQuery.data
        ? "ready"
        : "idle";

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

  // Distributes the bootstrap snapshot into state and keeps the active
  // selections valid. See `useAppDataBootstrap` for why the local mirrors are
  // reconciled during render while the store selections are deferred.
  useAppDataBootstrap({
    snapshot: appDataQuery.data,
    activeSessionId,
    chatProjectId,
    mergeSessionSummaries,
    setStatus,
    setModels,
    setAgents,
    setPrompts,
    setDocuments,
    setKnowledgeBases,
    setKnowledgeBaseDocuments,
    setPlatformFiles,
    setFileIndexingStatus,
    setProjects,
    setProjectFolders,
    setAuditEvents,
    setCostPolicy,
    setCostUsage,
    setProviderStatuses,
    setSelectedKnowledgeBaseId,
    setFolderDraftParentId,
    setActiveSessionId,
    setActiveAgentId,
    setSupportAgentIds,
    setSelectedKnowledgeProjectId,
    setSelectedKnowledgeFolderId,
    setChatProjectId,
    setChatProjectScopeMode
  });

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
  const chatTitleGate = useChatTitleGate(activeSession);
  const activeSessionIsModeling3D = isModeling3DChat(activeSession);
  const modeling3dEnabled = nextChatIs3D || activeSessionIsModeling3D;
  const activeModelingPlanId = activeSession?.modeling_plan_id ?? null;

  const applyChatTitleToSession = useCallback((sessionId: string, title: string) => {
    const normalizedTitle = normalizeRequiredChatTitle(title);
    if (!normalizedTitle) return;
    setSessions((current) =>
      sortSessionsByNewest(
        current.map((session) => {
          if (session.id !== sessionId) return session;
          const metadata = (session.metadata ?? {}) as Record<string, unknown>;
          return {
            ...session,
            title: normalizedTitle,
            metadata: {
              ...metadata,
              title_source: "manual"
            },
            updated_at: nowIso()
          };
        })
      )
    );
  }, []);

  // Onda 4.4 — mirror approve/reject/retry/revise outcomes from
  // useModelingPlanActions onto the local session graph so the
  // ModelingPlanCard reflects the new status / kind without a refetch.
  // We don't yet receive a dedicated SSE stream for plan execution;
  // until that arrives the hook is the single source of truth.
  const applyPlanToSession = useCallback(
    (plan: ModelingPlan, nextStage: ChatSession["modeling_stage"]) => {
      setSessions((current) =>
        current.map((session) => {
          if (session.id !== plan.conversation_id) return session;
          const messages = session.messages.map((message) =>
            messageMetadata(message).modeling_plan?.id === plan.id ? withModelingPlan(message, plan) : message
          );
          return {
            ...session,
            modeling_stage: nextStage,
            modeling_plan_id: nextStage === "discovery" ? null : (plan.id ?? session.modeling_plan_id),
            messages
          };
        })
      );
    },
    [setSessions]
  );

  const handleApproveModelingPlan = useCallback(
    async (planId: string) => {
      const execution = await modelingPlanActionsRuntime.approve(planId);
      if (!execution) return;
      const next = execution.plan.status === "failed" ? "editing" : "editing";
      applyPlanToSession(execution.plan, next);
    },
    [applyPlanToSession, modelingPlanActionsRuntime]
  );

  const handleRejectModelingPlan = useCallback(
    async (planId: string, reason: string) => {
      const rejected = await modelingPlanActionsRuntime.reject(planId, reason);
      if (!rejected) return;
      applyPlanToSession(rejected, "discovery");
    },
    [applyPlanToSession, modelingPlanActionsRuntime]
  );

  const handleRetryModelingPlan = useCallback(
    async (planId: string) => {
      const execution = await modelingPlanActionsRuntime.retry(planId);
      if (!execution) return;
      applyPlanToSession(execution.plan, "editing");
    },
    [applyPlanToSession, modelingPlanActionsRuntime]
  );

  const handleReviseModelingPlan = useCallback(
    async (planId: string) => {
      const rejected = await modelingPlanActionsRuntime.revise(planId);
      if (!rejected) return;
      applyPlanToSession(rejected, "discovery");
    },
    [applyPlanToSession, modelingPlanActionsRuntime]
  );

  const handleEditModelingPlan = useCallback(
    async (planId: string, payload: ModelingPlanEdit) => {
      const edited = await modelingPlanActionsRuntime.edit(planId, payload);
      if (!edited) return;
      applyPlanToSession(edited, "planning");
    },
    [applyPlanToSession, modelingPlanActionsRuntime]
  );

  const modelingPlanActions = useMemo<ModelingPlanCardActions>(
    () => ({
      onApprove: handleApproveModelingPlan,
      onReject: handleRejectModelingPlan,
      onRetry: handleRetryModelingPlan,
      onRevise: handleReviseModelingPlan,
      onEditPlan: handleEditModelingPlan,
      isBusy: modelingPlanActionsRuntime.busy
    }),
    [
      handleApproveModelingPlan,
      handleRejectModelingPlan,
      handleRetryModelingPlan,
      handleReviseModelingPlan,
      handleEditModelingPlan,
      modelingPlanActionsRuntime.busy
    ]
  );
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
  // Pure derivation from the draft + cursor (was a `setActiveMention` effect).
  const activeMention = useMemo(() => findMentionMatch(draft, draftCursor), [draft, draftCursor]);
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

  // `reasoningSummary` lives in the zustand store, so it can't be set during
  // render; the guard stays in an effect but defers the write to a microtask to
  // keep the `set-state-in-effect` rule satisfied.
  useEffect(() => {
    if (reasoningSummary && reasoningSummaryUnavailable) {
      queueMicrotask(() => setReasoningSummary(false));
    }
  }, [reasoningSummary, reasoningSummaryUnavailable, setReasoningSummary]);

  // `knowledgeBaseDraft` is local state reset whenever the selected base changes.
  // Reconciled during render (guarded on the selected-base reference) instead of
  // in an effect.
  const [knowledgeBaseDraftSource, setKnowledgeBaseDraftSource] = useState<KnowledgeBase | null>(null);
  if (selectedKnowledgeBase !== knowledgeBaseDraftSource) {
    setKnowledgeBaseDraftSource(selectedKnowledgeBase);
    setKnowledgeBaseDraft(
      selectedKnowledgeBase
        ? {
            name: selectedKnowledgeBase.name,
            description: selectedKnowledgeBase.description,
            scope: selectedKnowledgeBase.scope,
            color: selectedKnowledgeBase.color,
            tags: selectedKnowledgeBase.tags,
            max_documents_per_query: selectedKnowledgeBase.max_documents_per_query,
            max_chunks_per_document: selectedKnowledgeBase.max_chunks_per_document,
            enabled: selectedKnowledgeBase.enabled,
            metadata: selectedKnowledgeBase.metadata
          }
        : createDefaultKnowledgeBaseDraft()
    );
  }

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

  // `imageModelId` is store state, so its validity reconcile stays in an effect
  // with deferred (microtask) writes rather than running during render.
  useEffect(() => {
    if (!imageCapableModels.length) {
      if (imageModelId !== null) queueMicrotask(() => setImageModelId(null));
      return;
    }
    if (imageModelId && imageCapableModels.some((model) => model.id === imageModelId)) {
      return;
    }
    const nextImageModelId = defaultImageModel?.id ?? imageCapableModels[0]?.id ?? null;
    queueMicrotask(() => setImageModelId(nextImageModelId));
  }, [defaultImageModel, imageCapableModels, imageModelId, setImageModelId]);

  // The cursor restore is a genuine DOM effect (focus must run after render); the
  // `draftCursor` mirror is deferred to an animation frame so it isn't a
  // synchronous `setState` in the effect body.
  useEffect(() => {
    const pendingCursor = pendingCursorRef.current;
    const input = draftInputRef.current;
    if (pendingCursor === null || !input) return;
    pendingCursorRef.current = null;
    input.focus();
    input.setSelectionRange(pendingCursor, pendingCursor);
    const frame = requestAnimationFrame(() => setDraftCursor(pendingCursor));
    return () => cancelAnimationFrame(frame);
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

  // Load the active session's saved context into local state when the session
  // (or the general-project fallback) changes. Reconciled during render and
  // guarded on the session *id* (not its object reference) so streaming message
  // updates no longer re-clobber the user's in-session context picks.
  const [chatContextSourceKey, setChatContextSourceKey] = useState<string | null>(null);
  if (activeSession) {
    const nextContextSourceKey = `${activeSession.id}|${generalProjectId}`;
    if (nextContextSourceKey !== chatContextSourceKey) {
      setChatContextSourceKey(nextContextSourceKey);
      const fallbackProjectId = activeSession.project_id ?? generalProjectId;
      const incomingProjectIds =
        activeSession.context_project_ids.length > 0 ? activeSession.context_project_ids : [fallbackProjectId];
      setChatContextProjectIds(incomingProjectIds.slice(0, 1));
      setChatContextDocumentIds((activeSession.context_document_ids ?? []).slice(0, 20));
      setChatContextKnowledgeBaseIds(activeSession.context_knowledge_base_ids ?? []);
    }
  }

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(CONTEXT_MODAL_SEEN_PROJECTS_STORAGE_KEY, JSON.stringify(contextModalSeenProjectIds));
    } catch {
      // Ignore localStorage persistence errors (private mode / quota).
    }
  }, [contextModalSeenProjectIds]);

  // Auto-open the context modal once per project the user hasn't acknowledged.
  // Local state only, so it runs during render; self-converges once the modal is
  // open and the projects are marked seen.
  if (activeView === "chat" && normalizedContextProjectIds.length > 0 && !contextDocsModalOpen) {
    const seenSet = new Set(contextModalSeenProjectIds);
    const unseenProjectIds = normalizedContextProjectIds.filter((projectId) => !seenSet.has(projectId));
    if (unseenProjectIds.length > 0) {
      setContextModalSeenProjectIds((current) => Array.from(new Set([...current, ...unseenProjectIds])));
      setContextDocsModalOpen(true);
    }
  }

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
      // `activeMention` is now derived from draft+cursor; completing the mention
      // (trailing space) makes it recompute to null, so no manual reset is needed.
    },
    [activeMention, draft]
  );

  function handleSelectView(view: DashboardView) {
    if (view === "agents") {
      if (!editingAgentId) editAgent(activeAgent ?? null);
      setActiveView("agents");
      return;
    }
    setActiveView(view);
    setMobileMenuOpen(false);
  }

  function handleSelectSidebarSession(sessionId: string) {
    setActiveSessionId(sessionId);
    setActiveView("chat");
    setMobileMenuOpen(false);
  }

  function handleQuickAction(action: string) {
    if (action.includes("agentes")) {
      editAgent(activeAgent ?? null);
      return;
    }
    setDraft(action);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = draft.trim();
    if (!message || isStreaming) return;
    const confirmedTitle = chatTitleGate.needsTitle
      ? await chatTitleGate.openTitleDialog(activeSession?.title)
      : normalizeRequiredChatTitle(activeSession?.title);
    if (chatTitleGate.needsTitle && !confirmedTitle) return;
    const streamTitle = confirmedTitle || normalizeRequiredChatTitle(activeSession?.title) || undefined;
    if (streamTitle && activeSession?.id) {
      applyChatTitleToSession(activeSession.id, streamTitle);
    }
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
    const streamExecutionModes = normalizeStreamExecutionModes({
      reasoningOverride,
      deepResearch,
      responseMode,
      reasoningSummary,
      multiAgentMode,
      modeling3d: modeling3dPayload
    });
    const optimisticStatus = initialAssistantStatus({
      reasoningOverride: streamExecutionModes.reasoningOverride,
      deepResearch: streamExecutionModes.deepResearch,
      responseMode: streamExecutionModes.responseMode,
      multiAgentMode: streamExecutionModes.multiAgentMode,
      reasoningSummary: streamExecutionModes.reasoningSummary,
      modeling3dEnabled: streamExecutionModes.modeling3dEnabled
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
        id: optimisticId("user"),
        session_id: sessionId ?? "pending",
        role: "user",
        content: message,
        model_id: activeAgentModelLabel,
        metadata: {
          attached_document_ids: attachedDocumentIds,
          attached_file_ids: uploadedFileIds,
          attached_files: attachedPreviews
        },
        created_at: nowIso()
      };
      optimisticAssistant = localAssistantMessage(
        sessionId ?? "pending",
        optimisticStatus,
        streamExecutionModes.reasoningSummary
      );

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
          title: streamTitle,
          agent_id: activeAgent?.id,
          agent_ids: runtimeSupportAgents.map((agent) => agent.id),
          project_id: chatProjectId,
          folder_id: activeSessionFolderId,
          project_scope_mode: chatProjectScopeMode,
          context_project_ids: normalizedContextProjectIds,
          context_document_ids: normalizedContextDocumentIds,
          context_knowledge_base_ids: normalizedContextKnowledgeBaseIds,
          reasoning_override: streamExecutionModes.reasoningOverride,
          deep_research: streamExecutionModes.deepResearch,
          deep_research_max_tool_calls: deepResearchMaxToolCalls,
          response_mode: streamExecutionModes.responseMode,
          image_model_id:
            streamExecutionModes.responseMode === "image" ? (effectiveImageModel?.id ?? undefined) : undefined,
          reasoning_summary: streamExecutionModes.reasoningSummary ? "auto" : "off",
          multi_agent_mode: streamExecutionModes.multiAgentMode,
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
                  id: optimisticId("user"),
                  session_id: meta.session_id,
                  role: "user",
                  content: message,
                  model_id: activeAgentModelLabel,
                  created_at: nowIso()
                };
            const resolvedAssistantMessage: ChatMessage = optimisticAssistant
              ? { ...optimisticAssistant, id: meta.message_id, session_id: meta.session_id }
              : {
                  ...localAssistantMessage(meta.session_id, optimisticStatus, streamExecutionModes.reasoningSummary),
                  id: meta.message_id,
                  session_id: meta.session_id
                };
            setSessions((current) => {
              if (current.some((session) => session.id === meta.session_id)) return current;
              return sortSessionsByNewest([
                {
                  id: meta.session_id,
                  title: streamTitle ?? message.slice(0, 48),
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
                  metadata: {
                    is_empty_draft: false,
                    ...(streamTitle ? { title_source: "manual" } : {}),
                    ...(modeling3dPayload.enabled ? { modeling_3d: modeling3dPayload } : {})
                  },
                  created_at: nowIso(),
                  updated_at: nowIso(),
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
            if (error.reason === "chat_title_required") {
              return;
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
            if (sessionId) {
              await loadSessionPage(sessionId).catch(() => undefined);
            }
            await refreshSessionSummaries();
          }
        }
      );
      setAttachedFiles([]);
      setAttachedPlatformFileIds([]);
      setAttachedDocumentIds([]);

      // Onda 4.3 — when the chat is marked as 3D and the user attached
      // image/3D files alongside the message, fire the attachment
      // analyzer in the background. Each successful analysis is posted
      // back to the session as a local assistant note so the agent
      // (and the user) can read the structured summary without an
      // extra round-trip.
      if (modeling3dPayload.enabled && uploadedFileIds.length > 0) {
        const chatIdForAnalysis = sessionId ?? activeSession?.id ?? null;
        if (chatIdForAnalysis) {
          void Promise.all(
            uploadedFileIds.map((fileId) =>
              modeling3dApi
                .analyzeAttachment(chatIdForAnalysis, fileId)
                .then((analysis) => ({ ok: true as const, analysis }))
                .catch((exc: unknown) => ({
                  ok: false as const,
                  fileId,
                  error: exc instanceof Error ? exc.message : "Falha ao analisar anexo 3D."
                }))
            )
          ).then((results) => {
            const notes = results.map((entry, index) => {
              const baseId = `${optimisticId("m3d_note")}_${index}`;
              if (entry.ok) {
                return {
                  id: baseId,
                  session_id: chatIdForAnalysis,
                  role: "assistant" as const,
                  content: entry.analysis.context_text,
                  model_id: null,
                  metadata: {
                    response_mode: "modeling_3d_attachment_analysis",
                    attachment_analysis: entry.analysis
                  } as Record<string, unknown>,
                  created_at: nowIso()
                };
              }
              return {
                id: baseId,
                session_id: chatIdForAnalysis,
                role: "assistant" as const,
                content: `Não consegui analisar o anexo (${entry.fileId}): ${entry.error}`,
                model_id: null,
                metadata: { response_mode: "modeling_3d_attachment_analysis_error" } as Record<string, unknown>,
                created_at: nowIso()
              };
            });
            if (!notes.length) return;
            setSessions((current) =>
              current.map((session) =>
                session.id === chatIdForAnalysis ? { ...session, messages: [...session.messages, ...notes] } : session
              )
            );
          });
        }
      }
    } catch (error) {
      if (error instanceof ChatStreamHttpError && error.reason === "chat_title_required") {
        setDraft(message);
        if (sessionId && (optimisticUser || optimisticAssistant)) {
          const optimisticIds = new Set(
            [optimisticUser?.id, optimisticAssistant?.id].filter((id): id is string => Boolean(id))
          );
          setSessions((current) =>
            current.map((session) =>
              session.id === sessionId
                ? { ...session, messages: session.messages.filter((item) => !optimisticIds.has(item.id)) }
                : session
            )
          );
        }
        void chatTitleGate.openTitleDialog(activeSession?.title);
        return;
      }
      const errorMessage = error instanceof Error ? error.message : "Falha inesperada no chat.";
      const fallbackOptimisticUser =
        optimisticUser ??
        ({
          id: optimisticId("user"),
          session_id: sessionId ?? "pending",
          role: "user",
          content: message,
          model_id: activeAgentModelLabel,
          created_at: nowIso()
        } as ChatMessage);
      const fallbackOptimisticAssistant =
        optimisticAssistant ??
        localAssistantMessage(sessionId ?? "pending", optimisticStatus, streamExecutionModes.reasoningSummary);
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
        const localSessionId = optimisticId("local_error");
        setActiveSessionId(localSessionId);
        setSessions((current) =>
          sortSessionsByNewest([
            {
              id: localSessionId,
              title: streamTitle ?? message.slice(0, 48),
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
              metadata: {
                is_empty_draft: false,
                ...(modeling3dPayload.enabled ? { modeling_3d: modeling3dPayload } : {})
              },
              created_at: nowIso(),
              updated_at: nowIso(),
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
      if (streamExecutionModes.modeling3dEnabled && !activeSessionIsModeling3D) {
        setModeling3dEnabled(false);
      }
      setIsStreaming(false);
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
      resetDocumentDraft();
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
      <ChatTitleRequiredDialog
        key={chatTitleGate.dialogRequestId}
        open={chatTitleGate.dialogOpen}
        initialTitle={chatTitleGate.initialTitle}
        onConfirm={chatTitleGate.confirmTitle}
        onCancel={chatTitleGate.cancelTitleDialog}
      />
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

      <AppSidebar
        mobileMenuOpen={mobileMenuOpen}
        onCloseMobile={() => setMobileMenuOpen(false)}
        onNewChat={() => void startNewChat()}
        isCreatingNewChat={isCreatingNewChat}
        activeView={activeView}
        onSelectView={handleSelectView}
        sessionsCount={sessions.length}
        promptsCount={prompts.length}
        projects={nonGeneralProjects}
        folders={projectFolders}
        explorerSessions={projectExplorerSessions}
        historySessions={generalHistorySessions}
        activeSessionId={activeSessionId}
        projectExplorerCollapsed={projectExplorerCollapsed}
        projectExplorerExpanded={projectExplorerExpanded}
        onToggleProjectExplorerCollapsed={() => setProjectExplorerCollapsed((current) => !current)}
        onToggleProjectExplorerExpanded={(key) =>
          setProjectExplorerExpanded((current) => ({ ...current, [key]: !(current[key] ?? true) }))
        }
        historyCollapsed={historyCollapsed}
        deletingSessionId={deletingSessionId}
        historyDisabled={isStreaming}
        onToggleHistoryCollapsed={() => setHistoryCollapsed((current) => !current)}
        onSelectSession={handleSelectSidebarSession}
        onCreateChat={(projectId, folderId) => void createChatInProject(projectId, folderId)}
        onCreateFolder={(projectId, parentId) => void createFolderFromExplorer(projectId, parentId)}
        onDeleteFolder={(folderId) => void deleteFolderFromExplorer(folderId)}
        onMoveSession={(sessionId, projectId, folderId) => void moveSessionInExplorer(sessionId, projectId, folderId)}
        onDeleteSession={(session) => void deleteChatSession(session)}
        online={loadState === "ready"}
        agentModelLabel={activeAgentModelLabel}
        costUsage={costUsage}
        onOpenSettings={() => handleSelectView("agents")}
      />

      <main className="flex min-w-0 flex-1 flex-col">
        <AppHeader
          activeView={activeView}
          isModeling3D={activeSessionIsModeling3D}
          chatTitle={activeSession?.title ?? "Novo chat com JUDITE"}
          chatSubtitle={activeAgent?.description ?? "Orquestração local-first"}
          agentModelLabel={activeAgentModelLabel}
          online={loadState === "ready"}
          onOpenMobileMenu={() => setMobileMenuOpen(true)}
        />

        <div className="flex min-h-0 flex-1">
          {activeView === "chat" ? (
            <>
              <section className="flex min-w-0 flex-1 flex-col">
                <ChatMessageList
                  activeSession={activeSession}
                  activeSessionLazy={activeSessionLazy}
                  platformFilesById={platformFilesById}
                  isModeling3D={activeSessionIsModeling3D}
                  modelingPlanActions={modelingPlanActions}
                  scrollRef={chatScrollRef}
                  loadOlderRef={chatLoadOlderRef}
                  onScroll={handleChatScroll}
                  quickActions={quickActions}
                  onQuickAction={handleQuickAction}
                  sessionsCount={sessions.length}
                  documentsCount={documents.length}
                  monthlySpendBrl={costUsage?.estimated_spend_brl ?? null}
                />

                <form onSubmit={handleSubmit} className="border-t border-forge-line-soft bg-forge-ink p-3">
                  <div className="mx-auto max-w-3xl rounded-lg border border-forge-line bg-forge-panel p-3 shadow-soft">
                    <div className="mb-2 space-y-2 border-b border-forge-line-soft pb-2">
                      <div className="flex items-start justify-between gap-3">
                        <ComposerContextChips
                          agentName={activeAgent?.name ?? "Sem agente"}
                          projectLabel={`${contextProjectsLabel} · ${scopeModeLabel}`}
                          knowledgeBasesLabel={selectedContextDocsLabel}
                          executionLabel={executionLabels.length ? executionLabels.join(", ") : "padrão"}
                          selectedImageModelId={effectiveImageModel?.id ?? ""}
                          imageCapableModels={imageCapableModels}
                          showDiagnostics={activeSessionIsModeling3D}
                          onOpenDiagnostics={() => setModelingDiagnosticsOpen(true)}
                        />

                        <div className="flex items-center gap-1">
                          <ExecutionMenu
                            menuRef={executionMenuRef}
                            modeling3dEnabled={modeling3dEnabled}
                            reasoningSummaryUnavailable={reasoningSummaryUnavailable}
                            onEnableModeling3d={() => {
                              setModelingEnableDialogOpen(true);
                              setResponseMode("text");
                              setDeepResearch(false);
                              setReasoningSummary(false);
                              setMultiAgentMode(false);
                            }}
                            onToggleDeepResearch={() => {
                              setDeepResearch((current) => !current);
                              setResponseMode("text");
                              setReasoningSummary(false);
                              if (!activeSessionIsModeling3D) setModeling3dEnabled(false);
                            }}
                            onToggleImageMode={() => {
                              setResponseMode((current) => (current === "image" ? "text" : "image"));
                              setDeepResearch(false);
                              setReasoningSummary(false);
                              if (!activeSessionIsModeling3D) setModeling3dEnabled(false);
                            }}
                            onToggleMultiAgent={() => {
                              setMultiAgentMode((current) => !current);
                              if (!activeSessionIsModeling3D) setModeling3dEnabled(false);
                            }}
                            onEditKnowledgeBases={() => setContextDocsModalOpen(true)}
                            onAttachFile={() => fileInputRef.current?.click()}
                          />

                          <ShortcutMenu
                            menuRef={shortcutMenuRef}
                            agents={agents}
                            activeAgent={activeAgent}
                            availableContextProjects={availableContextProjects}
                            activeProjectId={normalizedContextProjectIds[0]}
                            onSelectAgent={(agentId) => {
                              setActiveAgentId(agentId);
                              setShortcutMenuOpen(false);
                              setShortcutSubmenu(null);
                            }}
                            onSelectProject={(project) => {
                              setChatProjectId(project.id);
                              setChatContextProjectIds([project.id]);
                              setChatContextKnowledgeBaseIds(project.context.knowledge_base_ids ?? []);
                              setShortcutMenuOpen(false);
                              setShortcutSubmenu(null);
                            }}
                            onEditKnowledgeBases={() => setContextDocsModalOpen(true)}
                          />
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
                    <ComposerAttachments
                      attachedFiles={attachedFiles}
                      attachedPlatformFileIds={attachedPlatformFileIds}
                      attachedDocumentIds={attachedDocumentIds}
                      platformFiles={platformFiles}
                      documents={documents}
                      onRemoveFile={(index) =>
                        setAttachedFiles((current) => current.filter((_, itemIndex) => itemIndex !== index))
                      }
                      onRemovePlatformFile={(fileId) =>
                        setAttachedPlatformFileIds((current) => current.filter((itemId) => itemId !== fileId))
                      }
                      onRemoveDocument={(documentId) =>
                        setAttachedDocumentIds((current) => current.filter((itemId) => itemId !== documentId))
                      }
                    />
                    <ChatComposerInput
                      showMentions={Boolean(activeMention)}
                      mentionSuggestions={mentionSuggestions}
                      onInsertMention={insertFolderMention}
                      draftInputRef={draftInputRef}
                      draft={draft}
                      onChangeDraft={(value, cursor) => {
                        setDraft(value);
                        setDraftCursor(cursor);
                      }}
                      onMoveCursor={setDraftCursor}
                      offline={loadState === "offline"}
                      modeling3dEnabled={modeling3dEnabled}
                      sendButtonTitle={sendButtonTitle}
                      sendDisabled={sendDisabled}
                      isStreaming={isStreaming}
                    />
                  </div>
                </form>
              </section>

              <ChatRightPanel
                activePanel={activePanel}
                onSelectPanel={setActivePanel}
                status={status}
                costUsage={costUsage}
                costPolicy={costPolicy}
                agentsCount={agents.length}
                prompts={prompts}
                documents={documents}
                auditEvents={auditEvents}
                documentTitle={documentTitle}
                onSetDocumentTitle={setDocumentTitle}
                documentContent={documentContent}
                onSetDocumentContent={setDocumentContent}
                documentQuery={documentQuery}
                onSetDocumentQuery={setDocumentQuery}
                documentResults={documentResults}
                isIndexingDocument={isIndexingDocument}
                onIndexTextDocument={() => void indexTextDocument()}
                onSearchDocuments={() => void searchIndexedDocuments()}
                setDraft={setDraft}
                providerStatuses={providerStatuses}
                providerDrafts={providerDrafts}
                onSetProviderDrafts={setProviderDrafts}
                providerEditMode={providerEditMode}
                onSetProviderEditMode={setProviderEditMode}
                onSaveProviderKey={(provider) => void saveProviderKey(provider)}
                onClearProviderKey={(provider) => void clearProviderKey(provider)}
                modeling3dSoftware={modeling3dSoftware}
                onModeling3dSoftwareChange={setModeling3dSoftware}
                onOpenAgentDashboard={() => editAgent(activeAgent ?? null)}
              />
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
