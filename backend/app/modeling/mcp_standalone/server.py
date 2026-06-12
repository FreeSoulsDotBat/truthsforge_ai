"""Servidor MCP low-level (SDK oficial) que expõe as tools Fusion.

Registra ``tools/list`` e ``tools/call`` dinamicamente a partir da allowlist de
fonte única e delega a execução ao ``FusionDesktopAdapter`` (executor real:
Autodesk Fusion MCP Server via HTTP / add-in loopback / mock). O envelope de
resposta atual é devolvido como ``structuredContent`` do MCP, preservando o
contrato consumido pelo executor do backend.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import anyio
import mcp.types as types
from mcp.server.lowlevel import Server

from app.core.contracts import (
    ModelingPlanStep,
    ModelingRiskLevel,
    ModelingSoftware,
    ModelingStepStatus,
)
from app.modeling.fusion_adapter import FUSION_TOOLS, FusionDesktopAdapter
from app.modeling.mcp_standalone.tools import build_fusion_tools
from app.modeling.tool_registry import is_destructive, is_high_risk

logger = logging.getLogger(__name__)

SERVER_NAME = "truths-forge-modeling-3d"
SERVER_VERSION = "0.1.0"
SERVER_INSTRUCTIONS = (
    "Servidor MCP local-first de modelagem 3D no Autodesk Fusion 360. "
    "Use tools/list para descobrir as ferramentas allowlistadas e tools/call "
    "para executá-las. Execução real exige o Fusion conectado na máquina do dono."
)


def _build_step(name: str, arguments: dict[str, Any]) -> ModelingPlanStep:
    return ModelingPlanStep(
        seq=1,
        title=name,
        software=ModelingSoftware.fusion,
        tool_name=name,
        risk_level=ModelingRiskLevel.low,
        approval_required=False,
        status=ModelingStepStatus.approved,
        input_json=dict(arguments),
    )


def execute_fusion_tool(
    adapter: FusionDesktopAdapter, name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Executa uma tool Fusion allowlistada e devolve o envelope-padrão."""
    if name not in FUSION_TOOLS:
        return {
            "ok": False,
            "mcp_server": SERVER_NAME,
            "transport": "mcp_http",
            "tool_name": name,
            "software": ModelingSoftware.fusion.value,
            "error_code": "fusion.tool_not_allowlisted",
            "retryable": False,
            "safe_to_retry_after_snapshot_restore": False,
            "message": f"Ferramenta '{name}' não está na allowlist do servidor MCP.",
            "input": arguments,
        }
    # Defesa em profundidade (constituição: human-in-the-loop para ações
    # destrutivas): o servidor standalone não tem humano no circuito, então
    # tools destrutivas/high-risk são recusadas aqui MESMO que algum caminho
    # as anuncie — o gate de aprovação vive no orchestrator/service do
    # backend. Predicados vêm do tool_registry (fonte única, sem duplicação).
    if is_destructive(name) or is_high_risk(name):
        return {
            "ok": False,
            "mcp_server": SERVER_NAME,
            "transport": "mcp_http",
            "tool_name": name,
            "software": ModelingSoftware.fusion.value,
            "error_code": "fusion.human_approval_required",
            "retryable": False,
            "safe_to_retry_after_snapshot_restore": False,
            "message": (
                f"Ferramenta '{name}' é destrutiva ou de alto risco e exige "
                "aprovação humana. O servidor MCP standalone não possui gate de "
                "aprovação; execute esta ação pelo fluxo supervisionado do "
                "backend (orchestrator/service), que aplica o human-in-the-loop."
            ),
            "input": arguments,
        }
    if not adapter.is_available():
        return {
            "ok": True,
            "mcp_server": SERVER_NAME,
            "transport": "mcp_http",
            "tool_name": name,
            "software": ModelingSoftware.fusion.value,
            "message": (
                "Tool call preparada via servidor MCP standalone. "
                "Fusion desktop ainda não conectado; chamadas ficam em mock."
            ),
            "input": arguments,
        }
    return adapter.execute(_build_step(name, arguments))


def build_server(adapter: FusionDesktopAdapter | None = None) -> Server:
    adapter = adapter or FusionDesktopAdapter()
    server: Server = Server(SERVER_NAME, version=SERVER_VERSION, instructions=SERVER_INSTRUCTIONS)
    fusion_tools = build_fusion_tools()

    @server.list_tools()
    async def _list_tools() -> list[Any]:
        return fusion_tools

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any]) -> types.CallToolResult:
        # ``adapter.execute`` é síncrono e pode bloquear em I/O (HTTP/socket).
        # Roda em thread para não travar o event loop do servidor.
        envelope = await anyio.to_thread.run_sync(execute_fusion_tool, adapter, name, arguments)
        # Deriva ``isError`` do envelope para que clientes MCP genéricos
        # interpretem falhas do Fusion como erro; mantém o envelope completo
        # em ``structuredContent`` (contrato consumido pelo executor interno).
        is_error = envelope.get("ok") is False
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(envelope))],
            structuredContent=envelope,
            isError=is_error,
        )

    return server
