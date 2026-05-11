from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def now_utc() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:16]}"


DEFAULT_GENERAL_PROJECT_ID = "project_general"
DEFAULT_GENERAL_PROJECT_NAME = "Geral"
MAX_CHAT_ATTACHMENT_FILE_IDS = 10
MAX_CHAT_ATTACHMENT_DOCUMENT_IDS = 20
MAX_CONTEXT_DOCUMENT_IDS = 20
MAX_CONTEXT_KNOWLEDGE_BASE_IDS = 12


class ProviderName(StrEnum):
    openai = "openai"
    anthropic = "anthropic"
    google = "google"


class ModelCapability(StrEnum):
    chat = "chat"
    vision = "vision"
    image_generation = "image_generation"
    deep_research = "deep_research"
    json = "json"
    tool_calling = "tool_calling"
    long_context = "long_context"


class PermissionMode(StrEnum):
    allow = "allow"
    ask = "ask"
    deny = "deny"


class JobStatus(StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class ModelingSoftware(StrEnum):
    auto = "auto"
    blender = "blender"
    fusion = "fusion"


class ModelingExecutionMode(StrEnum):
    plan_only = "plan_only"
    approval_required = "approval_required"
    safe_auto = "safe_auto"


class ModelingPlanStatus(StrEnum):
    draft = "draft"
    waiting_approval = "waiting_approval"
    approved = "approved"
    running = "running"
    completed = "completed"
    rejected = "rejected"
    failed = "failed"


class ModelingStepStatus(StrEnum):
    pending = "pending"
    waiting_approval = "waiting_approval"
    approved = "approved"
    running = "running"
    completed = "completed"
    rejected = "rejected"
    failed = "failed"


class ModelingRiskLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class ModelingApprovalDecision(StrEnum):
    approve = "approve"
    reject = "reject"


class ModelConfig(BaseModel):
    id: str
    provider: ProviderName
    display_name: str
    provider_model_id: str | None = None
    enabled: bool = True
    default: bool = False
    capabilities: list[ModelCapability] = Field(default_factory=lambda: [ModelCapability.chat])
    context_window: int | None = None
    input_token_cost_per_million: float | None = None
    output_token_cost_per_million: float | None = None
    temperature: float | None = Field(default=1, ge=0, le=2)
    top_p: float | None = Field(default=1, ge=0, le=1)
    top_k: int | None = Field(default=None, ge=0)
    max_output_tokens: int | None = Field(default=2048, ge=1)
    reasoning_effort: Literal["none", "minimal", "low", "medium", "high", "xhigh"] | None = None
    reasoning_budget_tokens: int | None = Field(default=None, ge=0)
    verbosity: Literal["low", "medium", "high"] | None = None
    response_format: Literal["text", "json"] = "text"
    tool_choice: Literal["auto", "none", "required"] = "auto"
    parallel_tool_calls: bool = True
    presence_penalty: float | None = Field(default=None, ge=-2, le=2)
    frequency_penalty: float | None = Field(default=None, ge=-2, le=2)
    seed: int | None = None
    stop_sequences: list[str] = Field(default_factory=list)
    notes: str | None = None


class ModelUpsert(BaseModel):
    id: str
    provider: ProviderName
    display_name: str
    provider_model_id: str | None = None
    enabled: bool = True
    default: bool = False
    capabilities: list[ModelCapability] = Field(default_factory=lambda: [ModelCapability.chat])
    context_window: int | None = None
    input_token_cost_per_million: float | None = None
    output_token_cost_per_million: float | None = None
    temperature: float | None = Field(default=1, ge=0, le=2)
    top_p: float | None = Field(default=1, ge=0, le=1)
    top_k: int | None = Field(default=None, ge=0)
    max_output_tokens: int | None = Field(default=2048, ge=1)
    reasoning_effort: Literal["none", "minimal", "low", "medium", "high", "xhigh"] | None = None
    reasoning_budget_tokens: int | None = Field(default=None, ge=0)
    verbosity: Literal["low", "medium", "high"] | None = None
    response_format: Literal["text", "json"] = "text"
    tool_choice: Literal["auto", "none", "required"] = "auto"
    parallel_tool_calls: bool = True
    presence_penalty: float | None = Field(default=None, ge=-2, le=2)
    frequency_penalty: float | None = Field(default=None, ge=-2, le=2)
    seed: int | None = None
    stop_sequences: list[str] = Field(default_factory=list)
    notes: str | None = None


class ProviderModel(BaseModel):
    id: str
    provider: ProviderName
    display_name: str
    owned_by: str | None = None
    created_at: str | None = None
    input_token_limit: int | None = None
    output_token_limit: int | None = None
    input_token_cost_per_million: float | None = None
    output_token_cost_per_million: float | None = None
    pricing_source: str | None = None
    pricing_note: str | None = None
    default_temperature: float | None = None
    max_temperature: float | None = None
    default_top_p: float | None = None
    default_top_k: int | None = None
    supported_actions: list[str] = Field(default_factory=list)


class CostPolicy(BaseModel):
    monthly_budget_brl: float = 200
    warn_threshold_percent: int = 80
    block_at_budget: bool = True
    currency: Literal["BRL"] = "BRL"
    updated_at: datetime = Field(default_factory=now_utc)


class CostUsage(BaseModel):
    month: str
    monthly_budget_brl: float
    estimated_spend_brl: float
    remaining_budget_brl: float
    warn_threshold_percent: int
    block_at_budget: bool
    request_count: int
    tokens_in: int
    tokens_out: int


class AuditEvent(BaseModel):
    id: str = Field(default_factory=lambda: new_id("audit"))
    event_type: str
    provider: ProviderName | None = None
    model_id: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    estimated_cost_brl: float = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=now_utc)


