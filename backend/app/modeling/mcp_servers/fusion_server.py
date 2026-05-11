"""stdio JSON-RPC server for Fusion 360 — mock until the desktop add-in lands.

Mirrors ``blender_server`` so the wire surface is identical from the client's
perspective. ``tools/call`` returns a deterministic mock envelope and never
touches Fusion; the real bridge will arrive with PR #6.
"""

from __future__ import annotations

import sys
from typing import Any

from app.core.contracts import ModelingSoftware
from app.modeling.mcp_servers._server_base import run_server

SERVER_NAME = "fusion_mcp"

FUSION_TOOLS: list[str] = [
    "fusion.create_sketch",
    "fusion.extrude_profile",
    "fusion.validate_dimensions",
    "fusion.validate_printability",
]


def handle_tool_call(name: str, arguments: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    if name not in FUSION_TOOLS:
        return {
            "ok": False,
            "mcp_server": SERVER_NAME,
            "transport": "stdio",
            "tool_name": name,
            "software": ModelingSoftware.fusion.value,
            "error_code": "fusion.tool_not_allowlisted",
            "retryable": False,
            "safe_to_retry_after_snapshot_restore": False,
            "message": f"Ferramenta '{name}' não está na allowlist do servidor Fusion.",
            "input": arguments,
        }
    return {
        "ok": True,
        "mcp_server": SERVER_NAME,
        "transport": "stdio",
        "tool_name": name,
        "software": ModelingSoftware.fusion.value,
        "message": (
            "Tool call preparada via servidor MCP stdio do Fusion. "
            "A execução real exige o add-in persistente (PR futuro)."
        ),
        "input": arguments,
        "_meta": meta,
    }


def handle_status() -> dict[str, Any]:
    return {
        "server": SERVER_NAME,
        "connected": False,
        "transport": "stdio",
        "status": "adapter_mock",
        "detail": (
            "Servidor Fusion stdio ativo, mas add-in desktop ainda não conectado; "
            "chamadas retornam mocks auditáveis."
        ),
        "tools": FUSION_TOOLS,
    }


def main() -> int:
    return run_server(
        server_name=SERVER_NAME,
        tools=FUSION_TOOLS,
        handle_tool_call=handle_tool_call,
        handle_status=handle_status,
    )


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    sys.exit(main())
