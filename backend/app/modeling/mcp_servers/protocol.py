"""Line-delimited JSON-RPC 2.0 helpers shared by stdio MCP servers and the client.

The protocol is intentionally a subset of the Model Context Protocol — enough to
expose ``tools/list``, ``tools/call`` and ``status`` over ``stdio``. We do not
chase 100% spec parity here because the same boundary may be replaced by an
upstream MCP SDK later; for now this gives Truth's Forge a deterministic,
testable wire format with zero third-party runtime dependencies.

Frame format: every JSON-RPC message is a single line of JSON terminated by
``\\n``. Implementations MUST NOT emit embedded newlines in the encoded payload.
"""

from __future__ import annotations

import json
from typing import Any, BinaryIO, TextIO

JSONRPC_VERSION = "2.0"

# Error codes follow the JSON-RPC 2.0 specification reserved range.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# Custom application range.
TOOL_NOT_FOUND = -32001
TOOL_EXECUTION_FAILED = -32002


class ProtocolError(Exception):
    """Raised when an inbound message cannot be decoded into a JSON-RPC request."""


def build_request(
    request_id: str | int, method: str, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "id": request_id, "method": method}
    if params is not None:
        payload["params"] = params
    return payload


def build_result(request_id: str | int | None, result: Any) -> dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}


def build_error(
    request_id: str | int | None,
    code: int,
    message: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "error": error}


def encode_message(message: dict[str, Any]) -> str:
    """Serialize a message into a single newline-terminated JSON line."""
    return json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n"


def decode_message(line: str) -> dict[str, Any]:
    """Parse a single inbound line; raises :class:`ProtocolError` on malformed input."""
    stripped = line.strip()
    if not stripped:
        raise ProtocolError("Linha vazia recebida no canal stdio.")
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"JSON inválido: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProtocolError("Mensagem JSON-RPC precisa ser um objeto na raiz.")
    return payload


def read_line_message(stream: TextIO | BinaryIO) -> dict[str, Any] | None:
    """Read the next message from a stream. Returns ``None`` on EOF."""
    line = stream.readline()
    if not line:
        return None
    if isinstance(line, bytes):
        line = line.decode("utf-8")
    return decode_message(line)


def write_message(stream: TextIO | BinaryIO, message: dict[str, Any]) -> None:
    """Write a message and flush the stream so the peer sees it immediately."""
    encoded = encode_message(message)
    if isinstance(stream, (bytes,)):  # pragma: no cover - defensive guard
        raise TypeError("Stream inválido para write_message.")
    written = stream.write(encoded if not _is_binary_stream(stream) else encoded.encode("utf-8"))
    if written is None:
        # Some text streams (rare) return None; ignore.
        pass
    stream.flush()


def _is_binary_stream(stream: TextIO | BinaryIO) -> bool:
    mode = getattr(stream, "mode", "")
    if "b" in mode:
        return True
    return hasattr(stream, "buffer") is False and isinstance(
        getattr(stream, "write", None), type(None)
    )
