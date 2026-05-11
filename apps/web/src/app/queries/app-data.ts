import { api } from "../../lib/api";
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

export const appDataQueryKey = ["app-data"] as const;
const INITIAL_LIBRARY_PAGE_SIZE = 80;

export type AppDataSnapshot = {
  serverStatus: ServerStatus;
  chatSessions: ChatSession[];
  modelList: ModelConfig[];
  agentList: Agent[];
  promptList: Prompt[];
  documentList: DocumentRecord[];
  knowledgeBaseList: KnowledgeBase[];
  knowledgeBaseDocumentList: KnowledgeBaseDocument[];
  fileList: PlatformFile[];
  fileIndexingStatus: PlatformFileIndexingStatus;
  documentTotal: number;
  fileTotal: number;
  documentsHasMore: boolean;
  filesHasMore: boolean;
  projectList: ProjectRecord[];
  folderList: ProjectFolder[];
  auditList: AuditEvent[];
  policy: CostPolicy;
  usage: CostUsage;
  providerList: ProviderSecretStatus[];
};

export async function fetchAppDataSnapshot(): Promise<AppDataSnapshot> {
  const [
    serverStatus,
    chatSessions,
    modelList,
    agentList,
    promptList,
    documentPage,
    knowledgeBaseList,
    knowledgeBaseDocumentList,
    filePage,
    fileIndexingStatus,
    projectList,
    folderList,
    auditList,
    policy,
    usage,
    providerList
  ] = await Promise.all([
    api.status(),
    api.sessions(false),
    api.models(),
    api.agents(),
    api.prompts(),
    api.documentsPage({ limit: INITIAL_LIBRARY_PAGE_SIZE, offset: 0 }),
    api.knowledgeBases(),
    api.knowledgeBaseDocumentsAll(),
    api.filesPage({ limit: INITIAL_LIBRARY_PAGE_SIZE, offset: 0 }),
    api.fileIndexingStatus(),
    api.projects(),
    api.projectFolders(),
    api.auditEvents(),
    api.costPolicy(),
    api.costUsage(),
    api.providerStatuses()
  ]);
  return {
    serverStatus,
    chatSessions,
    modelList,
    agentList,
    promptList,
    documentList: documentPage.items,
    knowledgeBaseList,
    knowledgeBaseDocumentList,
    fileList: filePage.items,
    fileIndexingStatus,
    documentTotal: documentPage.total,
    fileTotal: filePage.total,
    documentsHasMore: documentPage.has_more,
    filesHasMore: filePage.has_more,
    projectList,
    folderList,
    auditList,
    policy,
    usage,
    providerList
  };
}
