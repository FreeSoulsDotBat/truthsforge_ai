"""Tests for ``POST /api/chat/sessions/{chat_id}/attachments/analyze``
(Onda 2.7, ADR-013).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.contracts import (
    ChatSession,
    ModelingSoftware,
    PlatformFile,
)
from app.main import app
from app.modeling.blender_adapter import BlenderAdapter
from app.storage.store import get_store


def _create_chat(*, is_modeling_3d: bool, title: str = "Suporte para fone") -> ChatSession:
    store = get_store()
    chat = ChatSession(
        title=title,
        is_modeling_3d=is_modeling_3d,
        modeling_software_preference=(ModelingSoftware.blender if is_modeling_3d else None),
    )
    store.upsert_chat_session(chat)
    return chat


def _direct_insert(name: str, content: bytes, storage: Path) -> PlatformFile:
    """Write the bytes to ``storage`` and push a PlatformFile row into
    the active store. Bypasses ``PlatformFileCreate`` so the fixture
    stays self-contained without depending on the upload pipeline.
    """

    storage.write_bytes(content)
    store = get_store()
    pf = PlatformFile(
        filename=name,
        original_filename=name,
        content_type="image/png" if name.endswith(".png") else None,
        size_bytes=len(content),
        storage_path=str(storage),
        source="chat_attachment",
    )
    if hasattr(store, "_data"):  # dev store path
        store._data["platform_files"].append(pf.model_dump(mode="json"))
        store._write()
    else:  # pragma: no cover - postgres path not exercised in unit tests
        store.create_platform_file(pf)  # type: ignore[arg-type]
    return pf


@pytest.fixture(autouse=True)
def _blender_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force the metadata-only fallback so the test doesn't depend on a
    # real Blender install.
    monkeypatch.setattr(BlenderAdapter, "is_available", lambda self: False)


def test_analyze_returns_200_for_modeling_chat(tmp_path: Path) -> None:
    chat = _create_chat(is_modeling_3d=True)
    pf = _direct_insert("ref.png", b"PNGDATA", tmp_path / "ref.png")

    client = TestClient(app)
    response = client.post(
        f"/api/chat/sessions/{chat.id}/attachments/analyze",
        json={"file_id": pf.id},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["file_id"] == pf.id
    assert body["kind"] == "image"
    assert body["ok"] is True
    assert body["context_text"]
    assert isinstance(body["suggestions"], list)


def test_analyze_returns_400_when_chat_is_not_modeling_3d(tmp_path: Path) -> None:
    chat = _create_chat(is_modeling_3d=False, title="Conversa normal")
    pf = _direct_insert("ref.png", b"PNGDATA", tmp_path / "ref.png")

    client = TestClient(app)
    response = client.post(
        f"/api/chat/sessions/{chat.id}/attachments/analyze",
        json={"file_id": pf.id},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"] == "chat_is_not_modeling_3d"


def test_analyze_returns_404_for_unknown_chat(tmp_path: Path) -> None:
    pf = _direct_insert("ref.png", b"PNGDATA", tmp_path / "ref.png")

    client = TestClient(app)
    response = client.post(
        "/api/chat/sessions/chat_does_not_exist/attachments/analyze",
        json={"file_id": pf.id},
    )

    assert response.status_code == 404


def test_analyze_returns_200_with_ok_false_for_unknown_file(tmp_path: Path) -> None:
    chat = _create_chat(is_modeling_3d=True)

    client = TestClient(app)
    response = client.post(
        f"/api/chat/sessions/{chat.id}/attachments/analyze",
        json={"file_id": "file_does_not_exist"},
    )

    # Endpoint sempre devolve 200 com ok=false para falhas internas do
    # analyzer; o agente decide o que fazer com o resultado.
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error"] == "platform_file_not_found"


def test_analyze_rejects_blank_file_id() -> None:
    chat = _create_chat(is_modeling_3d=True)

    client = TestClient(app)
    response = client.post(
        f"/api/chat/sessions/{chat.id}/attachments/analyze",
        json={"file_id": ""},
    )

    assert response.status_code == 422  # Pydantic min_length=1 violation