class ProviderSecretStatus(BaseModel):
    provider: ProviderName
    configured: bool
    source: Literal["env", "local", "none"]


class ProviderSecretUpsert(BaseModel):
    api_key: str = Field(min_length=1)


class ToolDefinition(BaseModel):
    id: str = Field(default_factory=lambda: new_id("tool"))
    name: str
    description: str
    category: str
    dangerous: bool = False
    requires_confirmation: bool = False
    enabled: bool = True


class PermissionPolicy(BaseModel):
    agent_id: str
    dangerous_action_default: PermissionMode = PermissionMode.ask
    tool_permissions: dict[str, PermissionMode] = Field(default_factory=dict)


class AgentGraph(BaseModel):
    id: str = Field(default_factory=lambda: new_id("graph"))
    agent_id: str
    runtime: str = "langgraph"
    human_in_the_loop: bool = True
    state_schema_version: str = "v1"


class AgentLLMConfig(BaseModel):
    provider: ProviderName = ProviderName.openai
    provider_model_id: str | None = None
    display_name: str | None = None
    input_token_cost_per_million: float | None = None
    output_token_cost_per_million: float | None = None
    temperature: float | None = Field(default=1, ge=0, le=2)
    top_p: float | None = Field(default=1, ge=0, le=1)
    top_k: int | None = Field(default=None, ge=0)
    max_output_tokens: int | None = Field(default=2048, ge=1)
    reasoning_effort: Literal["none", "minimal", "low", "medium", "high", "xhigh"] | None = None
    reasoning_budget_tokens: int | None = Field(default=None, ge=0)
    verbosity: Literal["low", "medium", "high"] | None = None
    response_format: Literal["text", "json"] = "text"
    tool_choice: Literal["auto", "none", "required"] = "auto"
    parallel_tool_calls: bool = True
    presence_penalty: float | None = Field(default=None, ge=-2, le=2)
    frequency_penalty: float | None = Field(default=None, ge=-2, le=2)
    seed: int | None = None
    stop_sequences: list[str] = Field(default_factory=list)


class Agent(BaseModel):
    id: str = Field(default_factory=lambda: new_id("agent"))
    name: str
    description: str = ""
    system_prompt: str
    model_id: str | None = None
    llm_config: AgentLLMConfig = Field(default_factory=AgentLLMConfig)
    enabled: bool = True
    role: Literal["orchestrator", "specialist", "reviewer", "tool"] = "specialist"
    collaboration_mode: Literal["standalone", "delegate", "review", "parallel"] = "standalone"
    handoff_triggers: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    tools_allowed: list[str] = Field(default_factory=list)
    allowed_project_ids: list[str] = Field(default_factory=lambda: [DEFAULT_GENERAL_PROJECT_ID])
    knowledge_base_ids: list[str] = Field(default_factory=list)
    permission_policy: PermissionPolicy | None = None
    graph: AgentGraph | None = None
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class AgentCreate(BaseModel):
    name: str
    description: str = ""
    system_prompt: str
    model_id: str | None = None
    llm_config: AgentLLMConfig = Field(default_factory=AgentLLMConfig)
    enabled: bool = True
    role: Literal["orchestrator", "specialist", "reviewer", "tool"] = "specialist"
    collaboration_mode: Literal["standalone", "delegate", "review", "parallel"] = "standalone"
    handoff_triggers: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    tools_allowed: list[str] = Field(default_factory=list)
    allowed_project_ids: list[str] = Field(default_factory=lambda: [DEFAULT_GENERAL_PROJECT_ID])
    knowledge_base_ids: list[str] = Field(default_factory=list)


