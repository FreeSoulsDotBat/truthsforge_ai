"""Prompt assets for the chat-first 3D modeling agent (ADR-013, Onda 2.5).

Prompts live as Markdown files in this directory so designers can iterate
on them without touching Python code. The helpers below load them lazily
and cache the result in process memory.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent


def _load(name: str) -> str:
    path = _PROMPTS_DIR / name
    if not path.is_file():
        raise FileNotFoundError(
            f"Prompt asset {name!r} not found at {path}."
        )
    return path.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def discovery_system_prompt() -> str:
    """Return the discovery/editing system prompt as a single string.

    Cached after the first read. To pick up edits during development,
    call :func:`discovery_system_prompt.cache_clear()` (lru_cache API).
    """

    return _load("discovery_system.md")


__all__ = ["discovery_system_prompt"]
