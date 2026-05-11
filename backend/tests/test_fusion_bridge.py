"""Tests for the Fusion 360 loopback bridge.

The real add-in only runs inside Fusion 360, so these tests stand up a tiny
in-memory TCP server that mimics the add-in's JSON-RPC contract (auth +
tools/list + tools/call + status) and verify the backend adapter against it.
"""

from __future__ import annotations

import json
import secrets
import socket
import socketserver
import threading
from pathlib import Path
from typing import Any

import pytest

from app.core.contracts import (
    ModelingPlanStep,
    ModelingRiskLevel,
    ModelingSoftware,
    ModelingStepStatus,
)
from app.modeling.fusion_adapter import (
    FUSION_TOOLS,
    FusionBridgeError,
    FusionDesktopAdapter,
)
from app.modeling.mcp_servers.protocol import (
    build_error,
    build_result,
    decode_message,
    encode_message,
)

# ----------------------------------------------------------------- fake add-in


class _FakeAddinHandler(socketserver.StreamRequestHandler):
    """Mimics the add-in's wire contract exactly enough for adapter tests."""

    timeout = 5

    def handle(self) -> None:  # type: ignore[override]
        server: _FakeAddinServer = self.server  # type: ignore[assignment]
        authenticated = False
        while True:
            raw = self.rfile.readline()
            if not raw:
                return
            try:
                message = decode_message(raw.decode("utf-8"))
            except Exception:
                self._send(build_error(None, -32700, "parse"))
                continue
            request_id = message.get("id")
            method = message.get("method")
            params = message.get("params") or {}
            if method == "auth":
                token = params.get("token") if isinstance(params, dict) else None
                if token != server.expected_token:
                    self._send(build_error(request_id, -32001, "Token inválido."))
                    return
                authenticated = True
                self._send(build_result(request_id, {"ok": True}))
                continue
            if not authenticated:
                self._send(build_error(request_id, -32001, "Auth obrigatória."))
                return
            handler = server.handlers.get(method)
            if handler is None:
                self._send(build_error(request_id, -32601, f"Método não suportado: {method}"))
                continue
            try:
                result = handler(params)
                self._send(build_result(request_id, result))
            except Exception as exc:  # noqa: BLE001
                self._send(build_error(request_id, -32603, str(exc)))

    def _send(self, message: dict[str, Any]) -> None:
        try:
            self.wfile.write(encode_message(message).encode("utf-8"))
            self.wfile.flush()
        except OSError:
            pass


class _FakeAddinServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, expected_token: str, handlers: dict[str, Any]) -> None:
        super().__init__(("127.0.0.1", 0), _FakeAddinHandler)
        self.expected_token = expected_token
        self.handlers = handlers


def _spawn_fake_addin(
    handlers: dict[str, Any],
    *,
    token: str | None = None,
) -> tuple[_FakeAddinServer, str, int]:
    token = token or secrets.token_urlsafe(16)
    server = _FakeAddinServer(token, handlers)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, token, port


def _write_discovery(tmp_path: Path, port: int, token: str) -> Path:
    path = tmp_path / "fusion-bridge.json"
    path.write_text(
        json.dumps({"host": "127.0.0.1", "port": port, "token": token, "pid": 1234}),
        encoding="utf-8",
    )
    return path


def _step(tool_name: str = "fusion.create_sketch") -> ModelingPlanStep:
    return ModelingPlanStep(
        seq=1,
        title="t",
        software=ModelingSoftware.fusion,
        tool_name=tool_name,
        risk_level=ModelingRiskLevel.low,
        approval_required=False,
        status=ModelingStepStatus.approved,
        input_json={"plane_ref": "xy"},
    )


# --------------------------------------------------------------------- tests


def test_adapter_status_reports_unconnected_when_discovery_missing(tmp_path) -> None:
    adapter = FusionDesktopAdapter(discovery_path=tmp_path / "nope.json")
    status = adapter.status()
    assert status.connected is False
    assert status.transport == "mock"
    assert status.status == "adapter_mock"
    assert "Add-in" in status.detail


def test_adapter_status_reports_offline_when_port_refused(tmp_path) -> None:
    # Discovery points to a port that nothing is listening on.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        free_port = sock.getsockname()[1]
    discovery = _write_discovery(tmp_path, free_port, "any-token")
    adapter = FusionDesktopAdapter(discovery_path=discovery, timeout_seconds=2.0)
    status = adapter.status()
    assert status.connected is False
    assert status.status == "adapter_offline"


