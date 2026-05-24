"""Cliente do servidor MCP standalone (wrapper síncrono do SDK oficial).

O executor do backend é síncrono; este cliente expõe ``execute_step`` síncrono
que abre uma sessão MCP (HTTP streamable + Bearer), chama a tool e reconstrói o
envelope-padrão a partir do ``structuredContent`` da resposta. Falhas de
transporte viram envelope de erro (não estouram para o executor).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from app.core.config import settings
from app.core.contracts import ModelingPlanStep
from app.modeling.mcp_standalone.auth import load_or_create_token
from app.modeling.mcp_standalone.server import SERVER_NAME

logger = logging.getLogger(__name__)


class StandaloneMCPClient:
    def __init__(self, *, url: str | None = None, token: str | None = None) -> None:
        self.url = url or settings.modeling_mcp_server_url
        self._token = token

    def _resolve_token(self) -> str:
        if not self._token:
            self._token = load_or_create_token()
        return self._token

    async def _call_async(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        # Imports tardios: o SDK só é necessário neste caminho.
        from mcp.client.session import ClientSession
        from mcp.client.streamable_http import streamable_http_client
        from mcp.shared._httpx_utils import create_mcp_http_client

        headers = {"Authorization": f"Bearer {self._resolve_token()}"}
        # ``create_mcp_http_client`` monta o httpx.AsyncClient com os defaults
        # exigidos pelo transport streamable (Accept/Content-Type), somando o
        # header de auth.
        async with create_mcp_http_client(headers=headers) as http_client:
            async with streamable_http_client(self.url, http_client=http_client) as (
                read,
                write,
                _sid,
            ):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(name, arguments)
                    return _envelope_from_result(result, name, arguments)

    def execute_step(
        self,
        step: ModelingPlanStep,
        *,
        plan_id: str | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            return _run_sync(self._call_async(step.tool_name, dict(step.input_json)))
        except Exception as exc:  # noqa: BLE001 - transporte/conexão → envelope de erro
            logger.error(
                "Servidor MCP standalone inacessível para '%s': %s",
                step.tool_name,
                exc,
                exc_info=True,
            )
            return {
                "ok": False,
                "mcp_server": SERVER_NAME,
                "transport": "mcp_http",
                "tool_name": step.tool_name,
                "software": step.software.value,
                "error_code": "mcp.standalone_unreachable",
                "retryable": True,
                "safe_to_retry_after_snapshot_restore": False,
                "message": str(exc),
                "input": step.input_json,
            }


def _envelope_from_result(result: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict) and structured:
        return structured

    # Fallback: tenta parsear o primeiro bloco de texto como JSON.
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if not text:
            continue
        try:
            parsed = json.loads(text)
        except (ValueError, TypeError):
            continue
        if isinstance(parsed, dict):
            return parsed

    return {
        "ok": not getattr(result, "isError", False),
        "mcp_server": SERVER_NAME,
        "transport": "mcp_http",
        "tool_name": name,
        "message": "Resposta MCP sem structuredContent reconhecível.",
        "input": arguments,
    }


def _run_sync(coro: Any) -> Any:
    """Executa uma corrotina a partir de contexto síncrono (executor)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Caso raro: já dentro de um loop → roda em thread isolada.
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(coro)).result()