class AgentUpdate(AgentCreate):
    pass


class Prompt(BaseModel):
    id: str = Field(default_factory=lambda: new_id("prompt"))
    title: str
    template: str
    tags: list[str] = Field(default_factory=list)
    project_id: str | None = None
    agent_id: str | None = None
    favorite: bool = False
    version: int = 1
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class PromptCreate(BaseModel):
    title: str
    template: str
    tags: list[str] = Field(default_factory=list)
    project_id: str | None = None
    agent_id: str | None = None
    favorite: bool = False


class ChatSession(BaseModel):
    id: str = Field(default_factory=lambda: new_id("chat"))
    title: str = "Novo chat"
    model_id: str | None = None
    agent_id: str | None = None
    project_id: str = DEFAULT_GENERAL_PROJECT_ID
    folder_id: str | None = None
    context_project_ids: list[str] = Field(default_factory=list)
    context_document_ids: list[str] = Field(default_factory=list)
    context_knowledge_base_ids: list[str] = Field(default_factory=list)
    archived: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class ChatSessionCreate(BaseModel):
    title: str = "Novo chat"
    model_id: str | None = None
    agent_id: str | None = None
    project_id: str | None = None
    folder_id: str | None = None
    context_project_ids: list[str] = Field(default_factory=list)
    context_document_ids: list[str] = Field(default_factory=list)
    context_knowledge_base_ids: list[str] = Field(default_factory=list)


class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: new_id("msg"))
    session_id: str
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    model_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=now_utc)


class ChatSessionWithMessages(ChatSession):
    messages: list[ChatMessage] = Field(default_factory=list)


class ChatSessionDeleteResult(BaseModel):
    session_id: str
    deleted_message_count: int = 0
    deleted_file_ids: list[str] = Field(default_factory=list)


class ChatSessionMoveRequest(BaseModel):
    project_id: str
    folder_id: str | None = None


class ChatSessionContextUpdate(BaseModel):
    context_project_ids: list[str] = Field(default_factory=list)
    context_document_ids: list[str] = Field(default_factory=list)
    context_knowledge_base_ids: list[str] = Field(default_factory=list)


class ChatStreamRequest(BaseModel):
    message: str
    session_id: str | None = None
    model_id: str | None = None
    agent_id: str | None = None
    agent_ids: list[str] = Field(default_factory=list)
    project_id: str | None = None
    folder_id: str | None = None
    project_scope_mode: Literal["project_only", "project_plus_global", "global_only"] = (
        "global_only"
    )
    context_project_ids: list[str] = Field(default_factory=list)
    context_document_ids: list[str] = Field(
        default_factory=list, max_length=MAX_CONTEXT_DOCUMENT_IDS
    )
    context_knowledge_base_ids: list[str] = Field(
        default_factory=list, max_length=MAX_CONTEXT_KNOWLEDGE_BASE_IDS
    )
    reasoning_override: Literal["default", "long"] = "default"
    deep_research: bool = False
    deep_research_max_tool_calls: int = Field(default=20, ge=1, le=100)
    response_mode: Literal["text", "image"] = "text"
    image_model_id: str | None = None
    reasoning_summary: Literal["off", "auto"] = "off"
    multi_agent_mode: bool = False
    attached_document_ids: list[str] = Field(
        default_factory=list, max_length=MAX_CHAT_ATTACHMENT_DOCUMENT_IDS
    )
    attached_file_ids: list[str] = Field(
        default_factory=list, max_length=MAX_CHAT_ATTACHMENT_FILE_IDS
    )

    @model_validator(mode="after")
    def validate_response_modes(self) -> ChatStreamRequest:
        self.context_document_ids = list(dict.fromkeys(self.context_document_ids))
        self.context_knowledge_base_ids = list(dict.fromkeys(self.context_knowledge_base_ids))
        self.attached_document_ids = list(dict.fromkeys(self.attached_document_ids))
        self.attached_file_ids = list(dict.fromkeys(self.attached_file_ids))
        if self.deep_research and self.response_mode == "image":
            raise ValueError("Deep Research e geração de imagem são modos mutuamente exclusivos.")
        if self.reasoning_summary != "off" and self.response_mode != "text":
            raise ValueError("Resumo oficial de raciocínio está disponível apenas no modo texto.")
        if self.reasoning_summary != "off" and self.deep_research:
            raise ValueError(
                "Resumo oficial de raciocínio e Deep Research são modos mutuamente exclusivos."
            )
        return self


