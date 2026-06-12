import { useEffect, useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import { sortFoldersForUi, sortProjectsForUi } from "../../features/projects/project-domain";
import { sortSessionsByNewest } from "../../shared/utils/common";
import type {
  Agent,
  AuditEvent,
  ChatSession,
  CostPolicy,
  CostUsage,
  DocumentRecord,
  KnowledgeBase,
  KnowledgeBaseDocument,
  ModelConfig,
  PlatformFile,
  PlatformFileIndexingStatus,
  ProjectFolder,
  ProjectRecord,
  Prompt,
  ProviderSecretStatus,
  ServerStatus
} from "../../types/api";
import type { AppDataSnapshot } from "../queries/app-data";

type AppDataBootstrapConfig = {
  /** The fetched snapshot (`appDataQuery.data`), or `undefined` while loading. */
  snapshot: AppDataSnapshot | undefined;
  /** Current store selections, needed to keep `chatProjectId` valid. */
  activeSessionId: string | null;
  chatProjectId: string | null;
  /** Local-state mirrors (safe to set during render). */
  mergeSessionSummaries: (summaries: ChatSession[]) => void;
  setStatus: Dispatch<SetStateAction<ServerStatus | null>>;
  setModels: Dispatch<SetStateAction<ModelConfig[]>>;
  setAgents: Dispatch<SetStateAction<Agent[]>>;
  setPrompts: Dispatch<SetStateAction<Prompt[]>>;
  setDocuments: Dispatch<SetStateAction<DocumentRecord[]>>;
  setKnowledgeBases: Dispatch<SetStateAction<KnowledgeBase[]>>;
  setKnowledgeBaseDocuments: Dispatch<SetStateAction<KnowledgeBaseDocument[]>>;
  setPlatformFiles: Dispatch<SetStateAction<PlatformFile[]>>;
  setFileIndexingStatus: Dispatch<SetStateAction<PlatformFileIndexingStatus | null>>;
  setProjects: Dispatch<SetStateAction<ProjectRecord[]>>;
  setProjectFolders: Dispatch<SetStateAction<ProjectFolder[]>>;
  setAuditEvents: Dispatch<SetStateAction<AuditEvent[]>>;
  setCostPolicy: Dispatch<SetStateAction<CostPolicy | null>>;
  setCostUsage: Dispatch<SetStateAction<CostUsage | null>>;
  setProviderStatuses: Dispatch<SetStateAction<ProviderSecretStatus[]>>;
  setSelectedKnowledgeBaseId: Dispatch<SetStateAction<string | null>>;
  setFolderDraftParentId: Dispatch<SetStateAction<string | null>>;
  /** Store selections (zustand setters — must NOT run during render). */
  setActiveSessionId: Dispatch<SetStateAction<string | null>>;
  setActiveAgentId: Dispatch<SetStateAction<string | null>>;
  setSupportAgentIds: Dispatch<SetStateAction<string[]>>;
  setSelectedKnowledgeProjectId: Dispatch<SetStateAction<string | null>>;
  setSelectedKnowledgeFolderId: Dispatch<SetStateAction<string | null>>;
  setChatProjectId: Dispatch<SetStateAction<string | null>>;
};

/**
 * Distributes the bootstrap snapshot into the app's state and keeps the active
 * selections valid. Extracted from `App.tsx` so the reconcile is independently
 * analysable by the React Compiler (architecture-map "monólitos de borda").
 *
 * The split is deliberate and required by the `react-hooks/set-state-in-effect`
 * rule:
 * - Local-state mirrors are reconciled *during render* (React's sanctioned
 *   "adjust state when a value changes" pattern), guarded on snapshot identity.
 * - Store-backed selections stay in an effect (zustand setters can't run during
 *   render — that warns "cannot update a different component") but defer their
 *   writes to a microtask so no synchronous `setState` happens in the effect.
 */
export function useAppDataBootstrap({
  snapshot,
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
  setChatProjectId
}: AppDataBootstrapConfig): void {
  const [syncedSnapshot, setSyncedSnapshot] = useState<AppDataSnapshot | null>(null);
  if (snapshot && snapshot !== syncedSnapshot) {
    setSyncedSnapshot(snapshot);
    setStatus(snapshot.serverStatus);
    mergeSessionSummaries(sortSessionsByNewest(snapshot.chatSessions));
    setModels(snapshot.modelList);
    setAgents(snapshot.agentList);
    setPrompts(snapshot.promptList);
    setDocuments(snapshot.documentList);
    setKnowledgeBases(snapshot.knowledgeBaseList);
    setKnowledgeBaseDocuments(snapshot.knowledgeBaseDocumentList);
    setPlatformFiles(snapshot.fileList);
    setFileIndexingStatus(snapshot.fileIndexingStatus);
    setProjects(sortProjectsForUi(snapshot.projectList));
    setProjectFolders(sortFoldersForUi(snapshot.folderList));
    setAuditEvents(snapshot.auditList);
    setCostPolicy(snapshot.policy);
    setCostUsage(snapshot.usage);
    setProviderStatuses(snapshot.providerList);
    setSelectedKnowledgeBaseId((current) =>
      current && snapshot.knowledgeBaseList.some((knowledgeBase) => knowledgeBase.id === current)
        ? current
        : (snapshot.knowledgeBaseList[0]?.id ?? null)
    );
    setFolderDraftParentId((current) =>
      current && snapshot.folderList.some((folder) => folder.id === current) ? current : null
    );
  }

  useEffect(() => {
    if (!snapshot) return;
    const { agentList, projectList, folderList } = snapshot;
    const sortedChatSessions = sortSessionsByNewest(snapshot.chatSessions);
    const generalProjectId = projectList.find((project) => project.is_general)?.id ?? projectList[0]?.id ?? null;
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
    queueMicrotask(() => {
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
      setSelectedKnowledgeProjectId((current) =>
        current && projectList.some((project) => project.id === current) ? current : generalProjectId
      );
      setSelectedKnowledgeFolderId((current) =>
        current && folderList.some((folder) => folder.id === current) ? current : null
      );
      setChatProjectId(resolvedChatProjectId);
    });
  }, [
    activeSessionId,
    chatProjectId,
    snapshot,
    setActiveAgentId,
    setActiveSessionId,
    setChatProjectId,
    setSelectedKnowledgeFolderId,
    setSelectedKnowledgeProjectId,
    setSupportAgentIds
  ]);
}
