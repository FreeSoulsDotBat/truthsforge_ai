from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from app.core.config import settings
from app.core.contracts import (
    ChatMessage,
    ChatSessionDeleteResult,
    ChatSessionWithMessages,
    PlatformFile,
)
from app.files.library import is_zip_storage_path
from app.rag.indexing import delete_documents_for_platform_file

MESSAGE_FILE_KEYS = ("attached_file_ids", "generated_file_ids")


def _safe_local_path(storage_path: str) -> Path | None:
    path = Path(storage_path).resolve()
    data_dir = settings.data_dir.resolve()
    if not path.is_relative_to(data_dir):
        return None
    return path


def extract_message_file_ids(message: ChatMessage) -> set[str]:
    metadata = message.metadata if isinstance(message.metadata, dict) else {}
    file_ids: set[str] = set()
    for key in MESSAGE_FILE_KEYS:
        raw_ids = metadata.get(key)
        if not isinstance(raw_ids, list):
            continue
        for raw_id in raw_ids:
            if isinstance(raw_id, str) and raw_id.strip():
                file_ids.add(raw_id)

    raw_attached_files = metadata.get("attached_files")
    if isinstance(raw_attached_files, list):
        for item in raw_attached_files:
            if not isinstance(item, dict):
                continue
            file_id = item.get("file_id") or item.get("id")
            if isinstance(file_id, str) and file_id.strip():
                file_ids.add(file_id)

    return file_ids


def session_related_file_ids(store, session: ChatSessionWithMessages) -> set[str]:
    related_ids = set()
    for message in session.messages:
        related_ids.update(extract_message_file_ids(message))

    if hasattr(store, "list_platform_files"):
        for platform_file in store.list_platform_files():
            metadata = platform_file.metadata if isinstance(platform_file.metadata, dict) else {}
            if metadata.get("session_id") == session.id:
                related_ids.add(platform_file.id)
    return related_ids


def other_sessions_file_ids(store, current_session_id: str) -> set[str]:
    referenced: set[str] = set()
    for session in store.list_chat_sessions():
        if session.id == current_session_id:
            continue
        for message in session.messages:
            referenced.update(extract_message_file_ids(message))
    return referenced


def knowledge_base_file_ids(store) -> set[str]:
    if not hasattr(store, "list_knowledge_base_documents") or not hasattr(store, "list_documents"):
        return set()

    linked_document_ids = {
        item.document_id for item in store.list_knowledge_base_documents() if item.document_id
    }
    if not linked_document_ids:
        return set()

    linked_file_ids: set[str] = set()
    for document in store.list_documents():
        if document.id not in linked_document_ids:
            continue
        metadata = document.metadata if isinstance(document.metadata, dict) else {}
        file_id = metadata.get("file_id")
        if isinstance(file_id, str) and file_id.strip():
            linked_file_ids.add(file_id)
    return linked_file_ids


def delete_platform_file_with_storage(store, file_id: str, all_files: list[PlatformFile]) -> bool:
    deleted = store.delete_platform_file(file_id)
    if deleted is None:
        return False
    delete_documents_for_platform_file(store, file_id)
    if is_zip_storage_path(deleted.storage_path):
        return True
    if any(
        platform_file.metadata.get("archive_file_id") == deleted.id
        for platform_file in all_files
        if platform_file.id != deleted.id
    ):
        return True

    if any(
        platform_file.id != deleted.id and platform_file.storage_path == deleted.storage_path
        for platform_file in all_files
    ):
        return True

    path = _safe_local_path(deleted.storage_path)
    if path is not None and path.is_file():
        path.unlink(missing_ok=True)
    return True


def delete_chat_session_with_files(
    store, session_id: str, *, delete_files: bool = True
) -> ChatSessionDeleteResult:
    session = store.get_chat_session(session_id) if hasattr(store, "get_chat_session") else None
    if session is None:
        session = next(
            (item for item in store.list_chat_sessions() if item.id == session_id),
            None,
        )
    if session is None:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")

    deleted_message_count = len(session.messages)
    deleted_file_ids: list[str] = []
    removable_file_ids: list[str] = []
    if (
        delete_files
        and hasattr(store, "list_platform_files")
        and hasattr(store, "delete_platform_file")
    ):
        related_file_ids = session_related_file_ids(store, session)
        # Os scans abaixo sao O(sessoes x mensagens) + O(documentos). So fazem
        # sentido se ha candidatos a remover; quando a sessao nao referencia
        # nenhum arquivo, evitamos materializar/varrer todas as sessoes e docs.
        if related_file_ids:
            referenced_elsewhere = other_sessions_file_ids(store, session_id)
            referenced_by_knowledge_base = knowledge_base_file_ids(store)
            removable_file_ids = sorted(
                file_id
                for file_id in related_file_ids
                if file_id not in referenced_elsewhere
                and file_id not in referenced_by_knowledge_base
            )

    if not hasattr(store, "delete_chat_session") or not store.delete_chat_session(session_id):
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")

    if removable_file_ids:
        all_files = store.list_platform_files()
        for file_id in removable_file_ids:
            if delete_platform_file_with_storage(store, file_id, all_files):
                deleted_file_ids.append(file_id)

    return ChatSessionDeleteResult(
        session_id=session_id,
        deleted_message_count=deleted_message_count,
        deleted_file_ids=deleted_file_ids,
    )
