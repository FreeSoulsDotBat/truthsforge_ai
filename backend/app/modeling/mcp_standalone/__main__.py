"""Entrypoint do servidor MCP standalone: ``python -m app.modeling.mcp_standalone``.

Bind **loopback** por padrão (P1/RNF-001). Para acesso remoto, prefira VPN/
pareamento (Tailscale/WireGuard) — nunca exposição pública ingênua.
"""

from __future__ import annotations

import logging

import uvicorn

from app.core.config import settings
from app.modeling.mcp_standalone.app import create_app
from app.modeling.mcp_standalone.auth import load_or_create_token, token_path

logger = logging.getLogger(__name__)

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    token = load_or_create_token()
    host = settings.modeling_mcp_server_host
    port = settings.modeling_mcp_server_port

    if host not in _LOOPBACK_HOSTS:
        logger.warning(
            "Bind não-loopback (%s): exponha SOMENTE via VPN/pareamento (P1/RNF-001).",
            host,
        )

    logger.info(
        "Servidor MCP standalone em http://%s:%d/mcp (token em %s).",
        host,
        port,
        token_path(),
    )
    uvicorn.run(create_app(token=token), host=host, port=port, log_level="info")


if __name__ == "__main__":  # pragma: no cover
    main()
