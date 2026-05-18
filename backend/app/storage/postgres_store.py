from __future__ import annotations

import logging
from datetime import datetime
from time import sleep
from typing import Any, TypeVar

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.core.config import settings
from app.core.contracts import (
    DEFAULT_GENERAL_PROJECT_ID,
    DEFAULT_GENERAL_PROJECT_NAME,
    Agent,
    AgentCreate,
    AgentGraph,
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
    ModelConfig,
    ModelingModelVersion,
    ModelingPlan,
    ModelingPrintabilityReport,
    ModelingSession,
    ModelingSnapshot,
    ModelingToolCall,
    ModelUpsert,
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
    now_utc,
)
from app.storage.dev_store import _dump_model, default_seed_data

T = TypeVar("T")

logger = logging.getLogger(__name__)

_POSTGRES_CONNECT_ATTEMPTS = 8
_POSTGRES_CONNECT_RETRY_DELAY_SECONDS = 1.0
_POSTGRES_RETRYABLE_CONNECT_ERROR_SNIPPETS = (
    "connection refused",
    "connection timed out",
    "could not translate host name",
    "failed to resolve host",
    "name or service not known",
    "temporary failure in name resolution",
    "the database system is starting up",
)


def _is_retryable_connect_error(error: psycopg.OperationalError) -> bool:
    message = str(error).lower()
    return any(snippet in message for snippet in _POSTGRES_RETRYABLE_CONNECT_ERROR_SNIPPETS)


