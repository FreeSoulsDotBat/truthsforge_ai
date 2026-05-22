"""Low-level SSE helpers shared by the chat-stream handlers.

Extracted from the ``chat.py`` monolith (architecture-map finding "monólitos
de borda") so both the main chat stream and the 3D modeling stream
(``chat_modeling.py``) can share them without a circular import. This module
is a leaf: it imports only the standard library.
"""

from __future__ import annotations

import json

# Default placeholder titles a brand-new chat may carry before the user types
# a real one. Used by the title-required gate and the modeling-stream title
# logic to decide when to overwrite the title.
DEFAULT_CHAT_TITLES = {"novo chat", "new chat"}


def _sse(event: str, payload: dict) -> str:
    """Serialize one Server-Sent Event frame (``event:``/``data:`` block)."""

    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _runtime_status(stage: str, label: str, detail: str | None = None) -> str:
    """Emit a ``status`` SSE event describing the current runtime stage."""

    payload: dict[str, object] = {"stage": stage, "label": label}
    if detail:
        payload["detail"] = detail
    return _sse("status", payload)


__all__ = ["DEFAULT_CHAT_TITLES", "_runtime_status", "_sse"]
