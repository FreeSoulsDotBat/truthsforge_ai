"""Project-scope resolution and validation for the chat routes.

Extracted from the ``chat.py`` monolith (architecture-map finding "monólitos
de borda"). Centralizes which projects an agent runtime may touch and the
403 guards that keep a conversation and its attachments inside the active
project's scope.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.core.contracts import (
    DEFAULT_GENERAL_PROJECT_ID,
    Agent,
    Document,
    PlatformFile,
)

MAX_CONTEXT_PROJECTS = 3


def _general_project_id(store) -> str:
    if hasattr(store, "list_projects"):
        general = next((project for project in store.list_projects() if project.is_general), None)
        if general is not None:
            return general.id
    return DEFAULT_GENERAL_PROJECT_ID


def _normalize_project_ids(
    project_ids: list[str], *, fallback_project_id: str, known_project_ids: set[str]
) -> list[str]:
    normalized: list[str] = []
    for raw_id in project_ids:
        if raw_id not in known_project_ids:
            continue
        if raw_id in normalized:
            continue
        normalized.append(raw_id)
    if not normalized:
        return [fallback_project_id]
    return normalized[:MAX_CONTEXT_PROJECTS]


def _agent_allowed_project_ids(agent: Agent | None, *, general_project_id: str) -> set[str]:
    if agent is None:
        return {general_project_id}
    allowed = set(agent.allowed_project_ids or [])
    if not allowed:
        return {general_project_id}
    return allowed


def _runtime_allowed_project_ids(
    agents: list[Agent | None], *, general_project_id: str
) -> set[str]:
    allowed: set[str] = set()
    for agent in agents:
        allowed.update(_agent_allowed_project_ids(agent, general_project_id=general_project_id))
    return allowed or {general_project_id}


def _validate_active_project_scope(
    *, active_project_id: str, runtime_allowed_project_ids: set[str]
) -> None:
    if active_project_id in runtime_allowed_project_ids:
        return
    raise HTTPException(
        status_code=403,
        detail="O agente selecionado não tem acesso ao projeto ativo desta conversa.",
    )


def _metadata_project_id(metadata: dict[str, Any] | None) -> str:
    if isinstance(metadata, dict):
        raw_project_id = metadata.get("project_id")
        if isinstance(raw_project_id, str) and raw_project_id.strip():
            return raw_project_id
    return DEFAULT_GENERAL_PROJECT_ID


def _document_scope_project_id(document: Document) -> str:
    return document.project_id or _metadata_project_id(document.metadata)


def _platform_file_scope_project_id(platform_file: PlatformFile) -> str:
    return _metadata_project_id(platform_file.metadata)


def _format_scoped_attachment_error(ids: list[str]) -> str:
    return ", ".join(ids[:5]) + ("..." if len(ids) > 5 else "")


def _validate_attachment_project_scope(
    *,
    active_project_id: str,
    runtime_allowed_project_ids: set[str],
    documents: list[Document],
    files: list[PlatformFile],
) -> None:
    if documents or files:
        if active_project_id not in runtime_allowed_project_ids:
            raise HTTPException(
                status_code=403,
                detail="O agente selecionado não tem acesso ao projeto ativo dos anexos.",
            )

    invalid_document_ids = [
        document.id
        for document in documents
        if _document_scope_project_id(document) != active_project_id
    ]
    if invalid_document_ids:
        raise HTTPException(
            status_code=403,
            detail=(
                "Documentos anexados fora do escopo do projeto ativo: "
                + _format_scoped_attachment_error(invalid_document_ids)
            ),
        )

    invalid_file_ids = [
        platform_file.id
        for platform_file in files
        if _platform_file_scope_project_id(platform_file) != active_project_id
    ]
    if invalid_file_ids:
        raise HTTPException(
            status_code=403,
            detail=(
                "Arquivos anexados fora do escopo do projeto ativo: "
                + _format_scoped_attachment_error(invalid_file_ids)
            ),
        )


__all__ = [
    "MAX_CONTEXT_PROJECTS",
    "_agent_allowed_project_ids",
    "_document_scope_project_id",
    "_format_scoped_attachment_error",
    "_general_project_id",
    "_metadata_project_id",
    "_normalize_project_ids",
    "_platform_file_scope_project_id",
    "_runtime_allowed_project_ids",
    "_validate_active_project_scope",
    "_validate_attachment_project_scope",
]
