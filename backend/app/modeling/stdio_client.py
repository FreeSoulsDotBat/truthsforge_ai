"""Persistent stdio JSON-RPC client for the modeling MCP servers.

The client keeps a single subprocess alive per server (blender/fusion), serializes
requests on a lock, and reads back exactly one response per request — matching the
line-delimited JSON-RPC framing implemented in ``mcp_servers/_server_base.py``.

Failure model:

- If the subprocess dies between calls, ``call`` raises :class:`StdioServerError`
  with the captured stderr tail; the caller decides whether to restart.
- ``close()`` is idempotent and is also registered with ``atexit`` so the server
  shuts down with the backend.

This is not a generic MCP SDK — it covers the methods the backend actually uses
today (``tools/list``, ``tools/call``, ``status``, ``shutdown``).
"""

from __future__ import annotations

import atexit
import logging
import os
import subprocess
import sys
import threading
from typing import Any

from app.modeling.mcp_servers.protocol import (
    ProtocolError,
    build_request,
    decode_message,
    encode_message,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 60
STDERR_TAIL_BYTES = 4000
# Janela curta para o filho encerrar antes de drenarmos seu stderr; impede que
# ``stderr.read()`` (que bloqueia até EOF) trave o lock num processo pendurado.
STDERR_DRAIN_TIMEOUT_SECONDS = 5


class StdioServerError(RuntimeError):
    """Raised when the stdio server returns an error envelope or exits unexpectedly."""

    def __init__(self, message: str, *, code: int | None = None, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data


class StdioMCPClient:
    """Owns a persistent subprocess and exposes synchronous ``call`` semantics."""

    def __init__(
        self,
        command: list[str],
        *,
        name: str = "mcp",
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        env: dict[str, str] | None = None,
    ) -> None:
        self.command = list(command)
        self.name = name
        self.timeout_seconds = timeout_seconds
        self.env = env
        self._lock = threading.Lock()
        self._proc: subprocess.Popen[str] | None = None
        self._next_id = 0
        self._closed = False
        atexit.register(self.close)

    # ------------------------------------------------------------------ lifecycle

    def start(self) -> None:
        """Spawn the subprocess if it is not already running."""
        with self._lock:
            self._ensure_started_locked()

    def _ensure_started_locked(self) -> None:
        if self._closed:
            raise StdioServerError(f"Cliente stdio '{self.name}' já foi fechado.")
        if self._proc and self._proc.poll() is None:
            return
        logger.info("Iniciando servidor MCP stdio '%s' (%s).", self.name, self.command)
        # Force UTF-8 across the wire on Windows hosts whose console default is
        # cp1252; without this the child's print statements come back with
        # mojibake and ``readline()`` raises UnicodeDecodeError.
        child_env = {**os.environ, **(self.env or {})}
        child_env.setdefault("PYTHONIOENCODING", "utf-8")
        child_env.setdefault("PYTHONUTF8", "1")
        self._proc = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
            env=child_env,
        )

    def close(self) -> None:
        """Best-effort graceful shutdown; never raises."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            proc = self._proc
            self._proc = None
        if proc is None:
            return
        try:
            if proc.stdin and not proc.stdin.closed:
                try:
                    proc.stdin.write(encode_message(build_request("__shutdown", "shutdown")))
                    proc.stdin.flush()
                except (BrokenPipeError, OSError):
                    pass
                try:
                    proc.stdin.close()
                except OSError:
                    pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        except Exception:  # pragma: no cover - never propagate from close
            logger.exception("Falha ao encerrar servidor MCP stdio '%s'.", self.name)

    # --------------------------------------------------------------------- calls

    def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Send a request, wait for the matching response, and return ``result``."""
        with self._lock:
            self._ensure_started_locked()
            assert self._proc is not None and self._proc.stdin and self._proc.stdout
            self._next_id += 1
            request_id = f"{self.name}-{self._next_id}"
            request = build_request(request_id, method, params)
            try:
                self._proc.stdin.write(encode_message(request))
                self._proc.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                raise self._build_dead_process_error(exc) from exc

            # O framing JSON-RPC é uma linha por mensagem, sem comprimento. Linhas
            # de log/print espúrias emitidas ao stdout do servidor (ou por libs que
            # ele importa) desincronizariam o protocolo se tratássemos a primeira
            # linha como resposta. Por isso lemos em loop, ignorando linhas que não
            # decodificam ou cujo id não bate, até achar a resposta correta ou EOF.
            response: dict[str, Any] | None = None
            while True:
                line = self._proc.stdout.readline()
                if not line:
                    raise self._build_dead_process_error(
                        RuntimeError("EOF inesperado no stdout.")
                    )
                if not line.strip():
                    continue
                try:
                    candidate = decode_message(line)
                except ProtocolError as exc:
                    logger.debug(
                        "Servidor '%s' emitiu linha não-JSON-RPC no stdout (ignorada): %s",
                        self.name,
                        exc,
                    )
                    continue
                if candidate.get("id") != request_id:
                    logger.debug(
                        "Servidor '%s' emitiu mensagem com id divergente (ignorada): "
                        "esperado %s, recebido %r.",
                        self.name,
                        request_id,
                        candidate.get("id"),
                    )
                    continue
                response = candidate
                break
        if "error" in response:
            error = response["error"] or {}
            raise StdioServerError(
                str(error.get("message") or "Erro desconhecido."),
                code=error.get("code"),
                data=error.get("data"),
            )
        return response.get("result")

    def tools_list(self) -> dict[str, Any]:
        return self.call("tools/list")

    def tool_call(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": name, "arguments": arguments or {}}
        if meta:
            payload["_meta"] = meta
        return self.call("tools/call", payload)

    def status(self) -> dict[str, Any]:
        return self.call("status")

    # ----------------------------------------------------------------- internals

    def _build_dead_process_error(self, original: Exception) -> StdioServerError:
        stderr_tail = ""
        if self._proc and self._proc.stderr:
            # ``stderr.read()`` (sem tamanho) bloqueia até EOF, e um stdout vazio NÃO
            # garante que o filho saiu (ele pode ter fechado/half-closed o stdout e
            # continuar vivo ou travado). Confirmamos que o processo realmente morreu
            # — concedendo uma janela curta para encerrar — antes de drenar o stderr,
            # evitando travar o lock indefinidamente num filho pendurado.
            try:
                if self._proc.poll() is None:
                    try:
                        self._proc.wait(timeout=STDERR_DRAIN_TIMEOUT_SECONDS)
                    except subprocess.TimeoutExpired:
                        self._proc.kill()
                        try:
                            self._proc.wait(timeout=STDERR_DRAIN_TIMEOUT_SECONDS)
                        except subprocess.TimeoutExpired:
                            pass
                stderr_tail = self._proc.stderr.read()[-STDERR_TAIL_BYTES:]
            except OSError:
                stderr_tail = ""
        return StdioServerError(
            f"Servidor '{self.name}' não responde: {original}",
            data={"stderr_tail": stderr_tail},
        )


def build_blender_command() -> list[str]:
    return [sys.executable, "-m", "app.modeling.mcp_servers.blender_server"]


def build_fusion_command() -> list[str]:
    return [sys.executable, "-m", "app.modeling.mcp_servers.fusion_server"]