def test_adapter_status_connects_to_fake_addin(tmp_path) -> None:
    def status_handler(_params: dict[str, Any]) -> dict[str, Any]:
        return {"server": "fusion_mcp", "connected": True, "tools": list(FUSION_TOOLS)}

    server, token, port = _spawn_fake_addin({"status": status_handler})
    try:
        discovery = _write_discovery(tmp_path, port, token)
        adapter = FusionDesktopAdapter(discovery_path=discovery, timeout_seconds=2.0)
        status = adapter.status()
        assert status.connected is True
        assert status.transport == "loopback"
        assert status.addin_pid == 1234
    finally:
        server.shutdown()
        server.server_close()


def test_adapter_status_refuses_bad_token(tmp_path) -> None:
    server, token, port = _spawn_fake_addin({"status": lambda _params: {}})
    try:
        # Write discovery with a *different* token to simulate stale/forged file.
        discovery = _write_discovery(tmp_path, port, token + "_tampered")
        adapter = FusionDesktopAdapter(discovery_path=discovery, timeout_seconds=2.0)
        status = adapter.status()
        assert status.connected is False
        assert status.status == "adapter_offline"
    finally:
        server.shutdown()
        server.server_close()


def test_adapter_execute_returns_addin_payload(tmp_path) -> None:
    received: list[dict[str, Any]] = []

    def tool_call(params: dict[str, Any]) -> dict[str, Any]:
        received.append(params)
        return {
            "ok": True,
            "mcp_server": "fusion_mcp",
            "transport": "loopback",
            "tool_name": params["name"],
            "software": "fusion",
            "message": "feito",
            "artifact_paths": [],
        }

    def status_handler(_params: dict[str, Any]) -> dict[str, Any]:
        return {}

    server, token, port = _spawn_fake_addin({"tools/call": tool_call, "status": status_handler})
    try:
        discovery = _write_discovery(tmp_path, port, token)
        adapter = FusionDesktopAdapter(discovery_path=discovery, timeout_seconds=5.0)
        out = adapter.execute(_step(), plan_id="plan-1", project_id="prj-1")
        assert out["ok"] is True
        assert out["message"] == "feito"
        assert received and received[0]["name"] == "fusion.create_sketch"
        assert received[0]["_meta"]["plan_id"] == "plan-1"
        assert received[0]["_meta"]["software"] == "fusion"
    finally:
        server.shutdown()
        server.server_close()


def test_adapter_execute_rejects_tool_outside_allowlist(tmp_path) -> None:
    adapter = FusionDesktopAdapter(discovery_path=tmp_path / "nope.json")
    out = adapter.execute(_step("fusion.run_script"))
    assert out["ok"] is False
    assert out["error_code"] == "fusion.tool_not_allowlisted"


