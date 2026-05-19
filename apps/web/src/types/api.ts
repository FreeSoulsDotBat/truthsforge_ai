export type ProviderName = "openai" | "anthropic" | "google";
export type JobStatus = "pending" | "running" | "completed" | "failed";
export type ModelingSoftware = "auto" | "blender" | "fusion";
export type ModelingExecutionMode = "plan_only" | "approval_required" | "safe_auto";
export type ChatModelingStage = "discovery" | "planning" | "approved" | "executing" | "editing" | "completed";
export type ModelingPlanKind = "primary" | "edit";
export type ModelingPlanStatus =
  | "draft"
  | "waiting_approval"
  | "approved"
  | "running"
  | "completed"
  | "rejected"
  | "failed";
export type ModelingStepStatus =
  | "pending"
  | "waiting_approval"
  | "approved"
  | "running"
  | "completed"
  | "rejected"
  | "failed";
export type ModelingRiskLevel = "low" | "medium" | "high";

export interface ServerStatus {
  online: boolean;
  app_name: string;
  persona: string;
  environment: string;
  public_base_url: string;
  vector_store: string;
  database: string;
  mobile_access: string;
  features: Record<string, boolean>;
}

export type ModelingTransport = "stdio" | "http" | "mock" | "local";
export type ModelingPlannerSource = "llm" | "heuristic";
export type ModelingToolCallStatus = "ok" | "error" | "blocked";
export type ModelingPrintabilitySeverity = "info" | "warning" | "error";

export interface ModelingCapability {
  software: ModelingSoftware;
  connected: boolean;
  transport: ModelingTransport;
  tools: string[];
  status: string;
  detail: string;
}

export interface ModelingCapabilities {
  mode: "local_mcp";
  default_execution_mode: ModelingExecutionMode;
  safety_notes: string[];
  adapters: ModelingCapability[];
}

