from __future__ import annotations

import json
import logging
import re
import zipfile
from collections.abc import Callable, Iterable, Iterator
from datetime import UTC, datetime
from io import BytesIO, TextIOWrapper
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.core.config import settings
from app.core.contracts import (
    ChatGPTImportSummary,
    ChatMessage,
    ChatSession,
    ChatSessionWithMessages,
)
from app.files.library import is_image_file

logger = logging.getLogger(__name__)

MAX_IMPORT_BYTES = 5 * 1024 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024
MAX_ZIP_COMPRESSION_RATIO = 200
CHATGPT_SOURCE = "chatgpt_export"
ProgressCallback = Callable[[int, int | None, str], None]
CONVERSATION_SHARD_PATTERN = re.compile(r"^conversations-\d+\.json$", re.IGNORECASE)
FILE_POINTER_PATTERN = re.compile(
    r"(file-(?!service\b)[A-Za-z0-9]+|file_[A-Za-z0-9]+)", re.IGNORECASE
)


class ChatGPTImportError(ValueError):
    """Raised when an export cannot be parsed safely."""


def _iter_json_array_object_strings(
    handle: TextIOWrapper,
    total_bytes: int | None = None,
    progress: ProgressCallback | None = None,
) -> Iterator[str]:
    state = "before_array"
    depth = 0
    in_string = False
    escape = False
    processed_bytes = 0
    object_parts: list[str] = []

    while True:
        chunk = handle.read(CHUNK_SIZE)
        if not chunk:
            break
        processed_bytes += len(chunk)
        # Teto sobre bytes REALMENTE descomprimidos: o file_size do header do ZIP
        # pode estar subdimensionado (zip-bomb), então não confiamos só nele.
        if processed_bytes > MAX_IMPORT_BYTES:
            limit_gb = MAX_IMPORT_BYTES / 1024 / 1024 / 1024
            raise ChatGPTImportError(
                f"conversas do export maior que {limit_gb:.0f} GB ao descomprimir."
            )
        if progress:
            progress(
                min(processed_bytes, total_bytes or processed_bytes), total_bytes, "Lendo conversas"
            )
        for char in chunk:
            if state == "before_array":
                if char.isspace():
                    continue
                if char != "[":
                    raise ChatGPTImportError(
                        "conversations.json deve conter uma lista de conversas."
                    )
                state = "between_items"
                continue

            if state == "between_items":
                if char.isspace() or char == ",":
                    continue
                if char == "]":
                    state = "done"
                    continue
                if char != "{":
                    raise ChatGPTImportError("conversations.json deve conter objetos de conversa.")
                state = "in_object"
                depth = 1
                in_string = False
                escape = False
                object_parts = [char]
                continue

            if state == "done":
                if not char.isspace():
                    raise ChatGPTImportError(
                        "Conteúdo inesperado após o fim de conversations.json."
                    )
                continue

            object_parts.append(char)
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    yield "".join(object_parts)
                    object_parts = []
                    state = "between_items"

    if state != "done":
        raise ChatGPTImportError("conversations.json incompleto ou malformado.")


def _iter_conversations_from_text_handle(
    handle: TextIOWrapper,
    total_bytes: int | None = None,
    progress: ProgressCallback | None = None,
) -> Iterator[dict[str, Any]]:
    for raw_object in _iter_json_array_object_strings(
        handle, total_bytes=total_bytes, progress=progress
    ):
        try:
            item = json.loads(raw_object)
        except json.JSONDecodeError as exc:
            # Um objeto de conversa malformado não deve abortar o export inteiro:
            # pula a conversa corrompida e segue a contabilização por-conversa.
            logger.warning("Objeto de conversa ChatGPT malformado ignorado: %s", exc)
            continue
        if isinstance(item, dict):
            yield item


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}_{uuid5(NAMESPACE_URL, value).hex[:16]}"


def _datetime_from_export(value: Any, fallback: datetime | None = None) -> datetime:
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value, tz=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            pass
    if fallback is not None:
        return fallback
    return datetime.now(UTC)


def _pointer_token(pointer_value: Any) -> str | None:
    if not isinstance(pointer_value, str):
        return None
    candidate = pointer_value
    if "://" in candidate:
        candidate = candidate.split("://", maxsplit=1)[1]
    if "/" in candidate:
        candidate = candidate.split("/", maxsplit=1)[0]
    match = FILE_POINTER_PATTERN.search(candidate)
    if not match:
        match = FILE_POINTER_PATTERN.search(pointer_value)
    if not match:
        return None
    return match.group(1)


