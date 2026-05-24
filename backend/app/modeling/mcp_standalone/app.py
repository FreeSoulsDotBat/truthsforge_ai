"""App ASGI do servidor MCP standalone: HTTP streamable + auth Bearer.

Monta o ``StreamableHTTPSessionManager`` (SDK oficial) sob ``/mcp`` e protege
todo o app com um middleware ASGI **puro** de token. Usa-se ASGI cru (e não
``BaseHTTPMiddleware``) de propósito: este último bufferiza o corpo da resposta
e quebraria o streaming SSE do transport MCP.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import AsyncIterator

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import JSONResponse
from starlette.routing import Mount
from starlette.types import ASGIApp, Receive, Scope, Send

from app.modeling.fusion_adapter import FusionDesktopAdapter
from app.modeling.mcp_standalone.auth import verify_token
from app.modeling.mcp_standalone.server import build_server

logger = logging.getLogger(__name__)


class TokenAuthMiddleware:
    """Exige ``Authorization: Bearer <token>`` em toda requisição HTTP."""

    def __init__(self, app: ASGIApp, *, token: str) -> None:
        self.app = app
        self.token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        raw = headers.get(b"authorization", b"").decode("latin-1")
        provided = raw[7:].strip() if raw[:7].lower() == "bearer " else None
        if not verify_token(provided, self.token):
            response = JSONResponse({"error": "unauthorized"}, status_code=401)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


def create_app(
    *,
    token: str,
    adapter: FusionDesktopAdapter | None = None,
    json_response: bool = False,
) -> Starlette:
    server = build_server(adapter)
    session_manager = StreamableHTTPSessionManager(
        app=server, json_response=json_response, stateless=False
    )

    async def handle_mcp(scope: Scope, receive: Receive, send: Send) -> None:
        await session_manager.handle_request(scope, receive, send)

    @contextlib.asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            logger.info("Servidor MCP standalone pronto (transport HTTP streamable).")
            yield

    return Starlette(
        debug=False,
        routes=[Mount("/mcp", app=handle_mcp)],
        middleware=[Middleware(TokenAuthMiddleware, token=token)],
        lifespan=lifespan,
    )
