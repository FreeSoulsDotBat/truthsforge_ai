"""Testes do servidor MCP standalone (Fase 1 / ADR-017).

Sobe o app ASGI num porta loopback efêmera com uvicorn em thread e exercita o
contrato end-to-end via cliente MCP oficial: handshake (initialize), tools/list
(allowlist de fonte única), tools/call (paridade de envelope) e auth (aceita/
rejeita). Determinístico: o adapter Fusion roda sem MCP da Autodesk (mock).
"""

from __future__ import annotations

import asyncio
import socket
import threading
import time

import httpx
import pytest
import uvicorn

from app.core.contracts import (
    ModelingPlanStep,
    ModelingRiskLevel,
    ModelingSoftware,
    ModelingStepStatus,
)
from app.modeling.fusion_adapter import FUSION_TOOLS as ADAPTER_FUSION_TOOLS
from app.modeling.fusion_adapter import FusionDesktopAdapter
from app.modeling.mcp_standalone.app import create_app
from app.modeling.mcp_standalone.client import StandaloneMCPClient

TOKEN = "test-token-abc123"


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


class _ServerHandle:
    def __init__(self, url: str, token: str, server: uvicorn.Server, thread: threading.Thread):
        self.url = url
        self.token = token
        self._server = server
        self._thread = thread

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=5)


@pytest.fixture
def mcp_server():
    port = _free_port()
    # Adapter sem MCP Autodesk → caminho mock determinístico (sem rede/Fusion).
    adapter = FusionDesktopAdapter(enable_autodesk_mcp=False)
    app = create_app(token=TOKEN, adapter=adapter)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="on")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(250):
        if server.started:
            break
        time.sleep(0.02)
    assert server.started, "uvicorn não subiu a tempo"
    handle = _ServerHandle(f"http://127.0.0.1:{port}/mcp", TOKEN, server, thread)
    try:
        yield handle
    finally:
        handle.stop()


def _step(tool_name: str, **args) -> ModelingPlanStep:
    return ModelingPlanStep(
        seq=1,
        title=tool_name,
        software=ModelingSoftware.fusion,
        tool_name=tool_name,
        risk_level=ModelingRiskLevel.low,
        approval_required=False,
        status=ModelingStepStatus.approved,
        input_json=args,
    )


def test_list_tools_exposes_fusion_allowlist(mcp_server):
    async def _go() -> list[str]:
        from mcp.client.session import ClientSession
        from mcp.client.streamable_http import streamable_http_client
        from mcp.shared._httpx_utils import create_mcp_http_client

        headers = {"Authorization": f"Bearer {mcp_server.token}"}
        async with create_mcp_http_client(headers=headers) as http_client:
            async with streamable_http_client(mcp_server.url, http_client=http_client) as (
                read,
                write,
                _,
            ):
                async with ClientSession(read, write) as session:
                    init = await session.initialize()
                    assert init.serverInfo.name == "truths-forge-modeling-3d"
                    listed = await session.list_tools()
                    return [tool.name for tool in listed.tools]

    names = asyncio.run(_go())
    from app.modeling.mcp_standalone.tools import executable_fusion_tools

    # Paridade list/call real: só tools com handler executável no script são
    # expostas (fusion.relate_bodies é UNRELEASED/expandida pré-dispatch e
    # ficaria inexecutável para um cliente externo).
    assert set(names) == set(executable_fusion_tools())
    assert set(names) <= set(ADAPTER_FUSION_TOOLS)
    assert "fusion.relate_bodies" not in names
    # run_script nunca é exposto (RF-023).
    assert "fusion.run_script" not in names
    # Destrutivas nunca são anunciadas no standalone (sem humano no circuito).
    assert "fusion.delete_body" not in names
    assert "fusion.rollback_timeline" not in names


def test_call_tool_returns_envelope(mcp_server):
    client = StandaloneMCPClient(url=mcp_server.url, token=mcp_server.token)
    envelope = client.execute_step(_step("fusion.open_design"))
    assert envelope["tool_name"] == "fusion.open_design"
    assert envelope["software"] == "fusion"
    assert envelope["transport"] == "mcp_http"
    # Sem Fusion conectado, o servidor devolve envelope mock ok=True.
    assert envelope["ok"] is True


def test_executable_fusion_tools_exclude_destructive_and_high_risk():
    from app.modeling import tool_registry
    from app.modeling.mcp_standalone.tools import executable_fusion_tools

    names = executable_fusion_tools()
    assert "fusion.delete_body" not in names
    assert "fusion.rollback_timeline" not in names
    assert not any(
        tool_registry.is_destructive(name) or tool_registry.is_high_risk(name) for name in names
    )
    # Tools aditivas continuam na superfície executável.
    assert "fusion.add_box" in names
    assert "fusion.create_sketch" in names


def test_execute_fusion_tool_refuses_destructive_directly():
    """Defesa em profundidade: a recusa vale mesmo fora do tools/list."""
    from app.modeling.mcp_standalone.server import execute_fusion_tool

    adapter = FusionDesktopAdapter(enable_autodesk_mcp=False)
    for tool in ("fusion.delete_body", "fusion.rollback_timeline"):
        envelope = execute_fusion_tool(adapter, tool, {"body": "b1"})
        assert envelope["ok"] is False
        assert envelope["error_code"] == "fusion.human_approval_required"
        assert envelope["retryable"] is False
        assert "aprovação humana" in envelope["message"]


def test_call_tool_refuses_destructive_via_mcp(mcp_server):
    """End-to-end: cliente MCP com token válido NÃO executa destrutivo."""
    client = StandaloneMCPClient(url=mcp_server.url, token=mcp_server.token)
    envelope = client.execute_step(_step("fusion.delete_body", body="b1"))
    assert envelope["ok"] is False
    assert envelope["error_code"] == "fusion.human_approval_required"