export interface ModelingSession {
  id: string;
  software: ModelingSoftware;
  project_id?: string | null;
  status: "starting" | "connected" | "mock" | "failed" | "closed";
  mcp_server: string;
  host_pid?: number | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ModelingSessionStart {
  software: Exclude<ModelingSoftware, "auto">;
  project_id?: string | null;
  force_mock?: boolean;
}

export interface ModelingPlanStep {
  id: string;
  seq: number;
  title: string;
  software: ModelingSoftware;
  tool_name: string;
  risk_level: ModelingRiskLevel;
  approval_required: boolean;
  status: ModelingStepStatus;
  input_json: Record<string, unknown>;
  output_json: Record<string, unknown>;
  error?: string | null;
  approved_at?: string | null;
  completed_at?: string | null;
}

export interface ModelingPlan {
  id: string;
  project_id?: string | null;
  conversation_id?: string | null;
  prompt: string;
  mode: ModelingExecutionMode;
  software_choice: ModelingSoftware;
  confidence: number;
  approval_required: boolean;
  status: ModelingPlanStatus;
  rationale: string;
  assumptions: string[];
  risks: string[];
  knowledge_base_ids: string[];
  steps: ModelingPlanStep[];
  planner_source?: ModelingPlannerSource | null;
  fallback_reason?: string | null;
  // Presente apenas quando o plano é serializado via SSE (rota chat stream).
  // Endpoints REST que devolvem ``ModelingPlan`` puro não populam — use
  // ``GET /api/3d/plans/{id}/trace`` consultando pelo plan_id nesse caso.
  trace_id?: string | null;
  kind?: ModelingPlanKind;
  parent_plan_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ModelingPlanCreate {
  prompt: string;
  project_id?: string | null;
  conversation_id?: string | null;
  mode?: ModelingExecutionMode;
  software_override?: ModelingSoftware | null;
  knowledge_base_ids?: string[];
}

// Observabilidade — alinhado com backend/app/core/contracts.py
// ``ModelingTraceSource``, ``ModelingTraceLevel`` e ``ModelingTraceEvent``.
export type ModelingTraceSource = "ui" | "backend" | "mcp" | "fusion" | "blender";
export type ModelingTraceLevel = "debug" | "info" | "warn" | "error";

export interface ModelingTraceEvent {
  id: string;
  trace_id: string;
  plan_id: string | null;
  session_id: string | null;
  project_id: string | null;
  event_type: string;
  source: ModelingTraceSource;
  level: ModelingTraceLevel;
  message: string | null;
  payload: Record<string, unknown>;
  duration_ms: number | null;
  sequence: number;
  schema_version: number;
  created_at: string;
}

export interface ModelingTraceEventCreate {
  trace_id: string;
  plan_id?: string | null;
  event_type: string;
  level?: ModelingTraceLevel;
  message?: string | null;
  payload?: Record<string, unknown>;
  duration_ms?: number | null;
}

export interface ChatModeling3DContext {
  enabled: boolean;
  mode?: ModelingExecutionMode;
  software_override?: ModelingSoftware | null;
}

export interface ModelingApprovalRequest {
  decision: "approve" | "reject";
  reason?: string;
}

export interface ModelingSnapshotFile {
  relative_path: string;
  sha256: string;
  size_bytes: number;
}

export interface ModelingSnapshot {
  id: string;
  project_id?: string | null;
  plan_id?: string | null;
  step_id?: string | null;
  parent_snapshot_id?: string | null;
  label: string;
  reason: string;
  workspace_path?: string | null;
  storage_path?: string | null;
  files: ModelingSnapshotFile[];
  manifest: Record<string, unknown>;
  restored_at?: string | null;
  created_at: string;
}

export interface ModelingSnapshotCreate {
  project_id?: string | null;
  plan_id?: string | null;
  step_id?: string | null;
  parent_snapshot_id?: string | null;
  label?: string;
  reason?: string;
}

export interface ModelingSnapshotRestore {
  reason?: string;
  force?: boolean;
}

export interface ModelingSnapshotRestoreResult {
  snapshot: ModelingSnapshot;
  auto_snapshot?: ModelingSnapshot | null;
  restored_file_count: number;
}

export interface ModelingToolCall {
  id: string;
  plan_id: string;
  step_id: string;
  seq: number;
  mcp_server: string;
  tool_name: string;
  software: ModelingSoftware;
  transport: ModelingTransport;
  status: ModelingToolCallStatus;
  request_json: Record<string, unknown>;
  response_json: Record<string, unknown>;
  error_code?: string | null;
  error_message?: string | null;
  retryable: boolean;
  safe_to_retry_after_snapshot_restore: boolean;
  duration_ms?: number | null;
  artifact_paths: string[];
  artifact_file_ids: string[];
  model_version_ids: string[];
  created_at: string;
}

export interface ModelingPrintabilityIssue {
  check: string;
  severity: ModelingPrintabilitySeverity;
  message: string;
  detail: Record<string, unknown>;
  recommendation: string;
}

export interface ModelingPrintabilityReport {
  id: string;
  project_id?: string | null;
  plan_id?: string | null;
  step_id?: string | null;
  file_id?: string | null;
  checks_executed: string[];
  issues: ModelingPrintabilityIssue[];
  metrics: Record<string, unknown>;
  recommendations: string[];
  risk_score: number;
  summary: string;
  report_json: Record<string, unknown>;
  created_at: string;
}

export interface ModelingPrintabilityRequest {
  project_id?: string | null;
  plan_id?: string | null;
  step_id?: string | null;
  file_id?: string | null;
  checks?: string[];
  printer_profile?: string | null;
}

export interface ModelingModelVersion {
  id: string;
  project_id?: string | null;
  plan_id?: string | null;
  step_id?: string | null;
  parent_version_id?: string | null;
  software: ModelingSoftware;
  source_file_id?: string | null;
  file_ids: string[];
  export_format?: string | null;
  snapshot_id?: string | null;
  label: string;
  notes: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ModelingExecutionResult {
  plan: ModelingPlan;
  executed_step_ids: string[];
  blocked_step_ids: string[];
  events: string[];
  tool_call_ids: string[];
}

export interface ModelConfig {
  id: string;
  provider: ProviderName;
  display_name: string;
  provider_model_id?: string | null;
  enabled: boolean;
  default: boolean;
  capabilities: string[];
  context_window?: number | null;
  input_token_cost_per_million?: number | null;
  output_token_cost_per_million?: number | null;
  temperature?: number | null;
  top_p?: number | null;
  top_k?: number | null;
  max_output_tokens?: number | null;
  reasoning_effort?: "none" | "minimal" | "low" | "medium" | "high" | "xhigh" | null;
  reasoning_budget_tokens?: number | null;
  verbosity?: "low" | "medium" | "high" | null;
  response_format: "text" | "json";
  tool_choice: "auto" | "none" | "required";
  parallel_tool_calls: boolean;
  presence_penalty?: number | null;
  frequency_penalty?: number | null;
  seed?: number | null;
  stop_sequences: string[];
  notes?: string | null;
}

export type ModelUpsert = ModelConfig;

export interface ProviderModel {
  id: string;
  provider: ProviderName;
  display_name: string;
  owned_by?: string | null;
  created_at?: string | null;
  input_token_limit?: number | null;
  output_token_limit?: number | null;
  input_token_cost_per_million?: number | null;
  output_token_cost_per_million?: number | null;
  pricing_source?: string | null;
  pricing_note?: string | null;
  default_temperature?: number | null;
  max_temperature?: number | null;
  default_top_p?: number | null;
  default_top_k?: number | null;
  supported_actions: string[];
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: "system" | "user" | "assistant" | "tool";
  content: string;
  model_id?: string | null;
  metadata?: Record<string, unknown>;
  created_at: string;
}

export interface ChatSession {
  id: string;
  title: string;
  model_id?: string | null;
  agent_id?: string | null;
  project_id: string;
  folder_id?: string | null;
  context_project_ids: string[];
  context_document_ids: string[];
  context_knowledge_base_ids: string[];
  archived: boolean;
  is_modeling_3d?: boolean;
  modeling_software_preference?: ModelingSoftware | null;
  modeling_stage?: ChatModelingStage | null;
  modeling_plan_id?: string | null;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  messages: ChatMessage[];
}

export interface ChatAttachmentAnalyzeResponse {
  file_id: string;
  filename: string;
  kind: "image" | "mesh" | "blend" | "cad" | "unsupported";
  ok: boolean;
  summary: string;
  metrics: Record<string, unknown>;
  suggestions: string[];
  error?: string | null;
  context_text: string;
}

export interface ChatSessionDeleteResult {
  session_id: string;
  deleted_message_count: number;
  deleted_file_ids: string[];
}

export interface PlatformFile {
  id: string;
  filename: string;
  original_filename: string;
  content_type?: string | null;
  size_bytes: number;
  storage_path: string;
  checksum_sha256?: string | null;
  duplicate_of_id?: string | null;
  source: "upload" | "chat_attachment" | "chatgpt_import" | "generated" | "knowledge_base";
  tags: string[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface PlatformFileUpdate {
  filename?: string | null;
  original_filename?: string | null;
  tags?: string[] | null;
  metadata?: Record<string, unknown> | null;
}

export interface PlatformFileIndexingStatus {
  total_files: number;
  documents_linked: number;
  completed_files: number;
  pending_files: number;
  running_files: number;
  failed_files: number;
  missing_documents: number;
  backlog_files: number;
  indexing_in_background: boolean;
  updated_at: string;
}

export interface Agent {
  id: string;
  name: string;
  description: string;
  system_prompt: string;
  model_id?: string | null;
  llm_config: AgentLLMConfig;
  enabled: boolean;
  role: "orchestrator" | "specialist" | "reviewer" | "tool";
  collaboration_mode: "standalone" | "delegate" | "review" | "parallel";
  handoff_triggers: string[];
  tags: string[];
  tools_allowed: string[];
  allowed_project_ids: string[];
  knowledge_base_ids: string[];
}

export type AgentUpsert = Omit<Agent, "id">;

export interface AgentLLMConfig {
  provider: ProviderName;
  provider_model_id?: string | null;
  display_name?: string | null;
  input_token_cost_per_million?: number | null;
  output_token_cost_per_million?: number | null;
  temperature?: number | null;
  top_p?: number | null;
  top_k?: number | null;
  max_output_tokens?: number | null;
  reasoning_effort?: "none" | "minimal" | "low" | "medium" | "high" | "xhigh" | null;
  reasoning_budget_tokens?: number | null;
  verbosity?: "low" | "medium" | "high" | null;
  response_format: "text" | "json";
  tool_choice: "auto" | "none" | "required";
  parallel_tool_calls: boolean;
  presence_penalty?: number | null;
  frequency_penalty?: number | null;
  seed?: number | null;
  stop_sequences: string[];
}

export interface Prompt {
  id: string;
  title: string;
  template: string;
  tags: string[];
  project_id?: string | null;
  favorite: boolean;
  version: number;
}

export interface ProjectContextConfig {
  scope_mode: "project_only" | "project_plus_global" | "global_only";
  max_documents: number;
  folder_ids: string[];
  document_ids: string[];
  knowledge_base_ids: string[];
  file_ids: string[];
  prompt_ids: string[];
}

export interface ProjectRecord {
  id: string;
  name: string;
  description: string;
  color: string;
  is_general: boolean;
  context: ProjectContextConfig;
  created_at: string;
  updated_at: string;
}

export interface ProjectUpsert {
  name: string;
  description: string;
  color: string;
  is_general?: boolean;
  context: ProjectContextConfig;
}

export interface ProjectFolder {
  id: string;
  project_id: string;
  parent_id?: string | null;
  name: string;
  depth: number;
  path: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectFolderCreate {
  project_id: string;
  parent_id?: string | null;
  name: string;
}

export interface ProjectFolderDeleteResult {
  folder_id: string;
  deleted_folder_ids: string[];
  deleted_chat_session_ids: string[];
}

export interface DocumentRecord {
  id: string;
  title: string;
  source_type: string;
  indexed: boolean;
  index_status: string;
  created_at?: string | null;
  updated_at?: string | null;
  category_id?: string | null;
  folder_id?: string | null;
  project_id?: string | null;
  pinned: boolean;
  tags: string[];
  metadata?: Record<string, unknown>;
}

export interface PagedResult<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export type DocumentPage = PagedResult<DocumentRecord>;
export type PlatformFilePage = PagedResult<PlatformFile>;

export interface DocumentTextCreate {
  title: string;
  content: string;
  source_type: "markdown" | "txt" | "csv" | "html";
  category_id?: string | null;
  folder_id?: string | null;
  pinned?: boolean;
  tags?: string[];
  project_id?: string | null;
  metadata?: Record<string, unknown>;
}

export interface DocumentFromFileCreate {
  file_id: string;
  category_id?: string | null;
  folder_id?: string | null;
  pinned?: boolean;
  tags?: string[];
  project_id?: string | null;
  metadata?: Record<string, unknown>;
}

export interface DocumentSearchRequest {
  query: string;
  limit?: number;
  project_id?: string | null;
  project_scope_mode?: "project_only" | "project_plus_global" | "global_only";
  folder_ids?: string[];
  category_ids?: string[];
  knowledge_base_ids?: string[];
  tags?: string[];
}

export interface ChatSessionMoveRequest {
  project_id: string;
  folder_id?: string | null;
}

export interface ChatSessionContextUpdate {
  context_project_ids: string[];
  context_document_ids: string[];
  context_knowledge_base_ids?: string[];
}

export interface DocumentSearchResult {
  document_id: string;
  title: string;
  score: number;
  content: string;
  metadata: Record<string, unknown>;
}

export interface KnowledgeCategory {
  id: string;
  name: string;
  description: string;
  color: string;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeCategoryUpsert {
  name: string;
  description: string;
  color: string;
}

export interface KnowledgeBase {
  id: string;
  name: string;
  description: string;
  scope: string;
  color: string;
  tags: string[];
  max_documents_per_query: number;
  max_chunks_per_document: number;
  enabled: boolean;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export type KnowledgeBaseUpsert = Omit<KnowledgeBase, "id" | "created_at" | "updated_at">;

export interface KnowledgeBaseDocument {
  id: string;
  knowledge_base_id: string;
  document_id: string;
  priority: number;
  note: string;
  tags: string[];
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeBaseDocumentUpsert {
  document_id: string;
  priority?: number;
  note?: string;
  tags?: string[];
  enabled?: boolean;
}

export interface CostPolicy {
  monthly_budget_brl: number;
  warn_threshold_percent: number;
  block_at_budget: boolean;
  currency: "BRL";
}

export interface CostUsage {
  month: string;
  monthly_budget_brl: number;
  estimated_spend_brl: number;
  remaining_budget_brl: number;
  warn_threshold_percent: number;
  block_at_budget: boolean;
  request_count: number;
  tokens_in: number;
  tokens_out: number;
}

export interface AuditEvent {
  id: string;
  event_type: string;
  provider?: ProviderName | null;
  model_id?: string | null;
  tokens_in: number;
  tokens_out: number;
  estimated_cost_brl: number;
  created_at: string;
}

export interface ProviderSecretStatus {
  provider: ProviderName;
  configured: boolean;
  source: "env" | "local" | "none";
}

export interface ChatGPTImportSummary {
  source_filename: string;
  conversations_found: number;
  sessions_imported: number;
  sessions_skipped: number;
  messages_imported: number;
  messages_skipped: number;
  errors: string[];
}

export interface ChatGPTImportJob {
  id: string;
  kind: "chatgpt";
  status: JobStatus;
  source_filename: string;
  file_path: string;
  platform_file_id?: string | null;
  file_size_bytes: number;
  total_bytes?: number | null;
  processed_bytes: number;
  progress_percent: number;
  current_step: string;
  summary?: ChatGPTImportSummary | null;
  error?: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}
