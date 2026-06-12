"""Autenticação local-first do servidor MCP standalone (ADR-017 / RNF-001).

Token Bearer estático: precedência para o token explícito em
``settings.modeling_mcp_server_token``; na ausência, gera um token aleatório e
o persiste em ``modeling_dir/mcp_server_token`` (reaproveitado entre execuções).
"""

from __future__ import annotations

import os
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
    # Cria o arquivo já com permissão restrita e de forma atômica (O_EXCL),
    # evitando a janela world-readable entre write+chmod em POSIX. O_EXCL
    # também resolve a race de primeira execução: se outro processo já criou
    # o arquivo, relemos o token gravado em vez de sobrescrever — assim
    # cliente e servidor convergem para o mesmo token.
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
        # Arquivo existe mas está vazio (gravação parcial); sobrescreve pelo
        # mesmo caminho restritivo: restringe a permissão ANTES de gravar o
        # segredo (o arquivo ainda está vazio, então nada vaza), eliminando a
        # janela world-readable que um write+chmod posterior abriria em POSIX.
        try:  # melhor-esforço (no-op/redundante em ACLs do Windows)
            path.chmod(0o600)
        except OSError:
            pass
        fd = os.open(str(path), os.O_WRONLY | os.O_TRUNC)
        _write_token_fd(fd, token)
        return token
    _write_token_fd(fd, token)
    try:  # melhor-esforço (no-op/redundante em ACLs do Windows)
        path.chmod(0o600)
    except OSError:
        pass
    return token


def _write_token_fd(fd: int, token: str) -> None:
    """Grava o token num descritor já aberto com permissões restritas."""
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(token)


def verify_token(provided: str | None, expected: str) -> bool:
    """Comparação em tempo constante; falso para token vazio/ausente."""
    if not provided or not expected:
        return False
    return secrets.compare_digest(provided, expected)
