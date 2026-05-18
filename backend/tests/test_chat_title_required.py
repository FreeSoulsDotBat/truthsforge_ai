"""Tests for the ADR-014 title-required gate on ``POST /api/chat/stream``
(Onda 2.9).

The gate is feature-flagged via ``settings.require_chat_title`` so the
legacy frontend keeps working until the Onda 5 React UI ships. Once the
flag flips to ``true`` (env var or test override), the backend must
reject the first turn of a brand-new chat unless the client provided a
non-default, non-blank title.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


@pytest.fixture(autouse=True)
def _require_chat_title_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "require_chat_title", True)


def _post_stream(client: TestClient, payload: dict) -> dict:
    response = client.post("/api/chat/stream", json=payload)
    return {
        "status": response.status_code,
        "json": response.json() if response.headers.get("content-type", "").startswith(
            "application/json"
        )
        else None,
        "text": response.text,
    }


def test_blank_title_rejected_with_422() -> None:
    client = TestClient(app)
    response = _post_stream(
        client,
        {"message": "olá", "title": ""},
    )
    assert response["status"] == 422
    detail = response["json"]["detail"]
    assert detail["error"] == "chat_title_required"
    assert "título" in detail["message"]


def test_default_novo_chat_rejected_with_422() -> None:
    client = TestClient(app)
    response = _post_stream(
        client,
        {"message": "olá", "title": "Novo chat"},
    )
    assert response["status"] == 422
    assert response["json"]["detail"]["error"] == "chat_title_required"


def test_default_new_chat_rejected_with_422() -> None:
    client = TestClient(app)
    response = _post_stream(
        client,
        {"message": "olá", "title": "New chat"},
    )
    assert response["status"] == 422


def test_whitespace_only_title_rejected_with_422() -> None:
    client = TestClient(app)
    response = _post_stream(
        client,
        {"message": "olá", "title": "   "},
    )
    assert response["status"] == 422


def test_meaningful_title_does_not_trigger_422() -> None:
    """A real title bypasses the gate; the stream may still fail for
    unrelated reasons (no provider configured, etc.) but the status
    must not be 422 / chat_title_required."""

    client = TestClient(app)
    response = _post_stream(
        client,
        {"message": "olá", "title": "Suporte para fone — versão 1"},
    )
    if response["status"] == 422 and isinstance(response["json"], dict):
        detail = response["json"].get("detail")
        if isinstance(detail, dict):
            assert detail.get("error") != "chat_title_required"


def test_flag_off_keeps_legacy_default_title_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the flag, the gate is dormant — sanity-check the toggle."""

    monkeypatch.setattr(settings, "require_chat_title", False)
    client = TestClient(app)
    response = _post_stream(client, {"message": "olá", "title": "Novo chat"})
    if response["status"] == 422 and isinstance(response["json"], dict):
        detail = response["json"].get("detail")
        if isinstance(detail, dict):
            assert detail.get("error") != "chat_title_required"