class PostgresStore:
    """Postgres-backed store for the local-first MVP.

    The first implementation keeps typed payloads in JSONB with stable primary keys. This gives
    us durable Postgres persistence now while leaving room to normalize hot paths later.
    """

    def __init__(self, database_url: str = settings.database_url) -> None:
        self.database_url = database_url
        self.init_schema()
        self.seed_if_empty()
        self.migrate_projects_and_folders()
        self.reconcile_chatgpt_session_timestamps()

    def _connect(self) -> psycopg.Connection:
        for attempt in range(1, _POSTGRES_CONNECT_ATTEMPTS + 1):
            try:
                return psycopg.connect(self.database_url, row_factory=dict_row)
            except psycopg.OperationalError as error:
                if attempt == _POSTGRES_CONNECT_ATTEMPTS or not _is_retryable_connect_error(error):
                    raise
                logger.warning(
                    "Postgres connection attempt %s/%s failed: %s",
                    attempt,
                    _POSTGRES_CONNECT_ATTEMPTS,
                    error,
                )
                sleep(_POSTGRES_CONNECT_RETRY_DELAY_SECONDS)

        raise RuntimeError("Postgres connection retry loop exited unexpectedly")

    def init_schema(self) -> None:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS model_configs (
              id TEXT PRIMARY KEY,
              payload JSONB NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS agents (
              id TEXT PRIMARY KEY,
              payload JSONB NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS prompts (
              id TEXT PRIMARY KEY,
              payload JSONB NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS projects (
              id TEXT PRIMARY KEY,
              payload JSONB NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS project_folders (
              id TEXT PRIMARY KEY,
              payload JSONB NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS chat_sessions (
              id TEXT PRIMARY KEY,
              payload JSONB NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
              id TEXT PRIMARY KEY,
              session_id TEXT NOT NULL,
              payload JSONB NOT NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id)",
            """
            CREATE TABLE IF NOT EXISTS documents (
              id TEXT PRIMARY KEY,
              payload JSONB NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS platform_files (
              id TEXT PRIMARY KEY,
              payload JSONB NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS knowledge_categories (
              id TEXT PRIMARY KEY,
              payload JSONB NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS knowledge_bases (
              id TEXT PRIMARY KEY,
              payload JSONB NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS knowledge_base_documents (
              id TEXT PRIMARY KEY,
              payload JSONB NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_kb_documents_payload_base
            ON knowledge_base_documents ((payload->>'knowledge_base_id'))
            """,
            """
            DO $$
            BEGIN
              IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'knowledge_base_documents'
                  AND column_name = 'knowledge_base_id'
                  AND is_nullable = 'NO'
              ) THEN
                ALTER TABLE knowledge_base_documents
                ALTER COLUMN knowledge_base_id DROP NOT NULL;
              END IF;

              IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'knowledge_base_documents'
                  AND column_name = 'document_id'
                  AND is_nullable = 'NO'
              ) THEN
                ALTER TABLE knowledge_base_documents
                ALTER COLUMN document_id DROP NOT NULL;
              END IF;
            END $$;
            """,
            """
            CREATE TABLE IF NOT EXISTS audit_events (
              id TEXT PRIMARY KEY,
              payload JSONB NOT NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS import_jobs (
              id TEXT PRIMARY KEY,
              payload JSONB NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS modeling_sessions (
              id TEXT PRIMARY KEY,
              payload JSONB NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS modeling_plans (
              id TEXT PRIMARY KEY,
              payload JSONB NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS modeling_snapshots (
              id TEXT PRIMARY KEY,
              payload JSONB NOT NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS modeling_tool_calls (
              id TEXT PRIMARY KEY,
              payload JSONB NOT NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_modeling_tool_calls_plan
            ON modeling_tool_calls ((payload->>'plan_id'))
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_modeling_tool_calls_step
            ON modeling_tool_calls ((payload->>'step_id'))
            """,
            """
            CREATE TABLE IF NOT EXISTS modeling_printability_reports (
              id TEXT PRIMARY KEY,
              payload JSONB NOT NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_modeling_print_reports_plan
            ON modeling_printability_reports ((payload->>'plan_id'))
            """,
            """
            CREATE TABLE IF NOT EXISTS modeling_model_versions (
              id TEXT PRIMARY KEY,
              payload JSONB NOT NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_modeling_versions_project
            ON modeling_model_versions ((payload->>'project_id'))
            """,
            """
            CREATE TABLE IF NOT EXISTS cost_policy (
              id TEXT PRIMARY KEY,
              payload JSONB NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """,
        ]
        with self._connect() as conn:
            with conn.cursor() as cur:
                for statement in statements:
                    cur.execute(statement)

    def seed_if_empty(self) -> None:
        seed = default_seed_data()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS count FROM model_configs")
                if not cur.fetchone()["count"]:
                    self._bulk_insert(cur, "model_configs", seed["models"])
                    self._bulk_insert(cur, "agents", seed["agents"])
                    self._bulk_insert(cur, "prompts", seed["prompts"])
                    self._bulk_insert(cur, "projects", seed["projects"])
                    cur.execute(
                        """
                        INSERT INTO cost_policy (id, payload)
                        VALUES ('default', %s)
                        ON CONFLICT (id) DO UPDATE
                        SET payload = EXCLUDED.payload, updated_at = now()
                        """,
                        (Jsonb(seed["cost_policy"]),),
                    )
                else:
                    self._bulk_insert(cur, "model_configs", seed["models"])
                    self._bulk_insert(cur, "projects", seed["projects"])

                cur.execute("SELECT COUNT(*) AS count FROM knowledge_categories")
                if not cur.fetchone()["count"]:
                    self._bulk_insert(cur, "knowledge_categories", seed["knowledge_categories"])
                cur.execute("SELECT COUNT(*) AS count FROM knowledge_bases")
                if not cur.fetchone()["count"]:
                    self._bulk_insert(cur, "knowledge_bases", seed["knowledge_bases"])
                cur.execute("SELECT COUNT(*) AS count FROM project_folders")
                if not cur.fetchone()["count"] and seed.get("project_folders"):
                    self._bulk_insert(cur, "project_folders", seed["project_folders"])

    def _general_project(self) -> Project:
        projects = self.list_projects()
        existing = next((project for project in projects if project.is_general), None)
        if existing is not None:
            return existing
        fallback = next(
            (project for project in projects if project.id == DEFAULT_GENERAL_PROJECT_ID), None
        )
        if fallback is not None:
            return fallback
        project = Project(
            id=DEFAULT_GENERAL_PROJECT_ID,
            name=DEFAULT_GENERAL_PROJECT_NAME,
            description="Projeto global para conteúdos não vinculados a um projeto específico.",
            color="#f0b84d",
            is_general=True,
        )
        self._upsert_payload("projects", _dump_model(project))
        return project

    def migrate_projects_and_folders(self) -> None:
        general_project = self._general_project()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE projects
                    SET payload = jsonb_set(
                        CASE
                            WHEN jsonb_typeof(payload->'context') = 'object'
                                THEN payload
                            ELSE jsonb_set(payload, '{context}', '{}'::jsonb, true)
                        END,
                        '{context,max_documents}',
                        '20'::jsonb,
                        true
                    ),
                    updated_at = now()
                    """
                )
                cur.execute(
                    """
                    UPDATE projects
                    SET payload = jsonb_set(
                            payload,
                            '{context,knowledge_base_ids}',
                            '[]'::jsonb,
                            true
                        ),
                        updated_at = now()
                    WHERE jsonb_typeof(payload #> '{context,knowledge_base_ids}') != 'array'
                        OR payload #> '{context,knowledge_base_ids}' IS NULL
                    """
                )
                cur.execute(
                    """
                    UPDATE projects
                    SET payload = jsonb_set(
                        payload,
                        '{context,scope_mode}',
                        '"project_only"'::jsonb,
                        true
                    ),
                        updated_at = now()
                    WHERE payload #>> '{context,scope_mode}' NOT IN
                        ('project_only', 'project_plus_global', 'global_only')
                        OR payload #>> '{context,scope_mode}' IS NULL
                    """
                )
        categories = self.list_knowledge_categories()
        folders = self.list_project_folders(general_project.id)
        by_legacy_category_id = {
            folder.path.removeprefix("legacy:")
            for folder in folders
            if folder.path.startswith("legacy:")
        }
        for category in categories:
            if category.id in by_legacy_category_id:
                continue
            folder = ProjectFolder(
                project_id=general_project.id,
                name=category.name.strip() or "Categoria",
                depth=0,
                path=f"legacy:{category.id}",
            )
            self._upsert_payload("project_folders", _dump_model(folder))
            by_legacy_category_id.add(category.id)

        folders = self.list_project_folders(general_project.id)
        folder_for_category = {
            folder.path.removeprefix("legacy:"): folder.id
            for folder in folders
            if folder.path.startswith("legacy:")
        }

        documents = self.list_documents()
        for document in documents:
            updates: dict[str, Any] = {}
            if not document.project_id:
                updates["project_id"] = general_project.id
            if not getattr(document, "folder_id", None) and document.category_id:
                mapped = folder_for_category.get(document.category_id)
                if mapped:
                    updates["folder_id"] = mapped
            if not updates:
                continue
            document = document.model_copy(update=updates)
            self._upsert_payload("documents", _dump_model(document))

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload FROM chat_sessions")
                raw_sessions = [dict(row["payload"] or {}) for row in cur.fetchall()]
        for session_payload in raw_sessions:
            if not session_payload.get("id"):
                continue
            updates: dict[str, Any] = {}
            if not session_payload.get("project_id"):
                updates["project_id"] = general_project.id
            if "folder_id" not in session_payload:
                updates["folder_id"] = None
            if not isinstance(session_payload.get("context_project_ids"), list):
                updates["context_project_ids"] = []
            if not isinstance(session_payload.get("context_document_ids"), list):
                updates["context_document_ids"] = []
            if not isinstance(session_payload.get("context_knowledge_base_ids"), list):
                updates["context_knowledge_base_ids"] = []
            if not updates:
                continue
            self._upsert_payload(
                "chat_sessions",
                {
                    **session_payload,
                    **updates,
                },
            )

        files = self.list_platform_files()
        for platform_file in files:
            metadata = (
                dict(platform_file.metadata) if isinstance(platform_file.metadata, dict) else {}
            )
            if "project_id" in metadata:
                continue
            metadata["project_id"] = general_project.id
            self._upsert_payload(
                "platform_files",
                _dump_model(
                    platform_file.model_copy(update={"metadata": metadata, "updated_at": now_utc()})
                ),
            )

        agents = self.list_agents()
        known_project_ids = {project.id for project in self.list_projects()}
        for agent in agents:
            allowed_project_ids = [
                project_id
                for project_id in (agent.allowed_project_ids or [])
                if project_id in known_project_ids
            ]
            if not allowed_project_ids:
                allowed_project_ids = [general_project.id]
            if allowed_project_ids == agent.allowed_project_ids:
                if isinstance(getattr(agent, "knowledge_base_ids", None), list):
                    continue
            knowledge_base_ids = self._normalize_knowledge_base_ids(
                list(getattr(agent, "knowledge_base_ids", []) or [])
            )
            self._upsert_payload(
                "agents",
                _dump_model(
                    agent.model_copy(
                        update={
                            "allowed_project_ids": allowed_project_ids,
                            "knowledge_base_ids": knowledge_base_ids,
                            "updated_at": now_utc(),
                        }
                    )
                ),
            )

        self._migrate_default_knowledge_base_links()

    def reconcile_chatgpt_session_timestamps(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH latest AS (
                        SELECT
                            s.id,
                            COALESCE(MAX(m.created_at), s.updated_at) AS last_message_at
                        FROM chat_sessions s
                        LEFT JOIN chat_messages m ON m.session_id = s.id
                        GROUP BY s.id, s.updated_at
                    )
                    UPDATE chat_sessions s
                    SET
                        payload = jsonb_set(
                            s.payload,
                            '{updated_at}',
                            to_jsonb(
                                to_char(
                                    latest.last_message_at AT TIME ZONE 'UTC',
                                    'YYYY-MM-DD"T"HH24:MI:SS"Z"'
                                )
                            ),
                            true
                        ),
                        updated_at = latest.last_message_at
                    FROM latest
                    WHERE s.id = latest.id
                    """
                )

    def _bulk_insert(self, cur: psycopg.Cursor, table: str, payloads: list[dict[str, Any]]) -> None:
        for payload in payloads:
            cur.execute(
                f"""
                INSERT INTO {table} (id, payload)
                VALUES (%s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (payload["id"], Jsonb(payload)),
            )

    def _list(self, table: str, model_type: type[T], order_by: str = "updated_at DESC") -> list[T]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT payload FROM {table} ORDER BY {order_by}")
                return [model_type(**row["payload"]) for row in cur.fetchall()]

    def _upsert_payload(
        self, table: str, payload: dict[str, Any], timestamp_column: str = "updated_at"
    ) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {table} (id, payload)
                    VALUES (%s, %s)
                    ON CONFLICT (id)
                    DO UPDATE SET payload = EXCLUDED.payload, {timestamp_column} = now()
                    """,
                    (payload["id"], Jsonb(payload)),
                )

    def list_models(self) -> list[ModelConfig]:
        return self._list("model_configs", ModelConfig)

    def upsert_model(self, payload: ModelUpsert) -> ModelConfig:
        model = ModelConfig(**_dump_model(payload))
        with self._connect() as conn:
            with conn.cursor() as cur:
                if model.default:
                    cur.execute(
                        """
                        UPDATE model_configs
                        SET payload = jsonb_set(payload, '{default}', 'false'::jsonb),
                            updated_at = now()
                        """
                    )
                cur.execute(
                    """
                    INSERT INTO model_configs (id, payload)
                    VALUES (%s, %s)
                    ON CONFLICT (id) DO UPDATE SET payload = EXCLUDED.payload, updated_at = now()
                    """,
                    (model.id, Jsonb(_dump_model(model))),
                )
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

    def _migrate_default_knowledge_base_links(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS count FROM knowledge_base_documents")
                if cur.fetchone()["count"]:
                    return
        documents = [
            document
            for document in self.list_documents()
            if document.index_status in {JobStatus.completed, "completed"}
        ]
        if not documents:
            return
        bases = self.list_knowledge_bases()
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
            self._upsert_payload("knowledge_bases", _dump_model(default_base))
        for document in documents:
            item = KnowledgeBaseDocument(
                knowledge_base_id=default_base.id,
                document_id=document.id,
                note="Migrado automaticamente dos documentos existentes.",
                tags=document.tags,
            )
            self._upsert_payload("knowledge_base_documents", _dump_model(item))

    def create_agent(self, payload: AgentCreate) -> Agent:
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
        self._upsert_payload("agents", _dump_model(agent))
        return agent

    def update_agent(self, agent_id: str, payload: AgentUpdate) -> Agent:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload FROM agents WHERE id = %s", (agent_id,))
                row = cur.fetchone()
        if row:
            existing = Agent(**row["payload"])
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
        else:
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
        self._upsert_payload("agents", _dump_model(agent))
        return agent

    def list_prompts(self) -> list[Prompt]:
        return self._list("prompts", Prompt)

    def create_prompt(self, payload: PromptCreate) -> Prompt:
        prompt = Prompt(**_dump_model(payload))
        self._upsert_payload("prompts", _dump_model(prompt))
        return prompt

    def list_projects(self) -> list[Project]:
        projects = self._list("projects", Project)
        return sorted(
            projects, key=lambda item: (not item.is_general, item.updated_at), reverse=True
        )

    def create_project(self, payload: ProjectCreate) -> Project:
        raw = _dump_model(payload)
        raw["context"] = self._normalize_project_context(raw.get("context") or {})
        project = Project(**raw)
        self._upsert_payload("projects", _dump_model(project))
        return project

    def update_project(self, project_id: str, payload: ProjectUpdate) -> Project:
        raw = _dump_model(payload)
        raw["context"] = self._normalize_project_context(raw.get("context") or {})
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload FROM projects WHERE id = %s", (project_id,))
                row = cur.fetchone()
        if row:
            existing = Project(**row["payload"])
            project = Project(
                **{
                    **_dump_model(existing),
                    **raw,
                    "id": existing.id,
                    "created_at": existing.created_at,
                    "updated_at": now_utc(),
                }
            )
        else:
            project = Project(id=project_id, **raw)
        self._upsert_payload("projects", _dump_model(project))
        return project

    def _build_folder_path(
        self, project_id: str, parent_id: str | None, name: str
    ) -> tuple[int, str]:
        normalized_name = name.strip()
        if not parent_id:
            return 0, normalized_name
        parent = next(
            (
                folder
                for folder in self.list_project_folders(project_id)
                if folder.id == parent_id and folder.project_id == project_id
            ),
            None,
        )
        if parent is None:
            raise ValueError("Pasta pai não encontrada no projeto.")
        depth = parent.depth + 1
        if depth > 5:
            raise ValueError("Apenas 5 subníveis de pasta são permitidos.")
        return depth, f"{parent.path}/{normalized_name}".strip("/")

    def list_project_folders(self, project_id: str | None = None) -> list[ProjectFolder]:
        folders = self._list("project_folders", ProjectFolder)
        if project_id:
            folders = [folder for folder in folders if folder.project_id == project_id]
        return sorted(folders, key=lambda item: (item.depth, item.path, item.name))

    def create_project_folder(self, payload: ProjectFolderCreate) -> ProjectFolder:
        depth, path = self._build_folder_path(payload.project_id, payload.parent_id, payload.name)
        folder = ProjectFolder(
            project_id=payload.project_id,
            parent_id=payload.parent_id,
            name=payload.name.strip(),
            depth=depth,
            path=path,
        )
        self._upsert_payload("project_folders", _dump_model(folder))
        return folder

    def update_project_folder(self, folder_id: str, payload: ProjectFolderUpdate) -> ProjectFolder:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload FROM project_folders WHERE id = %s", (folder_id,))
                row = cur.fetchone()
        if not row:
            raise KeyError(folder_id)
        existing = ProjectFolder(**row["payload"])
        depth, path = self._build_folder_path(existing.project_id, existing.parent_id, payload.name)
        folder = ProjectFolder(
            **{
                **_dump_model(existing),
                "name": payload.name.strip(),
                "depth": depth,
                "path": path,
                "updated_at": now_utc(),
            }
        )
        self._upsert_payload("project_folders", _dump_model(folder))
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
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload FROM project_folders WHERE id = %s", (folder_id,))
                row = cur.fetchone()
        if not row:
            raise KeyError(folder_id)
        existing = ProjectFolder(**row["payload"])
        deleted_folder_ids, _ = self._folder_descendants(existing.project_id, folder_id)

        sessions = self.list_chat_sessions()
        deleted_chat_session_ids = [
            session.id
            for session in sessions
            if session.project_id == existing.project_id and session.folder_id in deleted_folder_ids
        ]

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM project_folders WHERE id = ANY(%s)",
                    (list(deleted_folder_ids),),
                )
                if deleted_chat_session_ids:
                    cur.execute(
                        "DELETE FROM chat_messages WHERE session_id = ANY(%s)",
                        (deleted_chat_session_ids,),
                    )
                    cur.execute(
                        "DELETE FROM chat_sessions WHERE id = ANY(%s)",
                        (deleted_chat_session_ids,),
                    )
        return sorted(deleted_folder_ids), deleted_chat_session_ids

    def list_documents(self) -> list[Document]:
        return self._list("documents", Document)

    def get_document(self, document_id: str) -> Document | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload FROM documents WHERE id = %s", (document_id,))
                row = cur.fetchone()
        return Document(**row["payload"]) if row else None

    def create_document(self, payload: DocumentCreate) -> Document:
        document = Document(**_dump_model(payload))
        self._upsert_payload("documents", _dump_model(document))
        return document

    def update_document(self, document: Document) -> Document:
        self._upsert_payload("documents", _dump_model(document))
        return document

    def delete_document(self, document_id: str) -> Document | None:
        existing = self.get_document(document_id)
        if existing is None:
            return None
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM documents WHERE id = %s", (document_id,))
                cur.execute(
                    "DELETE FROM knowledge_base_documents WHERE document_id = %s", (document_id,)
                )
        return existing

    def list_platform_files(self) -> list[PlatformFile]:
        return self._list("platform_files", PlatformFile)

    def get_platform_file(self, file_id: str) -> PlatformFile | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload FROM platform_files WHERE id = %s", (file_id,))
                row = cur.fetchone()
        return PlatformFile(**row["payload"]) if row else None

    def create_platform_file(self, payload: PlatformFileCreate) -> PlatformFile:
        platform_file = PlatformFile(
            **{
                **_dump_model(payload),
                "original_filename": payload.original_filename or payload.filename,
            }
        )
        self._upsert_payload("platform_files", _dump_model(platform_file))
        return platform_file

    def update_platform_file(self, file_id: str, payload: PlatformFileUpdate) -> PlatformFile:
        existing = self.get_platform_file(file_id)
        if existing is None:
            raise KeyError(file_id)
        data = _dump_model(existing)
        updates = payload.model_dump(exclude_unset=True)
        data.update({key: value for key, value in updates.items() if value is not None})
        data["updated_at"] = now_utc()
        platform_file = PlatformFile(**data)
        self._upsert_payload("platform_files", _dump_model(platform_file))
        return platform_file

    def delete_platform_file(self, file_id: str) -> PlatformFile | None:
        existing = self.get_platform_file(file_id)
        if existing is None:
            return None
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM platform_files WHERE id = %s", (file_id,))
        return existing

    def list_knowledge_categories(self) -> list[KnowledgeCategory]:
        return self._list("knowledge_categories", KnowledgeCategory)

    def create_knowledge_category(self, payload: KnowledgeCategoryCreate) -> KnowledgeCategory:
        category = KnowledgeCategory(**_dump_model(payload))
        self._upsert_payload("knowledge_categories", _dump_model(category))
        return category

    def update_knowledge_category(
        self, category_id: str, payload: KnowledgeCategoryUpdate
    ) -> KnowledgeCategory:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT payload FROM knowledge_categories WHERE id = %s", (category_id,)
                )
                row = cur.fetchone()
        if row:
            existing = KnowledgeCategory(**row["payload"])
            category = KnowledgeCategory(
                **{
                    **_dump_model(existing),
                    **_dump_model(payload),
                    "id": existing.id,
                    "created_at": existing.created_at,
                    "updated_at": now_utc(),
                }
            )
        else:
            category = KnowledgeCategory(id=category_id, **_dump_model(payload))
        self._upsert_payload("knowledge_categories", _dump_model(category))
        return category

    def list_knowledge_bases(self) -> list[KnowledgeBase]:
        return self._list("knowledge_bases", KnowledgeBase)

    def create_knowledge_base(self, payload: KnowledgeBaseCreate) -> KnowledgeBase:
        knowledge_base = KnowledgeBase(**_dump_model(payload))
        self._upsert_payload("knowledge_bases", _dump_model(knowledge_base))
        return knowledge_base

    def update_knowledge_base(
        self, knowledge_base_id: str, payload: KnowledgeBaseUpdate
    ) -> KnowledgeBase:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT payload FROM knowledge_bases WHERE id = %s", (knowledge_base_id,)
                )
                row = cur.fetchone()
        if row:
            existing = KnowledgeBase(**row["payload"])
            knowledge_base = KnowledgeBase(
                **{
                    **_dump_model(existing),
                    **_dump_model(payload),
                    "id": existing.id,
                    "created_at": existing.created_at,
                    "updated_at": now_utc(),
                }
            )
        else:
            knowledge_base = KnowledgeBase(id=knowledge_base_id, **_dump_model(payload))
        self._upsert_payload("knowledge_bases", _dump_model(knowledge_base))
        return knowledge_base

    def delete_knowledge_base(self, knowledge_base_id: str) -> KnowledgeBase | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT payload FROM knowledge_bases WHERE id = %s", (knowledge_base_id,)
                )
                row = cur.fetchone()
                if not row:
                    return None
                existing = KnowledgeBase(**row["payload"])
                cur.execute(
                    "DELETE FROM knowledge_base_documents WHERE knowledge_base_id = %s",
                    (knowledge_base_id,),
                )
                cur.execute("DELETE FROM knowledge_bases WHERE id = %s", (knowledge_base_id,))
        projects = self.list_projects()
        for project in projects:
            context = dict(project.context.model_dump())
            next_ids = [
                item for item in context.get("knowledge_base_ids", []) if item != knowledge_base_id
            ]
            if next_ids == context.get("knowledge_base_ids", []):
                continue
            context["knowledge_base_ids"] = next_ids
            self._upsert_payload(
                "projects",
                _dump_model(
                    project.model_copy(update={"context": context, "updated_at": now_utc()})
                ),
            )
        agents = self.list_agents()
        for agent in agents:
            next_ids = [item for item in agent.knowledge_base_ids if item != knowledge_base_id]
            if next_ids == agent.knowledge_base_ids:
                continue
            self._upsert_payload(
                "agents",
                _dump_model(
                    agent.model_copy(
                        update={"knowledge_base_ids": next_ids, "updated_at": now_utc()}
                    )
                ),
            )
        return existing

    def list_knowledge_base_documents(
        self, knowledge_base_id: str | None = None
    ) -> list[KnowledgeBaseDocument]:
        items = self._list("knowledge_base_documents", KnowledgeBaseDocument)
        if knowledge_base_id:
            items = [item for item in items if item.knowledge_base_id == knowledge_base_id]
        return sorted(
            items, key=lambda item: (item.knowledge_base_id, -item.priority, item.created_at)
        )

    def add_knowledge_base_document(
        self, knowledge_base_id: str, payload: KnowledgeBaseDocumentCreate
    ) -> KnowledgeBaseDocument:
        if not any(base.id == knowledge_base_id for base in self.list_knowledge_bases()):
            raise KeyError(knowledge_base_id)
        if self.get_document(payload.document_id) is None:
            raise KeyError(payload.document_id)
        existing = next(
            (
                item
                for item in self.list_knowledge_base_documents(knowledge_base_id)
                if item.document_id == payload.document_id
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
        else:
            item = KnowledgeBaseDocument(
                knowledge_base_id=knowledge_base_id, **_dump_model(payload)
            )
        self._upsert_payload("knowledge_base_documents", _dump_model(item))
        return item

    def update_knowledge_base_document(
        self, item_id: str, payload: KnowledgeBaseDocumentUpdate
    ) -> KnowledgeBaseDocument:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT payload FROM knowledge_base_documents WHERE id = %s", (item_id,)
                )
                row = cur.fetchone()
        if not row:
            raise KeyError(item_id)
        existing = KnowledgeBaseDocument(**row["payload"])
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
        self._upsert_payload("knowledge_base_documents", _dump_model(item))
        return item

    def remove_knowledge_base_document(
        self, knowledge_base_id: str, document_id: str
    ) -> KnowledgeBaseDocument | None:
        existing = next(
            (
                item
                for item in self.list_knowledge_base_documents(knowledge_base_id)
                if item.document_id == document_id
            ),
            None,
        )
        if existing is None:
            return None
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM knowledge_base_documents WHERE id = %s", (existing.id,))
        return existing

    def list_chat_sessions(self) -> list[ChatSessionWithMessages]:
        sessions = self._list("chat_sessions", ChatSession)
        messages = self._list("chat_messages", ChatMessage, order_by="created_at ASC")
        grouped: dict[str, list[ChatMessage]] = {}
        for message in messages:
            grouped.setdefault(message.session_id, []).append(message)
        hydrated = [
            ChatSessionWithMessages(**_dump_model(session), messages=grouped.get(session.id, []))
            for session in sessions
        ]
        return sorted(
            hydrated,
            key=lambda item: (item.updated_at, item.created_at, item.id),
            reverse=True,
        )

    def list_chat_session_summaries(self) -> list[ChatSessionWithMessages]:
        sessions = self._list("chat_sessions", ChatSession)
        summaries = [
            ChatSessionWithMessages(**_dump_model(session), messages=[]) for session in sessions
        ]
        return sorted(
            summaries,
            key=lambda item: (item.updated_at, item.created_at, item.id),
            reverse=True,
        )

    def get_chat_session(self, session_id: str) -> ChatSessionWithMessages | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload FROM chat_sessions WHERE id = %s", (session_id,))
                session_row = cur.fetchone()
                if not session_row:
                    return None
                cur.execute(
                    """
                    SELECT payload FROM chat_messages
                    WHERE session_id = %s
                    ORDER BY created_at ASC
                    """,
                    (session_id,),
                )
                messages = [ChatMessage(**row["payload"]) for row in cur.fetchall()]
        session = ChatSession(**session_row["payload"])
        return ChatSessionWithMessages(**_dump_model(session), messages=messages)

    def _resolve_chat_project_and_folder(
        self, project_id: str | None, folder_id: str | None
    ) -> tuple[str, str | None]:
        resolved_project_id = project_id or self._general_project().id
        known_projects = {project.id for project in self.list_projects()}
        if resolved_project_id not in known_projects:
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
        self._upsert_payload("chat_sessions", _dump_model(session))
        return ChatSessionWithMessages(**_dump_model(session), messages=[])

    def upsert_chat_session(self, session: ChatSession) -> ChatSession:
        project_id, folder_id = self._resolve_chat_project_and_folder(
            session.project_id, session.folder_id
        )
        session = session.model_copy(update={"project_id": project_id, "folder_id": folder_id})
        self._upsert_payload("chat_sessions", _dump_model(session))
        return session

    def get_or_create_session(self, payload: ChatStreamRequest) -> ChatSession:
        if payload.session_id:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT payload FROM chat_sessions WHERE id = %s", (payload.session_id,)
                    )
                    row = cur.fetchone()
                    if row:
                        return ChatSession(**row["payload"])
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
        self._upsert_payload("chat_sessions", _dump_model(session))
        return session

    def move_chat_session(
        self, session_id: str, project_id: str, folder_id: str | None
    ) -> ChatSession:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload FROM chat_sessions WHERE id = %s", (session_id,))
                row = cur.fetchone()
        if not row:
            raise KeyError(session_id)
        existing = ChatSession(**row["payload"])
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
        self._upsert_payload("chat_sessions", _dump_model(moved))
        return moved

    def add_message(self, message: ChatMessage) -> ChatMessage:
        message_payload = _dump_model(message)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO chat_messages (id, session_id, payload, created_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE
                    SET session_id = EXCLUDED.session_id, payload = EXCLUDED.payload
                    """,
                    (message.id, message.session_id, Jsonb(message_payload), message.created_at),
                )
                cur.execute(
                    """
                    UPDATE chat_sessions
                    SET payload = jsonb_set(payload, '{updated_at}', %s::jsonb), updated_at = now()
                    WHERE id = %s
                    """,
                    (Jsonb(now_utc().isoformat()), message.session_id),
                )
        return message

    def add_messages(self, messages: list[ChatMessage]) -> tuple[int, int]:
        if not messages:
            return 0, 0
        imported = 0
        with self._connect() as conn:
            with conn.cursor() as cur:
                for message in messages:
                    message_payload = _dump_model(message)
                    cur.execute(
                        """
                        INSERT INTO chat_messages (id, session_id, payload, created_at)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (id) DO NOTHING
                        RETURNING id
                        """,
                        (
                            message.id,
                            message.session_id,
                            Jsonb(message_payload),
                            message.created_at,
                        ),
                    )
                    if cur.fetchone():
                        imported += 1
        return imported, len(messages) - imported

    def chat_session_exists(self, session_id: str) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM chat_sessions WHERE id = %s", (session_id,))
                return cur.fetchone() is not None

    def delete_chat_session(self, session_id: str) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM chat_messages WHERE session_id = %s", (session_id,))
                cur.execute("DELETE FROM chat_sessions WHERE id = %s RETURNING id", (session_id,))
                return cur.fetchone() is not None

    def list_modeling_sessions(self) -> list[ModelingSession]:
        return self._list("modeling_sessions", ModelingSession)

    def upsert_modeling_session(self, session: ModelingSession) -> ModelingSession:
        self._upsert_payload("modeling_sessions", _dump_model(session))
        return session

    def list_modeling_plans(self) -> list[ModelingPlan]:
        return self._list("modeling_plans", ModelingPlan)

    def get_modeling_plan(self, plan_id: str) -> ModelingPlan | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload FROM modeling_plans WHERE id = %s", (plan_id,))
                row = cur.fetchone()
        return ModelingPlan(**row["payload"]) if row else None

    def get_modeling_plan_by_step(self, step_id: str) -> ModelingPlan | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT payload FROM modeling_plans
                    WHERE payload->'steps' @> %s::jsonb
                    LIMIT 1
                    """,
                    (Jsonb([{"id": step_id}]),),
                )
                row = cur.fetchone()
        return ModelingPlan(**row["payload"]) if row else None

    def upsert_modeling_plan(self, plan: ModelingPlan) -> ModelingPlan:
        self._upsert_payload("modeling_plans", _dump_model(plan))
        return plan

    def list_modeling_snapshots(
        self,
        *,
        plan_id: str | None = None,
        project_id: str | None = None,
    ) -> list[ModelingSnapshot]:
        clauses: list[str] = []
        params: list[Any] = []
        if plan_id is not None:
            clauses.append("payload->>'plan_id' = %s")
            params.append(plan_id)
        if project_id is not None:
            clauses.append("payload->>'project_id' = %s")
            params.append(project_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT payload FROM modeling_snapshots
                    {where}
                    ORDER BY created_at DESC
                    """,
                    tuple(params),
                )
                return [ModelingSnapshot(**row["payload"]) for row in cur.fetchall()]

    def upsert_modeling_snapshot(self, snapshot: ModelingSnapshot) -> ModelingSnapshot:
        self._upsert_payload(
            "modeling_snapshots", _dump_model(snapshot), timestamp_column="created_at"
        )
        return snapshot

    def get_modeling_snapshot(self, snapshot_id: str) -> ModelingSnapshot | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload FROM modeling_snapshots WHERE id = %s", (snapshot_id,))
                row = cur.fetchone()
        return ModelingSnapshot(**row["payload"]) if row else None

    def list_modeling_tool_calls(
        self,
        *,
        plan_id: str | None = None,
        step_id: str | None = None,
        limit: int = 200,
    ) -> list[ModelingToolCall]:
        clauses: list[str] = []
        params: list[Any] = []
        if plan_id:
            clauses.append("payload->>'plan_id' = %s")
            params.append(plan_id)
        if step_id:
            clauses.append("payload->>'step_id' = %s")
            params.append(step_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT payload FROM modeling_tool_calls
                    {where}
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [ModelingToolCall(**row["payload"]) for row in cur.fetchall()]

    def add_modeling_tool_call(self, record: ModelingToolCall) -> ModelingToolCall:
        self._upsert_payload(
            "modeling_tool_calls", _dump_model(record), timestamp_column="created_at"
        )
        return record

    def list_modeling_printability_reports(
        self, *, plan_id: str | None = None, file_id: str | None = None
    ) -> list[ModelingPrintabilityReport]:
        clauses: list[str] = []
        params: list[Any] = []
        if plan_id:
            clauses.append("payload->>'plan_id' = %s")
            params.append(plan_id)
        if file_id:
            clauses.append("payload->>'file_id' = %s")
            params.append(file_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT payload FROM modeling_printability_reports
                    {where}
                    ORDER BY created_at DESC
                    """,
                    tuple(params),
                )
                return [ModelingPrintabilityReport(**row["payload"]) for row in cur.fetchall()]

    def add_modeling_printability_report(
        self, report: ModelingPrintabilityReport
    ) -> ModelingPrintabilityReport:
        self._upsert_payload(
            "modeling_printability_reports",
            _dump_model(report),
            timestamp_column="created_at",
        )
        return report

    def list_modeling_model_versions(
        self, *, project_id: str | None = None
    ) -> list[ModelingModelVersion]:
        clauses: list[str] = []
        params: list[Any] = []
        if project_id:
            clauses.append("payload->>'project_id' = %s")
            params.append(project_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT payload FROM modeling_model_versions
                    {where}
                    ORDER BY created_at DESC
                    """,
                    tuple(params),
                )
                return [ModelingModelVersion(**row["payload"]) for row in cur.fetchall()]

    def add_modeling_model_version(self, version: ModelingModelVersion) -> ModelingModelVersion:
        self._upsert_payload(
            "modeling_model_versions",
            _dump_model(version),
            timestamp_column="created_at",
        )
        return version

    def list_import_jobs(self) -> list[ChatGPTImportJob]:
        return self._list("import_jobs", ChatGPTImportJob)

    def get_import_job(self, job_id: str) -> ChatGPTImportJob | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload FROM import_jobs WHERE id = %s", (job_id,))
                row = cur.fetchone()
        return ChatGPTImportJob(**row["payload"]) if row else None

    def upsert_import_job(self, job: ChatGPTImportJob) -> ChatGPTImportJob:
        job.updated_at = now_utc()
        self._upsert_payload("import_jobs", _dump_model(job))
        return job

    def list_audit_events(self) -> list[AuditEvent]:
        return self._list("audit_events", AuditEvent, order_by="created_at DESC")

    def add_audit_event(self, event: AuditEvent) -> AuditEvent:
        self._upsert_payload("audit_events", _dump_model(event), timestamp_column="created_at")
        return event

    def get_cost_policy(self) -> CostPolicy:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload FROM cost_policy WHERE id = 'default'")
                row = cur.fetchone()
        if not row:
            return CostPolicy(monthly_budget_brl=settings.monthly_budget_brl)
        return CostPolicy(**row["payload"])

    def set_cost_policy(self, policy: CostPolicy) -> CostPolicy:
        policy.updated_at = now_utc()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO cost_policy (id, payload)
                    VALUES ('default', %s)
                    ON CONFLICT (id) DO UPDATE SET payload = EXCLUDED.payload, updated_at = now()
                    """,
                    (Jsonb(_dump_model(policy)),),
                )
        return policy

    def audit_events_for_month(self, month: str) -> list[AuditEvent]:
        start = datetime.fromisoformat(f"{month}-01T00:00:00+00:00")
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT payload FROM audit_events
                    WHERE created_at >= %s AND created_at < %s
                    ORDER BY created_at DESC
                    """,
                    (start, end),
                )
                return [AuditEvent(**row["payload"]) for row in cur.fetchall()]