def test_adapter_execute_returns_envelope_when_addin_returns_error(tmp_path) -> None:
    def failing_handler(_params: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("simulated execution failure")

    def status_handler(_params: dict[str, Any]) -> dict[str, Any]:
        return {}

    server, token, port = _spawn_fake_addin(
        {"tools/call": failing_handler, "status": status_handler}
    )
    try:
        discovery = _write_discovery(tmp_path, port, token)
        adapter = FusionDesktopAdapter(discovery_path=discovery, timeout_seconds=2.0)
        out = adapter.execute(_step())
        assert out["ok"] is False
        assert out["error_code"] == "fusion.bridge_error"
        assert "simulated execution failure" in out["message"]
        assert out["retryable"] is True
    finally:
        server.shutdown()
        server.server_close()


def test_adapter_handles_malformed_discovery(tmp_path) -> None:
    bad = tmp_path / "fusion-bridge.json"
    bad.write_text("not json", encoding="utf-8")
    adapter = FusionDesktopAdapter(discovery_path=bad)
    assert adapter.is_available() is False
    out = adapter.execute(_step())
    assert out["ok"] is False
    assert out["error_code"] == "fusion.bridge_not_configured"


def test_fusion_bridge_error_carries_code_and_data() -> None:
    err = FusionBridgeError("boom", code=-32001, data={"why": "x"})
    assert err.code == -32001
    assert err.data == {"why": "x"}


def test_local_mcp_client_routes_in_process_fusion_through_adapter(monkeypatch, tmp_path) -> None:
    """When the adapter is available, in_process mode should use it instead of mock."""
    from app.modeling.mcp_client import LocalMCPClient

    def tool_call(params: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": True,
            "mcp_server": "fusion_mcp",
            "transport": "loopback",
            "tool_name": params["name"],
            "software": "fusion",
            "message": "real",
            "artifact_paths": [],
        }

    server, token, port = _spawn_fake_addin({"tools/call": tool_call, "status": lambda _params: {}})
    try:
        discovery = _write_discovery(tmp_path, port, token)
        adapter = FusionDesktopAdapter(discovery_path=discovery, timeout_seconds=5.0)
        client = LocalMCPClient(transport_mode="in_process", fusion_adapter=adapter)
        out = client.execute_step(_step(), plan_id="p", project_id="prj")
        assert out["transport"] == "loopback"
        assert out["message"] == "real"
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture(autouse=True)
def _close_lingering_sockets():
    # Defensive: ensure tests don't leave loopback ports open across the suite.
    yield


def test_adapter_host_override_via_env(monkeypatch, tmp_path) -> None:
    discovery = _write_discovery(tmp_path, 65000, "tok")
    monkeypatch.setenv("TRUTHS_FORGE_FUSION_BRIDGE_HOST", "host.docker.internal")
    adapter = FusionDesktopAdapter(discovery_path=discovery)
    parsed = adapter._read_discovery()  # type: ignore[attr-defined]
    assert parsed is not None
    assert parsed.host == "host.docker.internal"


def test_adapter_host_override_via_constructor_takes_precedence(monkeypatch, tmp_path) -> None:
    discovery = _write_discovery(tmp_path, 65000, "tok")
    monkeypatch.setenv("TRUTHS_FORGE_FUSION_BRIDGE_HOST", "ignored.example.com")
    adapter = FusionDesktopAdapter(discovery_path=discovery, host_override="explicit.host")
    parsed = adapter._read_discovery()  # type: ignore[attr-defined]
    assert parsed is not None
    assert parsed.host == "explicit.host"


def test_adapter_status_uses_cache_within_ttl(tmp_path) -> None:
    probe_count = {"n": 0}

    def status_handler(_params: dict[str, Any]) -> dict[str, Any]:
        probe_count["n"] += 1
        return {}

    server, token, port = _spawn_fake_addin({"status": status_handler})
    try:
        discovery = _write_discovery(tmp_path, port, token)
        adapter = FusionDesktopAdapter(
            discovery_path=discovery,
            timeout_seconds=2.0,
            status_cache_seconds=10.0,
        )
        first = adapter.status()
        second = adapter.status()
        assert first.connected is True
        assert second.connected is True
        assert probe_count["n"] == 1
        adapter.invalidate_status_cache()
        adapter.status()
        assert probe_count["n"] == 2
    finally:
        server.shutdown()
        server.server_close()


def test_adapter_records_consecutive_failures_and_enters_backoff(tmp_path) -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        dead_port = sock.getsockname()[1]
    discovery = _write_discovery(tmp_path, dead_port, "tok")
    adapter = FusionDesktopAdapter(
        discovery_path=discovery,
        timeout_seconds=0.5,
        status_cache_seconds=0.0,
    )
    statuses = [adapter.status() for _ in range(adapter.BACKOFF_THRESHOLD)]
    assert all(s.status == "adapter_offline" for s in statuses)
    assert statuses[-1].consecutive_failures == adapter.BACKOFF_THRESHOLD
    backoff_status = adapter.status()
    assert backoff_status.status == "adapter_backoff"
    assert backoff_status.consecutive_failures >= adapter.BACKOFF_THRESHOLD


def test_adapter_recovers_after_addin_restart(tmp_path) -> None:
    server, token, port = _spawn_fake_addin({"status": lambda _params: {}})
    try:
        discovery = _write_discovery(tmp_path, port, token)
        adapter = FusionDesktopAdapter(
            discovery_path=discovery,
            timeout_seconds=2.0,
            status_cache_seconds=0.0,
        )
        adapter._record_failure("simulated outage 1")  # type: ignore[attr-defined]
        adapter._record_failure("simulated outage 2")  # type: ignore[attr-defined]
        status = adapter.status()
        assert status.connected is True
        assert status.consecutive_failures == 0
        assert status.last_error_at is None
        assert status.last_error_message is None
    finally:
        server.shutdown()
        server.server_close()


def test_adapter_execute_failure_invalidates_status_cache(tmp_path) -> None:
    import time as _time

    from app.modeling.fusion_adapter import FusionAdapterStatus

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        dead_port = sock.getsockname()[1]
    discovery = _write_discovery(tmp_path, dead_port, "tok")
    adapter = FusionDesktopAdapter(
        discovery_path=discovery,
        timeout_seconds=0.5,
        status_cache_seconds=999.0,
    )
    # Forge a "stale connected" cached status so we can prove invalidate_status_cache
    # really kicks in when execute() fails.
    adapter._cached_status = FusionAdapterStatus(  # type: ignore[attr-defined]
        connected=True,
        transport="loopback",
        status="available",
        detail="forjado",
        discovery_path=str(discovery),
        addin_pid=999,
    )
    adapter._cached_status_expires_at = _time.monotonic() + 999  # type: ignore[attr-defined]

    out = adapter.execute(_step())
    assert out["ok"] is False
    assert out["error_code"] == "fusion.bridge_error"

    status = adapter.status()
    assert status.connected is False
    assert status.consecutive_failures >= 1