def _build_chatgpt_image_pointer_index(store: Any) -> dict[str, str]:
    if not hasattr(store, "list_platform_files"):
        return {}
    index: dict[str, str] = {}
    for platform_file in store.list_platform_files():
        if platform_file.source != "chatgpt_import":
            continue
        if not is_image_file(platform_file):
            continue
        token = _pointer_token(platform_file.original_filename) or _pointer_token(
            platform_file.filename
        )
        if not token:
            continue
        token_key = token.lower()
        if token_key in index:
            continue
        index[token_key] = (
            f"{settings.public_base_url.rstrip('/')}/api/files/{platform_file.id}/content"
        )
    return index


def _image_markdown_from_part(
    part: dict[str, Any], image_pointer_index: dict[str, str] | None
) -> str | None:
    if image_pointer_index is None:
        return None
    content_type = str(part.get("content_type") or "")
    if content_type != "image_asset_pointer":
        return None
    token = _pointer_token(part.get("asset_pointer"))
    if not token:
        return None
    image_url = image_pointer_index.get(token.lower())
    if not image_url:
        return None
    return f"![Imagem importada do ChatGPT]({image_url})"


def _message_text(
    content: dict[str, Any], image_pointer_index: dict[str, str] | None = None
) -> str:
    content_type = content.get("content_type")
    parts = content.get("parts")
    if isinstance(parts, list):
        text_parts = []
        for part in parts:
            if isinstance(part, str):
                text_parts.append(part)
            elif isinstance(part, dict):
                image_markdown = _image_markdown_from_part(part, image_pointer_index)
                nested_text = part.get("text") or part.get("name") or part.get("caption")
                if nested_text:
                    text_parts.append(str(nested_text))
                if image_markdown:
                    text_parts.append(image_markdown)
                elif part.get("content_type") == "image_asset_pointer":
                    text_parts.append("[imagem do ChatGPT indisponível no export]")
                elif nested_text:
                    continue
                else:
                    text_parts.append("[conteúdo não textual do ChatGPT omitido]")
        return "\n".join(part for part in text_parts if part).strip()

    if isinstance(content.get("text"), str):
        return content["text"].strip()

    if content_type and content_type != "text":
        return f"[conteúdo {content_type} do ChatGPT omitido]"

    return ""


def _ordered_nodes(conversation: dict[str, Any]) -> list[dict[str, Any]]:
    mapping = conversation.get("mapping")
    if not isinstance(mapping, dict):
        return []

    current_node = conversation.get("current_node")
    if isinstance(current_node, str) and current_node in mapping:
        ordered_ids = []
        node_id: str | None = current_node
        seen: set[str] = set()
        while node_id and node_id in mapping and node_id not in seen:
            seen.add(node_id)
            ordered_ids.append(node_id)
            parent = mapping[node_id].get("parent")
            node_id = parent if isinstance(parent, str) else None
        ordered_ids.reverse()
        return [mapping[node_id] for node_id in ordered_ids]

    nodes = list(mapping.values())
    return sorted(
        nodes,
        key=lambda node: (
            (node.get("message") or {}).get("create_time") is None,
            (node.get("message") or {}).get("create_time") or 0,
        ),
    )


def _validate_size(size: int, label: str = "Arquivo") -> None:
    if size > MAX_IMPORT_BYTES:
        limit_gb = MAX_IMPORT_BYTES / 1024 / 1024 / 1024
        raise ChatGPTImportError(f"{label} maior que {limit_gb:.0f} GB.")


