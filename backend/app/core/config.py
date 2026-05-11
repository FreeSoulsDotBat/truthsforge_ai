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
    redis_url: str = Field(
        default_factory=lambda: os.getenv("TRUTHS_FORGE_REDIS_URL", "redis://127.0.0.1:6379/0")
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
    allowed_origins_raw: str = Field(
        default_factory=lambda: os.getenv(
            "TRUTHS_FORGE_ALLOWED_ORIGINS",
            "http://127.0.0.1:5173,http://localhost:5173,tauri://localhost,capacitor://localhost",
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