class PlatformFile(BaseModel):
    id: str = Field(default_factory=lambda: new_id("file"))
    filename: str
    original_filename: str
    content_type: str | None = None
    size_bytes: int = 0
    storage_path: str
    checksum_sha256: str | None = None
    duplicate_of_id: str | None = None
    source: Literal[
        "upload", "chat_attachment", "chatgpt_import", "generated", "knowledge_base"
    ] = "upload"
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class PlatformFileCreate(BaseModel):
    filename: str
    original_filename: str | None = None
    content_type: str | None = None
    size_bytes: int = 0
    storage_path: str
    checksum_sha256: str | None = None
    duplicate_of_id: str | None = None
    source: Literal[
        "upload", "chat_attachment", "chatgpt_import", "generated", "knowledge_base"
    ] = "upload"
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlatformFileUpdate(BaseModel):
    filename: str | None = None
    original_filename: str | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


class KnowledgeCategory(BaseModel):
    id: str = Field(default_factory=lambda: new_id("kbcat"))
    name: str
    description: str = ""
    color: str = "#f0b84d"
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class KnowledgeCategoryCreate(BaseModel):
    name: str
    description: str = ""
    color: str = "#f0b84d"


class KnowledgeCategoryUpdate(KnowledgeCategoryCreate):
    pass


class KnowledgeBase(BaseModel):
    id: str = Field(default_factory=lambda: new_id("kb"))
    name: str
    description: str = ""
    scope: str = ""
    color: str = "#f0b84d"
    tags: list[str] = Field(default_factory=list)
    max_documents_per_query: int = Field(default=8, ge=1, le=20)
    max_chunks_per_document: int = Field(default=3, ge=1, le=10)
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class KnowledgeBaseCreate(BaseModel):
    name: str
    description: str = ""
    scope: str = ""
    color: str = "#f0b84d"
    tags: list[str] = Field(default_factory=list)
    max_documents_per_query: int = Field(default=8, ge=1, le=20)
    max_chunks_per_document: int = Field(default=3, ge=1, le=10)
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeBaseUpdate(KnowledgeBaseCreate):
    pass


class KnowledgeBaseDocument(BaseModel):
    id: str = Field(default_factory=lambda: new_id("kbdoc"))
    knowledge_base_id: str
    document_id: str
    priority: int = Field(default=0, ge=0, le=10)
    note: str = ""
    tags: list[str] = Field(default_factory=list)
    enabled: bool = True
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class KnowledgeBaseDocumentCreate(BaseModel):
    document_id: str
    priority: int = Field(default=0, ge=0, le=10)
    note: str = ""
    tags: list[str] = Field(default_factory=list)
    enabled: bool = True


class KnowledgeBaseDocumentUpdate(BaseModel):
    priority: int = Field(default=0, ge=0, le=10)
    note: str = ""
    tags: list[str] = Field(default_factory=list)
    enabled: bool = True


class ProjectContextConfig(BaseModel):
    scope_mode: Literal["project_only", "project_plus_global", "global_only"] = "project_only"
    max_documents: int = Field(default=20, ge=1, le=20)
    folder_ids: list[str] = Field(default_factory=list)
    document_ids: list[str] = Field(default_factory=list)
    knowledge_base_ids: list[str] = Field(default_factory=list)
    file_ids: list[str] = Field(default_factory=list)
    prompt_ids: list[str] = Field(default_factory=list)