def _conversation_entries(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    infos = archive.infolist()
    exact_entries = [
        item
        for item in infos
        if Path(item.filename.lower().replace("\\", "/")).name == "conversations.json"
    ]
    shard_entries = [
        item
        for item in infos
        if CONVERSATION_SHARD_PATTERN.match(Path(item.filename.replace("\\", "/")).name)
    ]
    conversation_entries = exact_entries or sorted(shard_entries, key=lambda item: item.filename)
    if not conversation_entries:
        if any(item.filename.lower().replace("\\", "/").endswith("chat.html") for item in infos):
            raise ChatGPTImportError(
                "Encontrei chat.html, mas esta versão importa conversas a partir de "
                "conversations.json ou conversations-000.json. Exporte novamente ou envie "
                "os arquivos de conversa direto."
            )
        raise ChatGPTImportError("ZIP sem conversations.json ou conversations-*.json.")

    total_size = sum(item.file_size for item in conversation_entries)
    _validate_size(total_size, "conversas do export")
    for entry in conversation_entries:
        if entry.compress_size <= 0:
            continue
        compression_ratio = entry.file_size / entry.compress_size
        # Razão de compressão é checada INCONDICIONALMENTE (independente do tamanho
        # descomprimido), pois uma zip-bomb pequena ainda explode em memória/CPU.
        if compression_ratio > MAX_ZIP_COMPRESSION_RATIO:
            raise ChatGPTImportError("ZIP com taxa de compressão suspeita para importação segura.")
    return conversation_entries


def iter_chatgpt_conversations_from_path(
    path: Path,
    filename: str,
    progress: ProgressCallback | None = None,
) -> Iterator[dict[str, Any]]:
    _validate_size(path.stat().st_size)
    suffix = filename.lower().rsplit(".", maxsplit=1)[-1] if "." in filename else ""
    if suffix == "zip":
        try:
            with zipfile.ZipFile(path) as archive:
                conversation_entries = _conversation_entries(archive)
                total_bytes = sum(item.file_size for item in conversation_entries)
                processed_base = 0
                for entry in conversation_entries:
                    with archive.open(entry) as binary_handle:
                        text_handle = TextIOWrapper(binary_handle, encoding="utf-8")

                        def entry_progress(
                            processed_bytes: int, _total_bytes: int | None, step: str
                        ) -> None:
                            if progress:
                                progress(
                                    processed_base + processed_bytes,
                                    total_bytes,
                                    f"{step}: {Path(entry.filename).name}",
                                )

                        yield from _iter_conversations_from_text_handle(
                            text_handle,
                            total_bytes=entry.file_size,
                            progress=entry_progress,
                        )
                    processed_base += entry.file_size
        except zipfile.BadZipFile as exc:
            raise ChatGPTImportError("ZIP inválido ou corrompido.") from exc
    else:
        with path.open("r", encoding="utf-8") as handle:
            yield from _iter_conversations_from_text_handle(
                handle,
                total_bytes=path.stat().st_size,
                progress=progress,
            )


def parse_chatgpt_conversations(raw: bytes, filename: str) -> list[dict[str, Any]]:
    _validate_size(len(raw))
    suffix = filename.lower().rsplit(".", maxsplit=1)[-1] if "." in filename else ""
    if suffix == "zip":
        try:
            with zipfile.ZipFile(BytesIO(raw)) as archive:
                conversations = []
                for entry in _conversation_entries(archive):
                    with archive.open(entry) as binary_handle:
                        text_handle = TextIOWrapper(binary_handle, encoding="utf-8")
                        conversations.extend(
                            _iter_conversations_from_text_handle(
                                text_handle, total_bytes=entry.file_size
                            )
                        )
                return conversations
        except zipfile.BadZipFile as exc:
            raise ChatGPTImportError("ZIP inválido ou corrompido.") from exc

    text_handle = TextIOWrapper(BytesIO(raw), encoding="utf-8")
    return list(_iter_conversations_from_text_handle(text_handle, total_bytes=len(raw)))


def conversation_to_session(
    conversation: dict[str, Any], image_pointer_index: dict[str, str] | None = None
) -> tuple[ChatSession, list[ChatMessage]]:
    external_id = str(
        conversation.get("id")
        or conversation.get("conversation_id")
        or f"{conversation.get('title', 'sem-titulo')}:{conversation.get('create_time', '')}"
    )
    session_id = _stable_id("chatgpt", external_id)
    title = str(conversation.get("title") or "Conversa importada do ChatGPT").strip()
    created_at = _datetime_from_export(conversation.get("create_time"))
    updated_at = _datetime_from_export(
        conversation.get("update_time") or conversation.get("create_time"),
        fallback=created_at,
    )
    session = ChatSession(
        id=session_id,
        title=title[:140] or "Conversa importada do ChatGPT",
        archived=bool(conversation.get("is_archived", False)),
        metadata={
            "source": CHATGPT_SOURCE,
            "external_id": external_id,
            "import_kind": "history",
        },
        created_at=created_at,
        updated_at=updated_at,
    )

    messages = []
    for node in _ordered_nodes(conversation):
        raw_message = node.get("message")
        if not isinstance(raw_message, dict):
            continue
        metadata = (
            raw_message.get("metadata") if isinstance(raw_message.get("metadata"), dict) else {}
        )
        if metadata.get("is_visually_hidden_from_conversation"):
            continue
        author = raw_message.get("author") if isinstance(raw_message.get("author"), dict) else {}
        role = author.get("role")
        if role not in {"system", "user", "assistant", "tool"}:
            continue
        content = raw_message.get("content") if isinstance(raw_message.get("content"), dict) else {}
        text = _message_text(content, image_pointer_index=image_pointer_index)
        if not text:
            continue
        message_external_id = str(raw_message.get("id") or node.get("id") or len(messages))
        messages.append(
            ChatMessage(
                id=_stable_id("chatgptmsg", f"{external_id}:{message_external_id}"),
                session_id=session.id,
                role=role,
                content=text,
                model_id=metadata.get("model_slug") or metadata.get("default_model_slug"),
                metadata={
                    "source": CHATGPT_SOURCE,
                    "external_id": message_external_id,
                    "conversation_external_id": external_id,
                    "content_type": content.get("content_type"),
                    "model_slug": metadata.get("model_slug") or metadata.get("default_model_slug"),
                },
                created_at=_datetime_from_export(
                    raw_message.get("create_time"),
                    fallback=updated_at,
                ),
            )
        )

    return session, messages


def _existing_ids(sessions: Iterable[ChatSessionWithMessages]) -> tuple[set[str], set[str]]:
    session_ids = set()
    message_ids = set()
    for session in sessions:
        session_ids.add(session.id)
        for message in session.messages:
            message_ids.add(message.id)
    return session_ids, message_ids


def import_chatgpt_export(raw: bytes, filename: str, store: Any) -> ChatGPTImportSummary:
    conversations = parse_chatgpt_conversations(raw, filename)
    image_pointer_index = _build_chatgpt_image_pointer_index(store)
    summary = ChatGPTImportSummary(source_filename=filename, conversations_found=len(conversations))

    for index, conversation in enumerate(conversations, start=1):
        _import_conversation(
            conversation,
            index,
            store,
            summary,
            image_pointer_index=image_pointer_index,
        )

    return summary


def _session_exists(
    store: Any, session_id: str, existing_session_ids: set[str] | None = None
) -> bool:
    if existing_session_ids is not None:
        return session_id in existing_session_ids
    if hasattr(store, "chat_session_exists"):
        return bool(store.chat_session_exists(session_id))
    return any(session.id == session_id for session in store.list_chat_sessions())


def _add_messages(store: Any, messages: list[ChatMessage]) -> tuple[int, int]:
    image_content_markers = (
        "![Imagem importada do ChatGPT]",
        "[imagem do ChatGPT indisponível no export]",
    )
    if hasattr(store, "add_messages"):
        imported, skipped = store.add_messages(messages)
        if skipped and hasattr(store, "add_message"):
            for message in messages:
                if not any(marker in message.content for marker in image_content_markers):
                    continue
                store.add_message(message)
        return imported, skipped

    _existing_session_ids, existing_message_ids = _existing_ids(store.list_chat_sessions())
    imported = 0
    skipped = 0
    for message in messages:
        if message.id in existing_message_ids:
            if hasattr(store, "add_message"):
                store.add_message(message)
            skipped += 1
            continue
        store.add_message(message)
        existing_message_ids.add(message.id)
        imported += 1
    return imported, skipped


def _import_conversation(
    conversation: dict[str, Any],
    index: int,
    store: Any,
    summary: ChatGPTImportSummary,
    existing_session_ids: set[str] | None = None,
    image_pointer_index: dict[str, str] | None = None,
) -> None:
    try:
        session, messages = conversation_to_session(
            conversation, image_pointer_index=image_pointer_index
        )
    except Exception as exc:
        summary.errors.append(f"Conversa {index}: {str(exc)[:200]}")
        return

    if _session_exists(store, session.id, existing_session_ids=existing_session_ids):
        summary.sessions_skipped += 1
    else:
        store.upsert_chat_session(session)
        if existing_session_ids is not None:
            existing_session_ids.add(session.id)
        summary.sessions_imported += 1

    imported, skipped = _add_messages(store, messages)
    summary.messages_imported += imported
    summary.messages_skipped += skipped


def import_chatgpt_export_from_path(
    path: Path,
    filename: str,
    store: Any,
    progress: ProgressCallback | None = None,
) -> ChatGPTImportSummary:
    summary = ChatGPTImportSummary(source_filename=filename)
    image_pointer_index = _build_chatgpt_image_pointer_index(store)
    existing_session_ids: set[str] | None = None
    if not hasattr(store, "chat_session_exists"):
        existing_session_ids, _existing_message_ids = _existing_ids(store.list_chat_sessions())

    for index, conversation in enumerate(
        iter_chatgpt_conversations_from_path(path, filename, progress=progress), start=1
    ):
        summary.conversations_found = index
        try:
            _import_conversation(
                conversation,
                index,
                store,
                summary,
                existing_session_ids=existing_session_ids,
                image_pointer_index=image_pointer_index,
            )
        except Exception as exc:
            summary.errors.append(f"Conversa {index}: {str(exc)[:200]}")
            continue
    return summary
