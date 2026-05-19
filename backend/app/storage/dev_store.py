from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import Any, TypeVar

from app.core.config import settings
from app.core.contracts import (
    DEFAULT_GENERAL_PROJECT_ID,
    DEFAULT_GENERAL_PROJECT_NAME,
    MODELING_TRACE_DEVSTORE_MAX_EVENTS,
    Agent,
    AgentCreate,
    AgentGraph,
    AgentLLMConfig,
    AgentUpdate,
    AuditEvent,
    ChatGPTImportJob,
    ChatMessage,
    ChatModelingStage,
    ChatSession,
    ChatSessionCreate,
    ChatSessionWithMessages,
    ChatStreamRequest,
    CostPolicy,
    Document,
    DocumentCreate,
    JobStatus,
    KnowledgeBase,
    KnowledgeBaseCreate,
    KnowledgeBaseDocument,
    KnowledgeBaseDocumentCreate,
    KnowledgeBaseDocumentUpdate,
    KnowledgeBaseUpdate,
    KnowledgeCategory,
    KnowledgeCategoryCreate,
    KnowledgeCategoryUpdate,
    ModelCapability,
    ModelConfig,
    ModelingModelVersion,
    ModelingPlan,
    ModelingPrintabilityReport,
    ModelingSession,
    ModelingSnapshot,
    ModelingToolCall,
    ModelingTraceEvent,
    ModelingTraceLevel,
    ModelingTraceSource,
    ModelUpsert,
    PermissionMode,
    PermissionPolicy,
    PlatformFile,
    PlatformFileCreate,
    PlatformFileUpdate,
    Project,
    ProjectCreate,
    ProjectFolder,
    ProjectFolderCreate,
    ProjectFolderUpdate,
    ProjectUpdate,
    Prompt,
    PromptCreate,
    ProviderName,
    now_utc,
)

T = TypeVar("T")