class Project(BaseModel):
    id: str = Field(default_factory=lambda: new_id("project"))
    name: str
    description: str = ""
    color: str = "#f0b84d"
    is_general: bool = False
    context: ProjectContextConfig = Field(default_factory=ProjectContextConfig)
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    color: str = "#f0b84d"
    is_general: bool = False
    context: ProjectContextConfig = Field(default_factory=ProjectContextConfig)


class ProjectUpdate(BaseModel):
    name: str
    description: str = ""
    color: str = "#f0b84d"
    is_general: bool = False
    context: ProjectContextConfig = Field(default_factory=ProjectContextConfig)


class ProjectFolder(BaseModel):
    id: str = Field(default_factory=lambda: new_id("folder"))
    project_id: str
    parent_id: str | None = None
    name: str
    depth: int = Field(default=0, ge=0, le=5)
    path: str = ""
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class ProjectFolderCreate(BaseModel):
    project_id: str
    parent_id: str | None = None
    name: str


class ProjectFolderUpdate(BaseModel):
    name: str


class ProjectFolderDeleteResult(BaseModel):
    folder_id: str
    deleted_folder_ids: list[str] = Field(default_factory=list)
    deleted_chat_session_ids: list[str] = Field(default_factory=list)


class ModelingCapability(BaseModel):
    software: ModelingSoftware
    connected: bool = False
    transport: Literal["stdio", "http", "mock"] = "mock"
    tools: list[str] = Field(default_factory=list)
    status: str = "adapter_mock"
    detail: str = ""


class ModelingCapabilities(BaseModel):
    mode: Literal["local_mcp"] = "local_mcp"
    default_execution_mode: ModelingExecutionMode = ModelingExecutionMode.approval_required
    safety_notes: list[str] = Field(default_factory=list)
    adapters: list[ModelingCapability] = Field(default_factory=list)


class ModelingSession(BaseModel):
    id: str = Field(default_factory=lambda: new_id("m3d_session"))
    software: ModelingSoftware
    project_id: str | None = None
    status: Literal["starting", "connected", "mock", "failed", "closed"] = "mock"
    mcp_server: str
    host_pid: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class ModelingSessionStart(BaseModel):
    software: ModelingSoftware
    project_id: str | None = None
    force_mock: bool = True

    @model_validator(mode="after")
    def validate_software(self) -> ModelingSessionStart:
        if self.software == ModelingSoftware.auto:
            raise ValueError("Escolha blender ou fusion para iniciar uma sessão 3D.")
        return self


class ModelingPlanStep(BaseModel):
    id: str = Field(default_factory=lambda: new_id("m3d_step"))
    seq: int = Field(ge=1)
    title: str
    software: ModelingSoftware
    tool_name: str
    risk_level: ModelingRiskLevel = ModelingRiskLevel.low
    approval_required: bool = False
    status: ModelingStepStatus = ModelingStepStatus.pending
    input_json: dict[str, Any] = Field(default_factory=dict)
    output_json: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    approved_at: datetime | None = None
    completed_at: datetime | None = None


class ModelingPlan(BaseModel):
    id: str = Field(default_factory=lambda: new_id("m3d_plan"))
    project_id: str | None = None
    conversation_id: str | None = None
    prompt: str
    mode: ModelingExecutionMode = ModelingExecutionMode.approval_required
    software_choice: ModelingSoftware
    confidence: float = Field(default=0.7, ge=0, le=1)
    approval_required: bool = True
    status: ModelingPlanStatus = ModelingPlanStatus.waiting_approval
    rationale: str = ""
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    knowledge_base_ids: list[str] = Field(default_factory=list)
    steps: list[ModelingPlanStep] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class ModelingPlanCreate(BaseModel):
    prompt: str = Field(min_length=1)
    project_id: str | None = None
    conversation_id: str | None = None
    mode: ModelingExecutionMode = ModelingExecutionMode.approval_required
    software_override: ModelingSoftware | None = None
    knowledge_base_ids: list[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def normalize_software_override(self) -> ModelingPlanCreate:
        if self.software_override == ModelingSoftware.auto:
            self.software_override = None
        self.knowledge_base_ids = list(dict.fromkeys(self.knowledge_base_ids))
        return self


class ModelingApprovalRequest(BaseModel):
    decision: ModelingApprovalDecision
    reason: str = ""


class ModelingSnapshot(BaseModel):
    id: str = Field(default_factory=lambda: new_id("m3d_snapshot"))
    project_id: str | None = None
    plan_id: str | None = None
    label: str
    reason: str = ""
    manifest: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=now_utc)


