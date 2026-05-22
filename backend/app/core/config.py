from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _resolve_from_project_root(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


class Settings(BaseModel):
    app_env: str = Field(default_factory=lambda: os.getenv("TRUTHS_FORGE_ENV", "development"))
    public_base_url: str = Field(
        default_factory=lambda: os.getenv("TRUTHS_FORGE_PUBLIC_BASE_URL", "http://127.0.0.1:8000")
    )
    data_dir: Path = Field(
        default_factory=lambda: _resolve_from_project_root(
            os.getenv("TRUTHS_FORGE_DATA_DIR", ".local")
        )
    )
    database_url: str = Field(
        default_factory=lambda: os.getenv(
            "TRUTHS_FORGE_DATABASE_URL",
            "postgresql://forge:forge_dev_password@127.0.0.1:5432/truths_forge_ai",
        )
    )
    qdrant_url: str = Field(
        default_factory=lambda: os.getenv("TRUTHS_FORGE_QDRANT_URL", "http://127.0.0.1:6333")
    )
    rag_embedding_backend: str = Field(
        default_factory=lambda: os.getenv("TRUTHS_FORGE_RAG_EMBEDDING_BACKEND", "auto").lower()
    )
    rag_embedding_model: str = Field(
        default_factory=lambda: os.getenv(
            "TRUTHS_FORGE_RAG_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
    )
    rag_embedding_dimensions: int = Field(
        default_factory=lambda: int(os.getenv("TRUTHS_FORGE_RAG_EMBEDDING_DIMENSIONS", "384"))
    )
    rag_ocr_languages: str = Field(
        default_factory=lambda: os.getenv("TRUTHS_FORGE_RAG_OCR_LANGUAGES", "por+eng")
    )
    redis_url: str = Field(
        default_factory=lambda: os.getenv("TRUTHS_FORGE_REDIS_URL", "redis://127.0.0.1:6379/0")
    )
    # Backend das filas de trabalho (índice/import). ``memory`` (default)
    # mantém a fila em processo — adequada para dev/single-replica. ``redis``
    # ou ``valkey`` usam o servidor em ``redis_url`` (stack local preferencial
    # do AGENTS.md), permitindo compartilhar a fila entre réplicas do backend.
    # Se o backend Redis/Valkey estiver indisponível no startup, a fila cai
    # graciosamente para memória (ver app/workers/job_queue.py).
    queue_backend: str = Field(
        default_factory=lambda: os.getenv("TRUTHS_FORGE_QUEUE_BACKEND", "memory").lower()
    )
    storage_backend: str = Field(
        default_factory=lambda: os.getenv("TRUTHS_FORGE_STORAGE_BACKEND", "auto")
    )
    allow_dev_llm: bool = Field(
        default_factory=lambda: (
            os.getenv("TRUTHS_FORGE_ALLOW_DEV_LLM", "true").lower() in {"1", "true", "yes", "on"}
        )
    )
    monthly_budget_brl: float = Field(
        default_factory=lambda: float(os.getenv("TRUTHS_FORGE_MONTHLY_BUDGET_BRL", "200"))
    )
    max_import_bytes: int = Field(
        default_factory=lambda: int(
            os.getenv("TRUTHS_FORGE_MAX_IMPORT_BYTES", str(5 * 1024 * 1024 * 1024))
        )
    )
    blender_executable: str | None = Field(
        default_factory=lambda: os.getenv("TRUTHS_FORGE_BLENDER_EXECUTABLE") or None
    )
    modeling_subprocess_timeout_seconds: int = Field(
        default_factory=lambda: int(os.getenv("TRUTHS_FORGE_MODELING_TIMEOUT_SECONDS", "90"))
    )
    modeling_mcp_transport: str = Field(
        default_factory=lambda: os.getenv("TRUTHS_FORGE_MCP_TRANSPORT", "in_process").lower()
    )
    fusion_mcp_url: str = Field(
        default_factory=lambda: os.getenv(
            "TRUTHS_FORGE_FUSION_MCP_URL", "http://127.0.0.1:27182/mcp"
        )
    )
    allowed_origins_raw: str = Field(
        default_factory=lambda: os.getenv(
            "TRUTHS_FORGE_ALLOWED_ORIGINS",
            "http://127.0.0.1:5173,http://localhost:5173,tauri://localhost,capacitor://localhost",
        )
    )
    # ADR-014 (Onda 2.9): when enabled, ``POST /api/chat/stream`` rejects
    # the first turn of a new chat unless the client provided a
    # non-default, non-blank title. Default OFF so the legacy frontend
    # keeps working until the Onda 5 UI ships; flip to ``true`` once
    # the React side enforces the title modal.
    require_chat_title: bool = Field(
        default_factory=lambda: (
            os.getenv("TRUTHS_FORGE_REQUIRE_CHAT_TITLE", "false").lower()
            in {"1", "true", "yes", "on"}
        )
    )

    # Observabilidade do módulo de modelagem 3D (ver plano em
    # C:\Users\Jonatan\.claude\plans\para-que-seja-mais-immutable-puffin.md).
    # Quando ``true``, o ``ModelingTracer`` persiste eventos de trace em
    # ``modeling_trace_events``, emite logs JSON estruturados em
    # ``app.modeling.*`` e enriquece eventos SSE com ``trace_id``. Default
    # ``true`` em dev para visibilidade imediata; desligar reduz custo de I/O
    # em produção pesada.
    modeling_observability_enabled: bool = Field(
        default_factory=lambda: (
            os.getenv("TRUTHS_FORGE_MODELING_OBSERVABILITY_ENABLED", "true").lower()
            in {"1", "true", "yes", "on"}
        )
    )
    # Quando ``true``, o payload dos eventos ``planner.llm_request`` /
    # ``planner.llm_response`` inclui prompt completo e resposta bruta do
    # LLM. Default ``false`` por privacidade — ativar só para debug.
    modeling_debug_llm_trace: bool = Field(
        default_factory=lambda: (
            os.getenv("TRUTHS_FORGE_MODELING_DEBUG_LLM_TRACE", "false").lower()
            in {"1", "true", "yes", "on"}
        )
    )
    # Reservas para job de retention futuro (não implementado nesta iteração).
    modeling_trace_retention_days_info: int = Field(
        default_factory=lambda: int(os.getenv("TRUTHS_FORGE_MODELING_TRACE_RETENTION_INFO", "30"))
    )
    modeling_trace_retention_days_error: int = Field(
        default_factory=lambda: int(
            os.getenv("TRUTHS_FORGE_MODELING_TRACE_RETENTION_ERROR", "180")
        )
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins_raw.split(",") if origin.strip()]

    @property
    def state_dir(self) -> Path:
        return self.data_dir / "state"

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def imports_dir(self) -> Path:
        return self.data_dir / "imports"

    @property
    def modeling_dir(self) -> Path:
        return self.data_dir / "modeling"

    def ensure_local_dirs(self) -> None:
        for path in [
            self.state_dir,
            self.files_dir,
            self.logs_dir,
            self.cache_dir,
            self.imports_dir,
            self.modeling_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