def _dump_model(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return json.loads(model.json())


def default_seed_data() -> dict[str, Any]:
    models = [
        ModelConfig(
            id="openai/default-chat",
            provider=ProviderName.openai,
            display_name="OpenAI - modelo configurável",
            provider_model_id="gpt-4o",
            default=True,
            capabilities=[
                ModelCapability.chat,
                ModelCapability.vision,
                ModelCapability.json,
                ModelCapability.tool_calling,
            ],
            notes="Defina o modelo real e preços no painel antes de usar em produção.",
        ),
        ModelConfig(
            id="anthropic/default-chat",
            provider=ProviderName.anthropic,
            display_name="Anthropic - modelo configurável",
            capabilities=[
                ModelCapability.chat,
                ModelCapability.long_context,
                ModelCapability.tool_calling,
            ],
            notes="Placeholder configurável para evitar nomes/preços hardcoded.",
        ),
        ModelConfig(
            id="google/default-chat",
            provider=ProviderName.google,
            display_name="Google Gemini - modelo configurável",
            capabilities=[
                ModelCapability.chat,
                ModelCapability.vision,
                ModelCapability.long_context,
            ],
            notes="Placeholder configurável para evitar nomes/preços hardcoded.",
        ),
        ModelConfig(
            id="openai/default-image",
            provider=ProviderName.openai,
            display_name="OpenAI - GPT Image 2 (padrão)",
            provider_model_id="gpt-image-2",
            capabilities=[ModelCapability.image_generation],
            notes=(
                "Modelo padrão para o atalho de imagem. "
                "Você pode escolher outro modelo por mensagem no chat."
            ),
        ),
        ModelConfig(
            id="openai/gpt-image-1-5",
            provider=ProviderName.openai,
            display_name="OpenAI - GPT Image 1.5",
            provider_model_id="gpt-image-1.5",
            capabilities=[ModelCapability.image_generation],
            notes="Modelo de alta qualidade para geração e edição de imagens.",
        ),
        ModelConfig(
            id="openai/chatgpt-image-latest",
            provider=ProviderName.openai,
            display_name="OpenAI - chatgpt-image-latest",
            provider_model_id="chatgpt-image-latest",
            capabilities=[ModelCapability.image_generation],
            notes="Alias de imagem usado pelo ChatGPT.",
        ),
        ModelConfig(
            id="openai/gpt-image-1-mini",
            provider=ProviderName.openai,
            display_name="OpenAI - GPT Image 1 mini",
            provider_model_id="gpt-image-1-mini",
            capabilities=[ModelCapability.image_generation],
            notes="Versão mais econômica para geração de imagem.",
        ),
        ModelConfig(
            id="openai/gpt-image-1",
            provider=ProviderName.openai,
            display_name="OpenAI - GPT Image 1",
            provider_model_id="gpt-image-1",
            capabilities=[ModelCapability.image_generation],
            notes="Modelo anterior de imagem da OpenAI; mantenha por compatibilidade.",
        ),
        ModelConfig(
            id="openai/deep-research",
            provider=ProviderName.openai,
            display_name="OpenAI - Deep Research",
            provider_model_id="o4-mini-deep-research",
            capabilities=[ModelCapability.deep_research],
            temperature=None,
            top_p=None,
            max_output_tokens=8192,
            notes=(
                "Modelo usado pelo atalho Pesquisa OpenAI. "
                "Usa Responses API com web_search_preview e limite de chamadas de ferramenta."
            ),
        ),
        ModelConfig(
            id="google/default-image",
            provider=ProviderName.google,
            display_name="Google - geração de imagem configurável",
            capabilities=[ModelCapability.image_generation],
            notes="Configure o modelo real do provedor antes de usar.",
        ),
    ]
    judite = Agent(
        name="JUDITE",
        description="Orquestradora central do Truth's Forge AI.",
        system_prompt=(
            "Você é JUDITE, a persona central do Truth's Forge AI. "
            "Responda em português do Brasil, proteja custos e privacidade, "
            "e peça confirmação antes de ações perigosas."
        ),
        model_id="openai/default-chat",
        llm_config=AgentLLMConfig(
            provider=ProviderName.openai,
            temperature=1,
            top_p=1,
            max_output_tokens=2048,
            response_format="text",
            tool_choice="auto",
            parallel_tool_calls=True,
        ),
        role="orchestrator",
        collaboration_mode="parallel",
        tags=["sistema", "orquestração"],
        tools_allowed=["rag.search", "prompt.render", "audit.read"],
    )
    judite.permission_policy = PermissionPolicy(
        agent_id=judite.id,
        dangerous_action_default=PermissionMode.ask,
        tool_permissions={
            "rag.search": PermissionMode.allow,
            "prompt.render": PermissionMode.allow,
            "audit.read": PermissionMode.allow,
            "python.run": PermissionMode.ask,
            "filesystem.write": PermissionMode.ask,
        },
    )
    judite.graph = AgentGraph(agent_id=judite.id)
    starter_prompt = Prompt(
        title="Planejamento técnico",
        template=(
            "Contexto: {{contexto}}\n"
            "Objetivo: {{objetivo}}\n"
            "Gere um plano prático, com riscos, critérios de aceite e próximos passos."
        ),
        tags=["planejamento", "engenharia"],
        favorite=True,
    )
    cost_policy = CostPolicy(monthly_budget_brl=settings.monthly_budget_brl)
    default_category = KnowledgeCategory(
        name="Geral",
        description="Contextos e arquivos ainda sem uma categoria específica.",
        color="#f0b84d",
    )
    default_knowledge_base = KnowledgeBase(
        id="kb_general",
        name="Base geral",
        description="Coleção curada inicial para documentos existentes e contexto comum.",
        scope="Conteúdo geral disponível para projetos e agentes quando atrelado explicitamente.",
        color="#f0b84d",
        tags=["geral"],
        max_documents_per_query=8,
        max_chunks_per_document=3,
    )
    general_project = Project(
        id=DEFAULT_GENERAL_PROJECT_ID,
        name=DEFAULT_GENERAL_PROJECT_NAME,
        description="Projeto global para conteúdos não vinculados a um projeto específico.",
        color="#f0b84d",
        is_general=True,
    )
    return {
        "models": [_dump_model(model) for model in models],
        "agents": [_dump_model(judite)],
        "projects": [_dump_model(general_project)],
        "project_folders": [],
        "knowledge_categories": [_dump_model(default_category)],
        "knowledge_bases": [_dump_model(default_knowledge_base)],
        "knowledge_base_documents": [],
        "prompts": [_dump_model(starter_prompt)],
        "chat_sessions": [],
        "messages": [],
        "documents": [],
        "platform_files": [],
        "import_jobs": [],
        "modeling_sessions": [],
        "modeling_plans": [],
        "modeling_snapshots": [],
        "modeling_tool_calls": [],
        "modeling_printability_reports": [],
        "modeling_model_versions": [],
        "audit_events": [],
        "cost_policy": _dump_model(cost_policy),
    }


class DevStore:
    """Small JSON-backed store for local development before Postgres repositories land."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = RLock()
        self._data = self._load_or_seed()
        self._ensure_seed_models()
        self._migrate_projects_and_folders()

    def _load_or_seed(self) -> dict[str, Any]:
        if self.path.exists():
            try:
                raw = self.path.read_text(encoding="utf-8")
                if not raw.strip():
                    raise json.JSONDecodeError("empty file", raw, 0)
                return json.loads(raw)
            except (OSError, json.JSONDecodeError):
                data = self._seed()
                self._write(data)
                return data
        data = self._seed()
        self._write(data)
        return data

    def _write(self, data: dict[str, Any] | None = None) -> None:
        target = data if data is not None else self._data
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(target, ensure_ascii=False, indent=2), encoding="utf-8")

    def _seed(self) -> dict[str, Any]:
        return default_seed_data()

    def _ensure_seed_models(self) -> None:
        seed_models = default_seed_data().get("models", [])
        existing_models = self._data.setdefault("models", [])
        existing_by_id = {str(m.get("id")): m for m in existing_models if isinstance(m, dict)}
        changed = False
        for model in seed_models:
            if not isinstance(model, dict):
                continue
            model_id = str(model.get("id", ""))
            if not model_id:
                continue
            if model_id not in existing_by_id:
                existing_models.append(model)
                existing_by_id[model_id] = model
                changed = True
            else:
                # Propaga provider_model_id da seed para modelos existentes que estejam sem ele
                existing = existing_by_id[model_id]
                seed_pmid = model.get("provider_model_id")
                if seed_pmid and not existing.get("provider_model_id"):
                    existing["provider_model_id"] = seed_pmid
                    changed = True
        if changed:
            self._write(self._data)

    def _general_project(self) -> Project:
        projects = self._list("projects", Project)
        existing = next((project for project in projects if project.is_general), None)
        if existing is not None:
            return existing
        fallback = next(
            (project for project in projects if project.id == DEFAULT_GENERAL_PROJECT_ID), None
        )
        if fallback is not None:
            return fallback
        created = Project(
            id=DEFAULT_GENERAL_PROJECT_ID,
            name=DEFAULT_GENERAL_PROJECT_NAME,
            description="Projeto global para conteúdos não vinculados a um projeto específico.",
            color="#f0b84d",
            is_general=True,
        )
        self._data["projects"].append(_dump_model(created))
        return created

    def _build_folder_path(
        self, project_id: str, parent_id: str | None, name: str
    ) -> tuple[int, str]:
        normalized_name = name.strip()
        if not parent_id:
            return 0, normalized_name
        parent = next(
            (
                ProjectFolder(**item)
                for item in self._data.get("project_folders", [])
                if item["id"] == parent_id and item["project_id"] == project_id
            ),
            None,
        )
        if parent is None:
            raise ValueError("Pasta pai não encontrada no projeto.")
        depth = parent.depth + 1
        if depth > 5:
            raise ValueError("Apenas 5 subníveis de pasta são permitidos.")
        return depth, f"{parent.path}/{normalized_name}".strip("/")

    def _migrate_projects_and_folders(self) -> None:
        self._ensure_key("projects", default_seed_data()["projects"])
        self._ensure_key("project_folders", [])
        self._ensure_key("knowledge_categories", default_seed_data()["knowledge_categories"])
        self._ensure_key("knowledge_bases", default_seed_data()["knowledge_bases"])
        self._ensure_key("knowledge_base_documents", [])
        self._ensure_key("documents", [])
        self._ensure_key("prompts", [])
        self._ensure_key("chat_sessions", [])
        self._ensure_key("platform_files", [])
        self._ensure_key("modeling_sessions", [])
        self._ensure_key("modeling_plans", [])
        self._ensure_key("modeling_snapshots", [])
        self._ensure_key("modeling_tool_calls", [])
        self._ensure_key("modeling_printability_reports", [])
        self._ensure_key("modeling_model_versions", [])

        changed = False
        general_project = self._general_project()
        general_project_id = general_project.id

        for project in self._data["projects"]:
            context = project.get("context")
            if not isinstance(context, dict):
                project["context"] = {
                    "scope_mode": "project_only",
                    "max_documents": 20,
                    "folder_ids": [],
                    "document_ids": [],
                    "knowledge_base_ids": [],
                    "file_ids": [],
                    "prompt_ids": [],
                }
                changed = True
                continue
            if context.get("max_documents") != 20:
                context["max_documents"] = 20
                changed = True
            if context.get("scope_mode") not in {
                "project_only",
                "project_plus_global",
                "global_only",
            }:
                context["scope_mode"] = "project_only"
                changed = True
            if not isinstance(context.get("knowledge_base_ids"), list):
                context["knowledge_base_ids"] = []
                changed = True

        category_to_folder_id: dict[str, str] = {}
        existing_folders = [ProjectFolder(**item) for item in self._data["project_folders"]]
        for folder in existing_folders:
            category_id = (
                folder.path.split("legacy:")[-1] if folder.path.startswith("legacy:") else ""
            )
            if category_id:
                category_to_folder_id[category_id] = folder.id

        for category in self._list("knowledge_categories", KnowledgeCategory):
            if category.id in category_to_folder_id:
                continue
            folder_name = category.name.strip() or "Categoria"
            folder = ProjectFolder(
                project_id=general_project_id,
                parent_id=None,
                name=folder_name,
                depth=0,
                path=f"legacy:{category.id}",
            )
            self._data["project_folders"].append(_dump_model(folder))
            category_to_folder_id[category.id] = folder.id
            changed = True

        for document in self._data["documents"]:
            if not document.get("project_id"):
                document["project_id"] = general_project_id
                changed = True
            if not document.get("folder_id") and document.get("category_id"):
                mapped = category_to_folder_id.get(str(document["category_id"]))
                if mapped:
                    document["folder_id"] = mapped
                    changed = True

        for session in self._data["chat_sessions"]:
            if not session.get("project_id"):
                session["project_id"] = general_project_id
                changed = True
            if "folder_id" not in session:
                session["folder_id"] = None
                changed = True
            if not isinstance(session.get("context_project_ids"), list):
                session["context_project_ids"] = []
                changed = True
            if not isinstance(session.get("context_document_ids"), list):
                session["context_document_ids"] = []
                changed = True
            if not isinstance(session.get("context_knowledge_base_ids"), list):
                session["context_knowledge_base_ids"] = []
                changed = True

        for platform_file in self._data["platform_files"]:
            metadata = platform_file.get("metadata")
            if not isinstance(metadata, dict):
                platform_file["metadata"] = {}
                changed = True
                metadata = platform_file["metadata"]
            if "project_id" not in metadata:
                metadata["project_id"] = general_project_id
                changed = True

        for agent in self._data["agents"]:
            allowed_project_ids = agent.get("allowed_project_ids")
            if not isinstance(allowed_project_ids, list) or not allowed_project_ids:
                agent["allowed_project_ids"] = [general_project_id]
                changed = True
            if not isinstance(agent.get("knowledge_base_ids"), list):
                agent["knowledge_base_ids"] = []
                changed = True

        changed = self._migrate_default_knowledge_base_links() or changed

        if changed:
            self._write()

    def _ensure_key(self, key: str, default: Any) -> None:
        if key not in self._data:
            self._data[key] = default
            self._write()

    def _list(self, key: str, model_type: type[T]) -> list[T]:
        return [model_type(**item) for item in self._data[key]]

    def list_models(self) -> list[ModelConfig]:
        self._ensure_key("models", default_seed_data()["models"])
        known_ids = {item["id"] for item in self._data["models"]}
        missing = [item for item in default_seed_data()["models"] if item["id"] not in known_ids]
        if missing:
            self._data["models"].extend(missing)
            self._write()
        return self._list("models", ModelConfig)

    def upsert_model(self, payload: ModelUpsert) -> ModelConfig:
        with self._lock:
            model = ModelConfig(**_dump_model(payload))
            models = [item for item in self._data["models"] if item["id"] != model.id]
            if model.default:
                for item in models:
                    item["default"] = False
            models.append(_dump_model(model))
            self._data["models"] = models
            self._write()
            return model

    def list_agents(self) -> list[Agent]:
        return self._list("agents", Agent)

    def _normalize_agent_project_access(self, allowed_project_ids: list[str]) -> list[str]:
        general_project_id = self._general_project().id
        known_ids = {project.id for project in self.list_projects()}
        normalized: list[str] = []
        for raw_id in allowed_project_ids:
            if raw_id not in known_ids:
                continue
            if raw_id in normalized:
                continue
            normalized.append(raw_id)
        if not normalized:
            return [general_project_id]
        return normalized

    def _normalize_knowledge_base_ids(self, knowledge_base_ids: list[str]) -> list[str]:
        known_ids = {knowledge_base.id for knowledge_base in self.list_knowledge_bases()}
        normalized: list[str] = []
        for raw_id in knowledge_base_ids:
            if raw_id not in known_ids or raw_id in normalized:
                continue
            normalized.append(raw_id)
        return normalized

    def _normalize_project_context(self, raw_context: dict[str, Any]) -> dict[str, Any]:
        context = dict(raw_context or {})
        context["max_documents"] = 20
        if context.get("scope_mode") not in {
            "project_only",
            "project_plus_global",
            "global_only",
        }:
            context["scope_mode"] = "project_only"
        context["knowledge_base_ids"] = self._normalize_knowledge_base_ids(
            list(context.get("knowledge_base_ids") or [])
        )
        context.setdefault("folder_ids", [])
        context.setdefault("document_ids", [])
        context.setdefault("file_ids", [])
        context.setdefault("prompt_ids", [])
        return context

    def _migrate_default_knowledge_base_links(self) -> bool:
        items = self._data.get("knowledge_base_documents", [])
        if items or not self._data.get("documents"):
            return False
        bases = self._list("knowledge_bases", KnowledgeBase)
        default_base = next(
            (base for base in bases if base.id == "kb_general"), bases[0] if bases else None
        )
        if default_base is None:
            default_base = KnowledgeBase(
                id="kb_general",
                name="Base geral",
                description="Coleção curada inicial para documentos existentes e contexto comum.",
                scope="Conteúdo geral disponível quando atrelado explicitamente.",
                tags=["geral"],
            )
            self._data["knowledge_bases"].append(_dump_model(default_base))
        for document in self._list("documents", Document):
            if document.index_status not in {JobStatus.completed, "completed"}:
                continue
            item = KnowledgeBaseDocument(
                knowledge_base_id=default_base.id,
                document_id=document.id,
                note="Migrado automaticamente dos documentos existentes.",
                tags=document.tags,
            )
            items.append(_dump_model(item))
        return bool(items)

    def list_projects(self) -> list[Project]:
        self._ensure_key("projects", default_seed_data()["projects"])
        projects = self._list("projects", Project)
        return sorted(
            projects, key=lambda item: (not item.is_general, item.updated_at), reverse=True
        )

    def create_project(self, payload: ProjectCreate) -> Project:
        with self._lock:
            raw = _dump_model(payload)
            raw["context"] = self._normalize_project_context(raw.get("context") or {})
            project = Project(**raw)
            self._data["projects"].append(_dump_model(project))
            self._write()
            return project

    def update_project(self, project_id: str, payload: ProjectUpdate) -> Project:
        with self._lock:
            raw = _dump_model(payload)
            raw["context"] = self._normalize_project_context(raw.get("context") or {})
            existing = next(
                (Project(**item) for item in self._data["projects"] if item["id"] == project_id),
                None,
            )
            if existing is None:
                project = Project(id=project_id, **raw)
            else:
                project = Project(
                    **{
                        **_dump_model(existing),
                        **raw,
                        "id": existing.id,
                        "created_at": existing.created_at,
                        "updated_at": now_utc(),
                    }
                )
            self._data["projects"] = [
                _dump_model(project) if item["id"] == project_id else item
                for item in self._data["projects"]
            ]
            if not any(item["id"] == project_id for item in self._data["projects"]):
                self._data["projects"].append(_dump_model(project))
            self._write()
            return project

    def list_project_folders(self, project_id: str | None = None) -> list[ProjectFolder]:
        self._ensure_key("project_folders", [])
        folders = self._list("project_folders", ProjectFolder)
        if project_id:
            folders = [folder for folder in folders if folder.project_id == project_id]
        return sorted(folders, key=lambda item: (item.depth, item.path, item.name))

    def create_project_folder(self, payload: ProjectFolderCreate) -> ProjectFolder:
        with self._lock:
            depth, path = self._build_folder_path(
                payload.project_id, payload.parent_id, payload.name
            )
            folder = ProjectFolder(
                project_id=payload.project_id,
                parent_id=payload.parent_id,
                name=payload.name.strip(),
                depth=depth,
                path=path,
            )
            self._data["project_folders"].append(_dump_model(folder))
            self._write()
            return folder

    def update_project_folder(self, folder_id: str, payload: ProjectFolderUpdate) -> ProjectFolder:
        with self._lock:
            existing = next(
                (
                    ProjectFolder(**item)
                    for item in self._data["project_folders"]
                    if item["id"] == folder_id
                ),
                None,
            )
            if existing is None:
                raise KeyError(folder_id)
            depth, path = self._build_folder_path(
                existing.project_id, existing.parent_id, payload.name
            )
            folder = ProjectFolder(
                **{
                    **_dump_model(existing),
                    "name": payload.name.strip(),
                    "depth": depth,
                    "path": path,
                    "updated_at": now_utc(),
                }
            )
            self._data["project_folders"] = [
                _dump_model(folder) if item["id"] == folder_id else item
                for item in self._data["project_folders"]
            ]
            self._write()
            return folder

    def _folder_descendants(
        self, project_id: str, folder_id: str
    ) -> tuple[set[str], list[ProjectFolder]]:
        folders = [folder for folder in self.list_project_folders(project_id)]
        by_parent: dict[str | None, list[ProjectFolder]] = {}
        for folder in folders:
            by_parent.setdefault(folder.parent_id, []).append(folder)

        descendants: set[str] = set()
        stack = [folder_id]
        while stack:
            current = stack.pop()
            if current in descendants:
                continue
            descendants.add(current)
            for child in by_parent.get(current, []):
                stack.append(child.id)
        return descendants, folders

    def delete_project_folder(self, folder_id: str) -> tuple[list[str], list[str]]:
        with self._lock:
            existing = next(
                (
                    ProjectFolder(**item)
                    for item in self._data["project_folders"]
                    if item["id"] == folder_id
                ),
                None,
            )
            if existing is None:
                raise KeyError(folder_id)

            deleted_folder_ids, _all_folders = self._folder_descendants(
                existing.project_id, folder_id
            )
            deleted_chat_session_ids = [
                item["id"]
                for item in self._data["chat_sessions"]
                if item.get("folder_id") in deleted_folder_ids
                and item.get("project_id") == existing.project_id
            ]

            self._data["project_folders"] = [
                item
                for item in self._data["project_folders"]
                if item["id"] not in deleted_folder_ids
            ]
            self._data["chat_sessions"] = [
                item
                for item in self._data["chat_sessions"]
                if item["id"] not in deleted_chat_session_ids
            ]
            self._data["messages"] = [
                item
                for item in self._data["messages"]
                if item["session_id"] not in set(deleted_chat_session_ids)
            ]
            self._write()
            return sorted(deleted_folder_ids), deleted_chat_session_ids

    def create_agent(self, payload: AgentCreate) -> Agent:
        with self._lock:
            raw = _dump_model(payload)
            raw["allowed_project_ids"] = self._normalize_agent_project_access(
                list(raw.get("allowed_project_ids") or [])
            )
            raw["knowledge_base_ids"] = self._normalize_knowledge_base_ids(
                list(raw.get("knowledge_base_ids") or [])
            )
            agent = Agent(**raw)
            agent.permission_policy = raw.get("permission_policy") or PermissionPolicy(
                agent_id=agent.id
            )
            agent.graph = AgentGraph(agent_id=agent.id)
            self._data["agents"].append(_dump_model(agent))
            self._write()
            return agent

    def update_agent(self, agent_id: str, payload: AgentUpdate) -> Agent:
        with self._lock:
            existing = next(
                (Agent(**item) for item in self._data["agents"] if item["id"] == agent_id), None
            )
            if existing is None:
                raw = _dump_model(payload)
                raw["allowed_project_ids"] = self._normalize_agent_project_access(
                    list(raw.get("allowed_project_ids") or [])
                )
                raw["knowledge_base_ids"] = self._normalize_knowledge_base_ids(
                    list(raw.get("knowledge_base_ids") or [])
                )
                agent = Agent(id=agent_id, **raw)
                agent.permission_policy = raw.get("permission_policy") or PermissionPolicy(
                    agent_id=agent.id
                )
                agent.graph = AgentGraph(agent_id=agent.id)
            else:
                raw = _dump_model(payload)
                raw["allowed_project_ids"] = self._normalize_agent_project_access(
                    list(raw.get("allowed_project_ids") or [])
                )
                raw["knowledge_base_ids"] = self._normalize_knowledge_base_ids(
                    list(raw.get("knowledge_base_ids") or [])
                )
                agent = Agent(
                    **{
                        **_dump_model(existing),
                        **raw,
                        "id": existing.id,
                        "created_at": existing.created_at,
                        "updated_at": now_utc(),
                    }
                )
            self._data["agents"] = [
                _dump_model(agent) if item["id"] == agent_id else item
                for item in self._data["agents"]
            ]
            if not any(item["id"] == agent_id for item in self._data["agents"]):
                self._data["agents"].append(_dump_model(agent))
            self._write()
            return agent

    def list_prompts(self) -> list[Prompt]:
        return self._list("prompts", Prompt)

    def create_prompt(self, payload: PromptCreate) -> Prompt:
        with self._lock:
            prompt = Prompt(**_dump_model(payload))
            self._data["prompts"].append(_dump_model(prompt))
            self._write()
            return prompt

    def list_documents(self) -> list[Document]:
        self._ensure_key("documents", [])
        return self._list("documents", Document)

    def get_document(self, document_id: str) -> Document | None:
        self._ensure_key("documents", [])
        return next(
            (Document(**item) for item in self._data["documents"] if item["id"] == document_id),
            None,
        )

    def create_document(self, payload: DocumentCreate) -> Document:
        with self._lock:
            document = Document(**_dump_model(payload))
            self._data["documents"].append(_dump_model(document))
            self._write()
            return document

    def delete_document(self, document_id: str) -> Document | None:
        with self._lock:
            existing = self.get_document(document_id)
            if existing is None:
                return None
            self._data["documents"] = [
                item for item in self._data["documents"] if item["id"] != document_id
            ]
            self._data["knowledge_base_documents"] = [
                item
                for item in self._data.get("knowledge_base_documents", [])
                if item["document_id"] != document_id
            ]
            self._write()
            return existing

    def list_platform_files(self) -> list[PlatformFile]:
        self._ensure_key("platform_files", [])
        return self._list("platform_files", PlatformFile)

    def get_platform_file(self, file_id: str) -> PlatformFile | None:
        self._ensure_key("platform_files", [])
        return next(
            (
                PlatformFile(**item)
                for item in self._data["platform_files"]
                if item["id"] == file_id
            ),
            None,
        )

    def create_platform_file(self, payload: PlatformFileCreate) -> PlatformFile:
        with self._lock:
            platform_file = PlatformFile(
                **{
                    **_dump_model(payload),
                    "original_filename": payload.original_filename or payload.filename,
                }
            )
            self._data["platform_files"].append(_dump_model(platform_file))
            self._write()
            return platform_file

    def update_platform_file(self, file_id: str, payload: PlatformFileUpdate) -> PlatformFile:
        with self._lock:
            existing = self.get_platform_file(file_id)
            if existing is None:
                raise KeyError(file_id)
            data = _dump_model(existing)
            updates = payload.model_dump(exclude_unset=True)
            data.update({key: value for key, value in updates.items() if value is not None})
            data["updated_at"] = now_utc()
            platform_file = PlatformFile(**data)
            self._data["platform_files"] = [
                _dump_model(platform_file) if item["id"] == file_id else item
                for item in self._data["platform_files"]
            ]
            self._write()
            return platform_file

    def delete_platform_file(self, file_id: str) -> PlatformFile | None:
        with self._lock:
            existing = self.get_platform_file(file_id)
            if existing is None:
                return None
            self._data["platform_files"] = [
                item for item in self._data["platform_files"] if item["id"] != file_id
            ]
            self._write()
            return existing

    def update_document(self, document: Document) -> Document:
        with self._lock:
            self._data["documents"] = [
                _dump_model(document) if item["id"] == document.id else item
                for item in self._data["documents"]
            ]
            self._write()
            return document

    def list_knowledge_bases(self) -> list[KnowledgeBase]:
        self._ensure_key("knowledge_bases", default_seed_data()["knowledge_bases"])
        return self._list("knowledge_bases", KnowledgeBase)

    def create_knowledge_base(self, payload: KnowledgeBaseCreate) -> KnowledgeBase:
        with self._lock:
            knowledge_base = KnowledgeBase(**_dump_model(payload))
            self._data["knowledge_bases"].append(_dump_model(knowledge_base))
            self._write()
            return knowledge_base

    def update_knowledge_base(
        self, knowledge_base_id: str, payload: KnowledgeBaseUpdate
    ) -> KnowledgeBase:
        with self._lock:
            existing = next(
                (
                    KnowledgeBase(**item)
                    for item in self._data["knowledge_bases"]
                    if item["id"] == knowledge_base_id
                ),
                None,
            )
            if existing is None:
                knowledge_base = KnowledgeBase(id=knowledge_base_id, **_dump_model(payload))
            else:
                knowledge_base = KnowledgeBase(
                    **{
                        **_dump_model(existing),
                        **_dump_model(payload),
                        "id": existing.id,
                        "created_at": existing.created_at,
                        "updated_at": now_utc(),
                    }
                )
            self._data["knowledge_bases"] = [
                _dump_model(knowledge_base) if item["id"] == knowledge_base_id else item
                for item in self._data["knowledge_bases"]
            ]
            if not any(item["id"] == knowledge_base_id for item in self._data["knowledge_bases"]):
                self._data["knowledge_bases"].append(_dump_model(knowledge_base))
            self._write()
            return knowledge_base

    def delete_knowledge_base(self, knowledge_base_id: str) -> KnowledgeBase | None:
        with self._lock:
            existing = next(
                (
                    KnowledgeBase(**item)
                    for item in self._data["knowledge_bases"]
                    if item["id"] == knowledge_base_id
                ),
                None,
            )
            if existing is None:
                return None
            self._data["knowledge_bases"] = [
                item for item in self._data["knowledge_bases"] if item["id"] != knowledge_base_id
            ]
            self._data["knowledge_base_documents"] = [
                item
                for item in self._data["knowledge_base_documents"]
                if item["knowledge_base_id"] != knowledge_base_id
            ]
            for project in self._data["projects"]:
                context = project.get("context") if isinstance(project.get("context"), dict) else {}
                context["knowledge_base_ids"] = [
                    item
                    for item in context.get("knowledge_base_ids", [])
                    if item != knowledge_base_id
                ]
            for agent in self._data["agents"]:
                agent["knowledge_base_ids"] = [
                    item
                    for item in agent.get("knowledge_base_ids", [])
                    if item != knowledge_base_id
                ]
            self._write()
            return existing

    def list_knowledge_base_documents(
        self, knowledge_base_id: str | None = None
    ) -> list[KnowledgeBaseDocument]:
        self._ensure_key("knowledge_base_documents", [])
        items = self._list("knowledge_base_documents", KnowledgeBaseDocument)
        if knowledge_base_id:
            items = [item for item in items if item.knowledge_base_id == knowledge_base_id]
        return sorted(
            items, key=lambda item: (item.knowledge_base_id, -item.priority, item.created_at)
        )

    def add_knowledge_base_document(
        self, knowledge_base_id: str, payload: KnowledgeBaseDocumentCreate
    ) -> KnowledgeBaseDocument:
        with self._lock:
            if not any(base.id == knowledge_base_id for base in self.list_knowledge_bases()):
                raise KeyError(knowledge_base_id)
            if self.get_document(payload.document_id) is None:
                raise KeyError(payload.document_id)
            existing = next(
                (
                    KnowledgeBaseDocument(**item)
                    for item in self._data["knowledge_base_documents"]
                    if item["knowledge_base_id"] == knowledge_base_id
                    and item["document_id"] == payload.document_id
                ),
                None,
            )
            if existing is not None:
                item = KnowledgeBaseDocument(
                    **{
                        **_dump_model(existing),
                        **_dump_model(payload),
                        "id": existing.id,
                        "knowledge_base_id": knowledge_base_id,
                        "document_id": payload.document_id,
                        "created_at": existing.created_at,
                        "updated_at": now_utc(),
                    }
                )
                self._data["knowledge_base_documents"] = [
                    _dump_model(item) if current["id"] == item.id else current
                    for current in self._data["knowledge_base_documents"]
                ]
            else:
                item = KnowledgeBaseDocument(
                    knowledge_base_id=knowledge_base_id, **_dump_model(payload)
                )
                self._data["knowledge_base_documents"].append(_dump_model(item))
            self._write()
            return item

    def update_knowledge_base_document(
        self, item_id: str, payload: KnowledgeBaseDocumentUpdate
    ) -> KnowledgeBaseDocument:
        with self._lock:
            existing = next(
                (
                    KnowledgeBaseDocument(**item)
                    for item in self._data["knowledge_base_documents"]
                    if item["id"] == item_id
                ),
                None,
            )
            if existing is None:
                raise KeyError(item_id)
            item = KnowledgeBaseDocument(
                **{
                    **_dump_model(existing),
                    **_dump_model(payload),
                    "id": existing.id,
                    "knowledge_base_id": existing.knowledge_base_id,
                    "document_id": existing.document_id,
                    "created_at": existing.created_at,
                    "updated_at": now_utc(),
                }
            )
            self._data["knowledge_base_documents"] = [
                _dump_model(item) if current["id"] == item.id else current
                for current in self._data["knowledge_base_documents"]
            ]
            self._write()
            return item

    def remove_knowledge_base_document(
        self, knowledge_base_id: str, document_id: str
    ) -> KnowledgeBaseDocument | None:
        with self._lock:
            existing = next(
                (
                    KnowledgeBaseDocument(**item)
                    for item in self._data["knowledge_base_documents"]
                    if item["knowledge_base_id"] == knowledge_base_id
                    and item["document_id"] == document_id
                ),
                None,
            )
            if existing is None:
                return None
            self._data["knowledge_base_documents"] = [
                item for item in self._data["knowledge_base_documents"] if item["id"] != existing.id
            ]
            self._write()
            return existing

    def list_knowledge_categories(self) -> list[KnowledgeCategory]:
        self._ensure_key("knowledge_categories", default_seed_data()["knowledge_categories"])
        return self._list("knowledge_categories", KnowledgeCategory)

    def create_knowledge_category(self, payload: KnowledgeCategoryCreate) -> KnowledgeCategory:
        with self._lock:
            category = KnowledgeCategory(**_dump_model(payload))
            self._data["knowledge_categories"].append(_dump_model(category))
            self._write()
            return category

    def update_knowledge_category(
        self, category_id: str, payload: KnowledgeCategoryUpdate
    ) -> KnowledgeCategory:
        with self._lock:
            existing = next(
                (
                    KnowledgeCategory(**item)
                    for item in self._data["knowledge_categories"]
                    if item["id"] == category_id
                ),
                None,
            )
            if existing is None:
                category = KnowledgeCategory(id=category_id, **_dump_model(payload))
            else:
                category = KnowledgeCategory(
                    **{
                        **_dump_model(existing),
                        **_dump_model(payload),
                        "id": existing.id,
                        "created_at": existing.created_at,
                        "updated_at": now_utc(),
                    }
                )
            self._data["knowledge_categories"] = [
                _dump_model(category) if item["id"] == category_id else item
                for item in self._data["knowledge_categories"]
            ]
            if not any(item["id"] == category_id for item in self._data["knowledge_categories"]):
                self._data["knowledge_categories"].append(_dump_model(category))
            self._write()
            return category

    def list_chat_sessions(self) -> list[ChatSessionWithMessages]:
        messages = self._list("messages", ChatMessage)
        grouped: dict[str, list[ChatMessage]] = {}
        for message in messages:
            grouped.setdefault(message.session_id, []).append(message)
        sessions = []
        for raw in self._data["chat_sessions"]:
            session = ChatSession(**raw)
            sessions.append(
                ChatSessionWithMessages(
                    **_dump_model(session), messages=grouped.get(session.id, [])
                )
            )
        return sorted(
            sessions,
            key=lambda item: (item.updated_at, item.created_at, item.id),
            reverse=True,
        )

    def list_chat_session_summaries(self) -> list[ChatSessionWithMessages]:
        sessions = [ChatSession(**raw) for raw in self._data["chat_sessions"]]
        summaries = [
            ChatSessionWithMessages(**_dump_model(session), messages=[]) for session in sessions
        ]
        return sorted(
            summaries,
            key=lambda item: (item.updated_at, item.created_at, item.id),
            reverse=True,
        )

    def get_chat_session(self, session_id: str) -> ChatSessionWithMessages | None:
        for session in self.list_chat_sessions():
            if session.id == session_id:
                return session
        return None

    def _resolve_chat_project_and_folder(
        self, project_id: str | None, folder_id: str | None
    ) -> tuple[str, str | None]:
        resolved_project_id = project_id or self._general_project().id
        if not any(project.id == resolved_project_id for project in self.list_projects()):
            resolved_project_id = self._general_project().id
        if not folder_id:
            return resolved_project_id, None
        folder = next(
            (
                item
                for item in self.list_project_folders(resolved_project_id)
                if item.id == folder_id and item.project_id == resolved_project_id
            ),
            None,
        )
        if folder is None:
            raise ValueError("Pasta não encontrada no projeto informado.")
        return resolved_project_id, folder.id

    def create_chat_session(self, payload: ChatSessionCreate) -> ChatSessionWithMessages:
        with self._lock:
            project_id, folder_id = self._resolve_chat_project_and_folder(
                payload.project_id, payload.folder_id
            )
            session = ChatSession(
                **{
                    **_dump_model(payload),
                    "project_id": project_id,
                    "folder_id": folder_id,
                }
            )
            self._data["chat_sessions"].append(_dump_model(session))
            self._write()
            return ChatSessionWithMessages(**_dump_model(session), messages=[])

    def upsert_chat_session(self, session: ChatSession) -> ChatSession:
        with self._lock:
            project_id, folder_id = self._resolve_chat_project_and_folder(
                session.project_id, session.folder_id
            )
            session = session.model_copy(update={"project_id": project_id, "folder_id": folder_id})
            payload = _dump_model(session)
            self._data["chat_sessions"] = [
                payload if item["id"] == session.id else item
                for item in self._data["chat_sessions"]
            ]
            if not any(item["id"] == session.id for item in self._data["chat_sessions"]):
                self._data["chat_sessions"].append(payload)
            self._write()
            return session

    def get_or_create_session(self, payload: ChatStreamRequest) -> ChatSession:
        with self._lock:
            if payload.session_id:
                for item in self._data["chat_sessions"]:
                    if item["id"] == payload.session_id:
                        return ChatSession(**item)
            project_id, folder_id = self._resolve_chat_project_and_folder(
                payload.project_id, payload.folder_id
            )
            explicit_title = (payload.title or "").strip()
            derived_title = (payload.message or "")[:48].strip()
            session_title = explicit_title or derived_title or "Novo chat"
            is_modeling_3d = payload.modeling_3d.enabled
            session = ChatSession(
                title=session_title,
                model_id=payload.model_id,
                agent_id=payload.agent_id,
                project_id=project_id,
                folder_id=folder_id,
                is_modeling_3d=is_modeling_3d,
                modeling_software_preference=payload.modeling_3d.software_override,
                modeling_stage=ChatModelingStage.discovery if is_modeling_3d else None,
            )
            self._data["chat_sessions"].append(_dump_model(session))
            self._write()
            return session

    def move_chat_session(
        self, session_id: str, project_id: str, folder_id: str | None
    ) -> ChatSession:
        with self._lock:
            existing = next(
                (
                    ChatSession(**item)
                    for item in self._data["chat_sessions"]
                    if item["id"] == session_id
                ),
                None,
            )
            if existing is None:
                raise KeyError(session_id)
            resolved_project_id, resolved_folder_id = self._resolve_chat_project_and_folder(
                project_id, folder_id
            )
            moved = existing.model_copy(
                update={
                    "project_id": resolved_project_id,
                    "folder_id": resolved_folder_id,
                    "updated_at": now_utc(),
                }
            )
            self._data["chat_sessions"] = [
                _dump_model(moved) if item["id"] == session_id else item
                for item in self._data["chat_sessions"]
            ]
            self._write()
            return moved

    def add_message(self, message: ChatMessage) -> ChatMessage:
        with self._lock:
            payload = _dump_model(message)
            self._data["messages"] = [
                payload if item["id"] == message.id else item for item in self._data["messages"]
            ]
            if not any(item["id"] == message.id for item in self._data["messages"]):
                self._data["messages"].append(payload)
            for session in self._data["chat_sessions"]:
                if session["id"] == message.session_id:
                    session["updated_at"] = (
                        _dump_model(now_utc()) if False else now_utc().isoformat()
                    )
            self._write()
            return message

    def add_messages(self, messages: list[ChatMessage]) -> tuple[int, int]:
        with self._lock:
            existing_ids = {item["id"] for item in self._data["messages"]}
            imported = 0
            skipped = 0
            for message in messages:
                if message.id in existing_ids:
                    skipped += 1
                    continue
                self._data["messages"].append(_dump_model(message))
                existing_ids.add(message.id)
                imported += 1
            self._write()
            return imported, skipped

    def chat_session_exists(self, session_id: str) -> bool:
        return any(item["id"] == session_id for item in self._data["chat_sessions"])

    def delete_chat_session(self, session_id: str) -> bool:
        with self._lock:
            sessions_before = len(self._data["chat_sessions"])
            self._data["chat_sessions"] = [
                item for item in self._data["chat_sessions"] if item["id"] != session_id
            ]
            if len(self._data["chat_sessions"]) == sessions_before:
                return False
            self._data["messages"] = [
                item for item in self._data["messages"] if item["session_id"] != session_id
            ]
            self._write()
            return True

    def list_modeling_sessions(self) -> list[ModelingSession]:
        self._ensure_key("modeling_sessions", [])
        return sorted(
            self._list("modeling_sessions", ModelingSession),
            key=lambda item: item.updated_at,
            reverse=True,
        )

    def upsert_modeling_session(self, session: ModelingSession) -> ModelingSession:
        with self._lock:
            payload = _dump_model(session)
            self._data["modeling_sessions"] = [
                payload if item["id"] == session.id else item
                for item in self._data["modeling_sessions"]
            ]
            if not any(item["id"] == session.id for item in self._data["modeling_sessions"]):
                self._data["modeling_sessions"].append(payload)
            self._write()
            return session

    def list_modeling_plans(self) -> list[ModelingPlan]:
        self._ensure_key("modeling_plans", [])
        return sorted(
            self._list("modeling_plans", ModelingPlan),
            key=lambda item: item.updated_at,
            reverse=True,
        )

    def get_modeling_plan(self, plan_id: str) -> ModelingPlan | None:
        self._ensure_key("modeling_plans", [])
        return next(
            (
                ModelingPlan(**item)
                for item in self._data["modeling_plans"]
                if item["id"] == plan_id
            ),
            None,
        )

    def get_modeling_plan_by_step(self, step_id: str) -> ModelingPlan | None:
        for plan in self.list_modeling_plans():
            if any(step.id == step_id for step in plan.steps):
                return plan
        return None

    def upsert_modeling_plan(self, plan: ModelingPlan) -> ModelingPlan:
        with self._lock:
            payload = _dump_model(plan)
            self._data["modeling_plans"] = [
                payload if item["id"] == plan.id else item for item in self._data["modeling_plans"]
            ]
            if not any(item["id"] == plan.id for item in self._data["modeling_plans"]):
                self._data["modeling_plans"].append(payload)
            self._write()
            return plan

    def list_modeling_snapshots(
        self,
        *,
        plan_id: str | None = None,
        project_id: str | None = None,
    ) -> list[ModelingSnapshot]:
        self._ensure_key("modeling_snapshots", [])
        snapshots = sorted(
            self._list("modeling_snapshots", ModelingSnapshot),
            key=lambda item: item.created_at,
            reverse=True,
        )
        if plan_id is not None:
            snapshots = [item for item in snapshots if item.plan_id == plan_id]
        if project_id is not None:
            snapshots = [item for item in snapshots if item.project_id == project_id]
        return snapshots

    def upsert_modeling_snapshot(self, snapshot: ModelingSnapshot) -> ModelingSnapshot:
        with self._lock:
            payload = _dump_model(snapshot)
            self._data["modeling_snapshots"] = [
                payload if item["id"] == snapshot.id else item
                for item in self._data["modeling_snapshots"]
            ]
            if not any(item["id"] == snapshot.id for item in self._data["modeling_snapshots"]):
                self._data["modeling_snapshots"].append(payload)
            self._write()
            return snapshot

    def get_modeling_snapshot(self, snapshot_id: str) -> ModelingSnapshot | None:
        self._ensure_key("modeling_snapshots", [])
        return next(
            (
                ModelingSnapshot(**item)
                for item in self._data["modeling_snapshots"]
                if item["id"] == snapshot_id
            ),
            None,
        )

    def list_modeling_tool_calls(
        self,
        *,
        plan_id: str | None = None,
        step_id: str | None = None,
        limit: int = 200,
    ) -> list[ModelingToolCall]:
        self._ensure_key("modeling_tool_calls", [])
        records = sorted(
            self._list("modeling_tool_calls", ModelingToolCall),
            key=lambda item: item.created_at,
            reverse=True,
        )
        if plan_id:
            records = [item for item in records if item.plan_id == plan_id]
        if step_id:
            records = [item for item in records if item.step_id == step_id]
        return records[:limit]

    def add_modeling_tool_call(self, record: ModelingToolCall) -> ModelingToolCall:
        with self._lock:
            self._ensure_key("modeling_tool_calls", [])
            self._data["modeling_tool_calls"].append(_dump_model(record))
            self._write()
            return record

    # ------------------------------------------------------------------
    # Modeling trace events (observabilidade)
    # ------------------------------------------------------------------
    # DevStore carrega o JSON inteiro em memória, então mantemos um ring
    # buffer cap em MODELING_TRACE_DEVSTORE_MAX_EVENTS para não explodir
    # RAM em sessões longas. Eventos mais antigos são descartados.

    def record_trace_events_bulk(self, events: list[ModelingTraceEvent]) -> None:
        if not events:
            return
        with self._lock:
            self._ensure_key("modeling_trace_events", [])
            bucket = self._data["modeling_trace_events"]
            bucket.extend(_dump_model(event) for event in events)
            # Aplica cap do ring buffer (descarta os mais antigos do início).
            overflow = len(bucket) - MODELING_TRACE_DEVSTORE_MAX_EVENTS
            if overflow > 0:
                del bucket[:overflow]
            self._write()

    def list_trace_events(
        self,
        *,
        trace_id: str | None = None,
        plan_id: str | None = None,
        levels: list[ModelingTraceLevel] | None = None,
        sources: list[ModelingTraceSource] | None = None,
        limit: int = 500,
    ) -> list[ModelingTraceEvent]:
        self._ensure_key("modeling_trace_events", [])
        events = self._list("modeling_trace_events", ModelingTraceEvent)
        if trace_id:
            events = [e for e in events if e.trace_id == trace_id]
        if plan_id:
            events = [e for e in events if e.plan_id == plan_id]
        if levels:
            allowed_levels = {level.value for level in levels}
            events = [e for e in events if e.level.value in allowed_levels]
        if sources:
            allowed_sources = {source.value for source in sources}
            events = [e for e in events if e.source.value in allowed_sources]
        # Ordena por (sequence, created_at) ASC, consistente com Postgres.
        events.sort(key=lambda e: (e.sequence, e.created_at))
        return events[:limit]

    def get_max_trace_sequence(self, *, trace_id: str) -> int | None:
        self._ensure_key("modeling_trace_events", [])
        max_sequence: int | None = None
        for item in self._data["modeling_trace_events"]:
            if item.get("trace_id") != trace_id:
                continue
            raw_sequence = item.get("sequence", 0)
            try:
                sequence = int(raw_sequence)
            except (TypeError, ValueError):
                sequence = 0
            max_sequence = sequence if max_sequence is None else max(max_sequence, sequence)
        return max_sequence

    def list_modeling_printability_reports(
        self, *, plan_id: str | None = None, file_id: str | None = None
    ) -> list[ModelingPrintabilityReport]:
        self._ensure_key("modeling_printability_reports", [])
        reports = sorted(
            self._list("modeling_printability_reports", ModelingPrintabilityReport),
            key=lambda item: item.created_at,
            reverse=True,
        )
        if plan_id:
            reports = [item for item in reports if item.plan_id == plan_id]
        if file_id:
            reports = [item for item in reports if item.file_id == file_id]
        return reports

    def add_modeling_printability_report(
        self, report: ModelingPrintabilityReport
    ) -> ModelingPrintabilityReport:
        with self._lock:
            self._ensure_key("modeling_printability_reports", [])
            self._data["modeling_printability_reports"].append(_dump_model(report))
            self._write()
            return report

    def list_modeling_model_versions(
        self, *, project_id: str | None = None
    ) -> list[ModelingModelVersion]:
        self._ensure_key("modeling_model_versions", [])
        versions = sorted(
            self._list("modeling_model_versions", ModelingModelVersion),
            key=lambda item: item.created_at,
            reverse=True,
        )
        if project_id:
            versions = [item for item in versions if item.project_id == project_id]
        return versions

    def add_modeling_model_version(self, version: ModelingModelVersion) -> ModelingModelVersion:
        with self._lock:
            self._ensure_key("modeling_model_versions", [])
            self._data["modeling_model_versions"].append(_dump_model(version))
            self._write()
            return version

    def list_import_jobs(self) -> list[ChatGPTImportJob]:
        self._ensure_key("import_jobs", [])
        return self._list("import_jobs", ChatGPTImportJob)

    def get_import_job(self, job_id: str) -> ChatGPTImportJob | None:
        self._ensure_key("import_jobs", [])
        return next(
            (
                ChatGPTImportJob(**item)
                for item in self._data["import_jobs"]
                if item["id"] == job_id
            ),
            None,
        )

    def upsert_import_job(self, job: ChatGPTImportJob) -> ChatGPTImportJob:
        with self._lock:
            self._ensure_key("import_jobs", [])
            job.updated_at = now_utc()
            payload = _dump_model(job)
            self._data["import_jobs"] = [
                payload if item["id"] == job.id else item for item in self._data["import_jobs"]
            ]
            if not any(item["id"] == job.id for item in self._data["import_jobs"]):
                self._data["import_jobs"].append(payload)
            self._write()
            return job

    def list_audit_events(self) -> list[AuditEvent]:
        return sorted(
            self._list("audit_events", AuditEvent), key=lambda item: item.created_at, reverse=True
        )

    def add_audit_event(self, event: AuditEvent) -> AuditEvent:
        with self._lock:
            self._data["audit_events"].append(_dump_model(event))
            self._write()
            return event

    def get_cost_policy(self) -> CostPolicy:
        return CostPolicy(**self._data["cost_policy"])

    def set_cost_policy(self, policy: CostPolicy) -> CostPolicy:
        with self._lock:
            policy.updated_at = now_utc()
            self._data["cost_policy"] = _dump_model(policy)
            self._write()
            return policy


_dev_store: DevStore | None = None


def get_dev_store() -> DevStore:
    global _dev_store
    if _dev_store is None:
        settings.ensure_local_dirs()
        _dev_store = DevStore(settings.state_dir / "dev-store.json")
    return _dev_store


def get_store() -> DevStore:
    return get_dev_store()