class ModelingSnapshotCreate(BaseModel):
    project_id: str | None = None
    plan_id: str | None = None
    label: str = "Snapshot 3D"
    reason: str = ""


class ModelingExecutionResult(BaseModel):
    plan: ModelingPlan
    executed_step_ids: list[str] = Field(default_factory=list)
    blocked_step_ids: list[str] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)


class Document(BaseModel):
    id: str = Field(default_factory=lambda: new_id("doc"))
    title: str
    source_type: Literal["pdf", "markdown", "csv", "txt", "docx", "image", "html", "unknown"] = (
        "unknown"
    )
    original_path: str | None = None
    storage_path: str | None = None
    category_id: str | None = None
    folder_id: str | None = None
    pinned: bool = False
    tags: list[str] = Field(default_factory=list)
    project_id: str | None = None
    indexed: bool = False
    index_status: JobStatus = JobStatus.pending
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class DocumentCreate(BaseModel):
    title: str
    source_type: Literal["pdf", "markdown", "csv", "txt", "docx", "image", "html", "unknown"] = (
        "unknown"
    )
    original_path: str | None = None
    category_id: str | None = None
    folder_id: str | None = None
    pinned: bool = False
    tags: list[str] = Field(default_factory=list)
    project_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentTextCreate(BaseModel):
    title: str
    content: str = Field(min_length=1)
    source_type: Literal["markdown", "txt", "csv", "html"] = "txt"
    category_id: str | None = None
    folder_id: str | None = None
    pinned: bool = False
    tags: list[str] = Field(default_factory=list)
    project_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentFromFileCreate(BaseModel):
    file_id: str
    category_id: str | None = None
    folder_id: str | None = None
    pinned: bool = False
    tags: list[str] = Field(default_factory=list)
    project_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=8, ge=1, le=20)
    project_id: str | None = None
    project_scope_mode: Literal["project_only", "project_plus_global", "global_only"] = (
        "project_only"
    )
    folder_ids: list[str] = Field(default_factory=list)
    category_ids: list[str] = Field(default_factory=list)
    knowledge_base_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class DocumentBatchRequest(BaseModel):
    ids: list[str] = Field(default_factory=list, max_length=200)


class DocumentSearchResult(BaseModel):
    document_id: str
    title: str
    score: float
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentPage(BaseModel):
    items: list[Document] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0
    has_more: bool = False


class PlatformFilePage(BaseModel):
    items: list[PlatformFile] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0
    has_more: bool = False


class PlatformFileIndexingStatus(BaseModel):
    total_files: int = 0
    documents_linked: int = 0
    completed_files: int = 0
    pending_files: int = 0
    running_files: int = 0
    failed_files: int = 0
    missing_documents: int = 0
    backlog_files: int = 0
    indexing_in_background: bool = False
    updated_at: datetime = Field(default_factory=now_utc)


class ServerStatus(BaseModel):
    online: bool = True
    app_name: str = "Truth's Forge AI"
    persona: str = "JUDITE"
    environment: str
    public_base_url: str
    vector_store: str = "qdrant"
    database: str = "postgresql"
    mobile_access: str = "Tailscale/WireGuard recomendado"
    features: dict[str, bool]


class ChatGPTImportSummary(BaseModel):
    source_filename: str
    conversations_found: int = 0
    sessions_imported: int = 0
    sessions_skipped: int = 0
    messages_imported: int = 0
    messages_skipped: int = 0
    errors: list[str] = Field(default_factory=list)


class ChatGPTImportJob(BaseModel):
    id: str = Field(default_factory=lambda: new_id("import"))
    kind: Literal["chatgpt"] = "chatgpt"
    status: JobStatus = JobStatus.pending
    source_filename: str
    file_path: str
    platform_file_id: str | None = None
    file_size_bytes: int
    total_bytes: int | None = None
    processed_bytes: int = 0
    progress_percent: float = 0
    current_step: str = "Aguardando processamento"
    summary: ChatGPTImportSummary | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)
    completed_at: datetime | None = None
