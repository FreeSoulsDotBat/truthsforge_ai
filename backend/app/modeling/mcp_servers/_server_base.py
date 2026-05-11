"""Shared scaffolding for stdio MCP servers.

Each concrete server only needs to declare its tool list and provide a
``handle_tool_call`` callable. The base loop handles framing, dispatch,
error envelopes and shutdown.
"""

from __future__ import annotations

import logging
import sys
import traceback
from collections.abc import Callable
from typing import Any

from app.modeling.mcp_servers.protocol import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    ProtocolError,
    build_error,
    build_result,
    decode_message,
    write_message,
)

logger = logging.getLogger(__name__)

ToolCallHandler = Callable[[str, dict[str, Any], dict[str, Any]], dict[str, Any]]
StatusHandler = Callable[[], dict[str, Any]]


def run_server(
    *,
    server_name: str,
    tools: list[str],
    handle_tool_call: ToolCallHandler,
    handle_status: StatusHandler | None = None,
    stdin: Any | None = None,
    stdout: Any | None = None,
) -> int:
    """Drive the JSON-RPC loop until stdin is closed.

    Returns the process exit code (0 = clean shutdown, 1 = unrecoverable error).
    """
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout

    for line in iter(stdin.readline, ""):
        if not line.strip():
            continue
        request_id: str | int | None = None
        try:
            request = decode_message(line)
        except ProtocolError as exc:
            write_message(stdout, build_error(None, PARSE_ERROR, str(exc)))
            continue

        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}
        if not isinstance(params, dict):
            write_message(
                stdout,
                build_error(request_id, INVALID_PARAMS, "params precisa ser um objeto."),
            )
            continue

        try:
            if method == "tools/list":
                response = build_result(request_id, {"server": server_name, "tools": tools})
            elif method == "tools/call":
                name = str(params.get("name") or "")
                arguments = params.get("arguments") or {}
                meta = params.get("_meta") or {}
                if not isinstance(arguments, dict) or not isinstance(meta, dict):
                    response = build_error(
                        request_id,
                        INVALID_PARAMS,
                        "arguments e _meta precisam ser objetos.",
                    )
                elif not name:
                    response = build_error(
                        request_id, INVALID_PARAMS, "name é obrigatório em tools/call."
                    )
                else:
                    result = handle_tool_call(name, arguments, meta)
                    response = build_result(request_id, result)
            elif method == "status":
                if handle_status is None:
                    response = build_result(request_id, {"server": server_name})
                else:
                    response = build_result(request_id, handle_status())
            elif method == "shutdown":
                write_message(stdout, build_result(request_id, {"ok": True}))
                return 0
            else:
                response = build_error(
                    request_id, METHOD_NOT_FOUND, f"Método não suportado: {method}"
                )
        except Exception as exc:  # noqa: BLE001 - serialize anything that explodes
            logger.exception("Erro ao executar método %s no servidor %s", method, server_name)
            response = build_error(
                request_id,
                INTERNAL_ERROR,
                str(exc) or "Erro interno no servidor MCP.",
                data={"traceback_tail": traceback.format_exc()[-2000:]},
            )

        write_message(stdout, response)

    return 0


def invalid_request(stdout: Any, request_id: str | int | None, message: str) -> None:
    """Convenience helper for tests."""
    write_message(stdout, build_error(request_id, INVALID_REQUEST, message))
