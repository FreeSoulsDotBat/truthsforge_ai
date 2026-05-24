"""Autenticação local-first do servidor MCP standalone (ADR-017 / RNF-001).

Token Bearer estático: precedência para o token explícito em
``settings.modeling_mcp_server_token``; na ausência, gera um token aleatório e
o persiste em ``modeling_dir/mcp_server_token`` (reaproveitado entre execuções).
"""

from __future__ import annotations

import secrets
from pathlib import Path

from app.core.config import settings

TOKEN_FILENAME = "mcp_server_token"


def token_path() -> Path:
    return settings.modeling_dir / TOKEN_FILENAME


def load_or_create_token() -> str:
    """Retorna o token configurado, ou um persistido, ou cria e persiste um novo."""
    configured = (settings.modeling_mcp_server_token or "").strip()
    if configured:
        return configured

    path = token_path()
    try:
        existing = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        existing = ""
    if existing:
        return existing

    token = secrets.token_urlsafe(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token, encoding="utf-8")
    try:  # melhor-esforço (no-op em ACLs do Windows)
        path.chmod(0o600)
    except OSError:
        pass
    return token


def verify_token(provided: str | None, expected: str) -> bool:
    """Comparação em tempo constante; falso para token vazio/ausente."""
    if not provided or not expected:
        return False
    return secrets.compare_digest(provided, expected)
