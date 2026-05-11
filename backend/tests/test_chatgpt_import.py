from __future__ import annotations

import json
import zipfile
from io import BytesIO

from app.core.contracts import ChatMessage, ChatSession, ChatSessionWithMessages
from app.importers.chatgpt import (
    conversation_to_session,
    import_chatgpt_export,
    parse_chatgpt_conversations,
)


class FakeStore:
    def __init__(self) -> None:
        self.sessions: dict[str, ChatSession] = {}
        self.messages: dict[str, ChatMessage] = {}

    def list_chat_sessions(self) -> list[ChatSessionWithMessages]:
        return [
            ChatSessionWithMessages(
                **session.model_dump(),
                messages=[
                    message
                    for message in self.messages.values()
                    if message.session_id == session.id
                ],
            )
            for session in self.sessions.values()
        ]

    def upsert_chat_session(self, session: ChatSession) -> ChatSession:
        self.sessions[session.id] = session
        return session

    def add_message(self, message: ChatMessage) -> ChatMessage:
        self.messages[message.id] = message
        return message


def sample_export() -> list[dict]:
    return [
        {
            "id": "conv_123",
            "title": "Teste importado",
            "create_time": 1_700_000_000,
            "update_time": 1_700_000_020,
            "current_node": "assistant-1",
            "mapping": {
                "root": {"id": "root", "message": None, "parent": None},
                "user-1": {
                    "id": "user-1",
                    "parent": "root",
                    "message": {
                        "id": "msg-user-1",
                        "author": {"role": "user"},
                        "create_time": 1_700_000_001,
                        "content": {"content_type": "text", "parts": ["Olá"]},
                        "metadata": {},
                    },
                },
                "assistant-1": {
                    "id": "assistant-1",
                    "parent": "user-1",
                    "message": {
                        "id": "msg-assistant-1",
                        "author": {"role": "assistant"},
                        "create_time": 1_700_000_002,
                        "content": {"content_type": "text", "parts": ["Oi!"]},
                        "metadata": {"model_slug": "gpt-test"},
                    },
                },
            },
        }
    ]


def test_parse_chatgpt_zip_finds_conversations_json() -> None:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("export/conversations.json", json.dumps(sample_export()))

    conversations = parse_chatgpt_conversations(buffer.getvalue(), "chatgpt.zip")

    assert conversations[0]["id"] == "conv_123"


def test_parse_chatgpt_zip_prefers_history_shards_over_shared_conversations() -> None:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "shared_conversations.json",
            json.dumps([{"id": "shared", "title": "Compartilhada"}]),
        )
        archive.writestr("conversations-001.json", json.dumps(sample_export()))
        archive.writestr(
            "conversations-000.json",
            json.dumps([{**sample_export()[0], "id": "conv_000"}]),
        )

    conversations = parse_chatgpt_conversations(buffer.getvalue(), "chatgpt.zip")

    assert [conversation["id"] for conversation in conversations] == ["conv_000", "conv_123"]


def test_import_chatgpt_export_is_idempotent() -> None:
    store = FakeStore()
    raw = json.dumps(sample_export()).encode("utf-8")

    first = import_chatgpt_export(raw, "conversations.json", store)
    second = import_chatgpt_export(raw, "conversations.json", store)

    assert first.conversations_found == 1
    assert first.sessions_imported == 1
    assert first.messages_imported == 2
    assert second.sessions_skipped == 1
    assert second.messages_skipped == 2
    assert len(store.sessions) == 1
    assert len(store.messages) == 2
    assert next(iter(store.sessions.values())).metadata["source"] == "chatgpt_export"


def test_conversation_to_session_renders_image_asset_pointer() -> None:
    conversation = {
        "id": "conv_image",
        "title": "Imagem importada",
        "create_time": 1_700_100_000,
        "update_time": 1_700_100_100,
        "current_node": "assistant-image",
        "mapping": {
            "root": {"id": "root", "message": None, "parent": None},
            "assistant-image": {
                "id": "assistant-image",
                "parent": "root",
                "message": {
                    "id": "msg-image-1",
                    "author": {"role": "assistant"},
                    "create_time": 1_700_100_010,
                    "content": {
                        "content_type": "multimodal_text",
                        "parts": [
                            {
                                "content_type": "image_asset_pointer",
                                "asset_pointer": "file-service://file-TestAsset123",
                                "width": 1024,
                                "height": 1024,
                            }
                        ],
                    },
                    "metadata": {"model_slug": "gpt-test-image"},
                },
            },
        },
    }

    session, messages = conversation_to_session(
        conversation, image_pointer_index={"file-testasset123": "/api/files/file_abc/content"}
    )

    assert session.title == "Imagem importada"
    assert len(messages) == 1
    assert "![Imagem importada do ChatGPT](/api/files/file_abc/content)" in messages[0].content


def test_conversation_to_session_marks_missing_image_asset_pointer() -> None:
    conversation = {
        "id": "conv_image_missing",
        "title": "Imagem ausente",
        "create_time": 1_700_200_000,
        "update_time": 1_700_200_100,
        "current_node": "assistant-image",
        "mapping": {
            "root": {"id": "root", "message": None, "parent": None},
            "assistant-image": {
                "id": "assistant-image",
                "parent": "root",
                "message": {
                    "id": "msg-image-missing",
                    "author": {"role": "assistant"},
                    "create_time": 1_700_200_010,
                    "content": {
                        "content_type": "multimodal_text",
                        "parts": [
                            {
                                "content_type": "image_asset_pointer",
                                "asset_pointer": "file-service://file-MissingAsset999",
                                "width": 1024,
                                "height": 1024,
                            }
                        ],
                    },
                    "metadata": {"model_slug": "gpt-test-image"},
                },
            },
        },
    }

    _session, messages = conversation_to_session(conversation, image_pointer_index={})

    assert len(messages) == 1
    assert "[imagem do ChatGPT indisponível no export]" in messages[0].content
