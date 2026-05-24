"""Servidor MCP standalone para modelagem 3D (ADR-017).

Expõe as tools Fusion (allowlist de fonte única em ``tool_registry``) atrás de
um servidor MCP-compliant (SDK oficial) com transport HTTP streamable + auth
Bearer, local-first. O backend do produto consome este servidor como cliente
(``LocalMCPClient`` em modo ``mcp_http``); o executor real continua sendo o
``FusionDesktopAdapter``.

Ver ``specs/005-modeling-3d-fusion/micro/fase-1-mcp-standalone.md``.
"""

from __future__ import annotations

from app.modeling.mcp_standalone.app import create_app
from app.modeling.mcp_standalone.client import StandaloneMCPClient
from app.modeling.mcp_standalone.server import SERVER_NAME, build_server

__all__ = ["create_app", "build_server", "StandaloneMCPClient", "SERVER_NAME"]