def test_call_tool_rejects_non_allowlisted(mcp_server):
    client = StandaloneMCPClient(url=mcp_server.url, token=mcp_server.token)
    envelope = client.execute_step(_step("fusion.run_script", script="evil"))
    assert envelope["ok"] is False
    assert envelope["error_code"] == "fusion.tool_not_allowlisted"


def test_auth_rejects_wrong_token(mcp_server):
    client = StandaloneMCPClient(url=mcp_server.url, token="wrong-token")
    envelope = client.execute_step(_step("fusion.open_design"))
    assert envelope["ok"] is False
    assert envelope["error_code"] == "mcp.standalone_unreachable"


class _FakeStandalone:
    def __init__(self):
        self.calls: list[str] = []

    def execute_step(self, step, *, plan_id=None, project_id=None):
        self.calls.append(step.tool_name)
        return {
            "ok": True,
            "transport": "mcp_http",
            "tool_name": step.tool_name,
            "software": step.software.value,
            "input": step.input_json,
        }


def test_local_client_routes_fusion_via_mcp_http():
    from app.modeling.mcp_client import LocalMCPClient

    fake = _FakeStandalone()
    client = LocalMCPClient(
        transport_mode="mcp_http",
        standalone_client=fake,
        fusion_adapter=FusionDesktopAdapter(enable_autodesk_mcp=False),
    )

    # fusion.* é roteado para o servidor standalone.
    env = client.execute_step(_step("fusion.open_design"))
    assert env["transport"] == "mcp_http"
    assert fake.calls == ["fusion.open_design"]
    assert client.transport(ModelingSoftware.fusion) == "mcp_http"

    # project_store.* permanece in-process (não toca o standalone).
    internal = ModelingPlanStep(
        seq=1,
        title="snap",
        software=ModelingSoftware.fusion,
        tool_name="project_store.create_snapshot",
        risk_level=ModelingRiskLevel.high,
        approval_required=True,
        status=ModelingStepStatus.approved,
        input_json={},
    )
    client.execute_step(internal)
    assert fake.calls == ["fusion.open_design"]  # inalterado


# ------------------------------------------------------------ auth: token em disco


def _patch_auth_settings(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from app.modeling.mcp_standalone import auth

    monkeypatch.setattr(
        auth,
        "settings",
        SimpleNamespace(modeling_mcp_server_token="", modeling_dir=tmp_path),
    )
    return auth


def test_auth_new_token_created_with_o_excl_and_mode_600(monkeypatch, tmp_path):
    import os

    auth = _patch_auth_settings(monkeypatch, tmp_path)
    opens: list[tuple[int, int]] = []
    real_open = os.open

    def tracking_open(path, flags, mode=0o777, **kwargs):
        opens.append((flags, mode))
        return real_open(path, flags, mode, **kwargs)

    monkeypatch.setattr(auth.os, "open", tracking_open)

    token = auth.load_or_create_token()
    assert token
    assert (tmp_path / auth.TOKEN_FILENAME).read_text(encoding="utf-8").strip() == token
    flags, mode = opens[0]
    assert flags & os.O_CREAT and flags & os.O_EXCL
    assert mode == 0o600


def test_auth_existing_token_is_reused(monkeypatch, tmp_path):
    auth = _patch_auth_settings(monkeypatch, tmp_path)
    (tmp_path / auth.TOKEN_FILENAME).write_text("tok-existente\n", encoding="utf-8")
    assert auth.load_or_create_token() == "tok-existente"


def test_auth_empty_token_file_restricts_perms_before_writing(monkeypatch, tmp_path):
    """Ramo FileExistsError + arquivo vazio: chmod 0o600 ANTES de gravar o segredo,
    sem janela world-readable entre write e chmod (POSIX)."""
    import os
    from pathlib import Path

    auth = _patch_auth_settings(monkeypatch, tmp_path)
    token_file = tmp_path / auth.TOKEN_FILENAME
    token_file.write_text("", encoding="utf-8")

    events: list[tuple[str, int]] = []
    real_open = os.open

    def tracking_open(path, flags, mode=0o777, **kwargs):
        events.append(("open", flags))
        return real_open(path, flags, mode, **kwargs)

    real_chmod = Path.chmod

    def tracking_chmod(self, mode, **kwargs):
        events.append(("chmod", mode))
        return real_chmod(self, mode, **kwargs)

    monkeypatch.setattr(auth.os, "open", tracking_open)
    monkeypatch.setattr(Path, "chmod", tracking_chmod)

    token = auth.load_or_create_token()
    assert token
    assert token_file.read_text(encoding="utf-8").strip() == token

    # A primeira abertura (O_EXCL) falha porque o arquivo já existe; o ramo de
    # recuperação precisa restringir a permissão antes de abrir para gravação.
    trunc_idx = next(
        i for i, (kind, value) in enumerate(events) if kind == "open" and value & os.O_TRUNC
    )
    chmod_idx = next(
        i for i, (kind, value) in enumerate(events) if kind == "chmod" and value == 0o600
    )
    assert chmod_idx < trunc_idx, "chmod(0o600) deve preceder a gravação do token"
    # E nenhuma gravação ocorre via caminho permissivo (sem O_TRUNC nem O_EXCL).
    write_opens = [
        value for kind, value in events if kind == "open" and value & (os.O_WRONLY | os.O_RDWR)
    ]
    assert all(value & (os.O_TRUNC | os.O_EXCL) for value in write_opens)


def test_auth_rejects_missing_token(mcp_server):
    async def _go() -> int:
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                mcp_server.url,
                json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                headers={
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json",
                },
            )
            return resp.status_code

    assert asyncio.run(_go()) == 401
