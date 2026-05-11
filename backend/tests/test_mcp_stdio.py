"""Tests for the stdio JSON-RPC transport.

Three layers:
- protocol helpers (pure functions, no I/O)
- server loop driven through in-memory StringIO streams
- LocalMCPClient dispatching through a fake StdioMCPClient
"""

from __future__ import annotations

import io
import sys
from typing import Any

import pytest

from app.core.contracts import (
    ModelingPlanStep,
    ModelingRiskLevel,
    ModelingSoftware,
    ModelingStepStatus,
)
from app.modeling.mcp_client import LocalMCPClient
from app.modeling.mcp_servers import blender_server, fusion_server
from app.modeling.mcp_servers._server_base import run_server
from app.modeling.mcp_servers.protocol import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    build_error,
    build_request,
    build_result,
    decode_message,
    encode_message,
)
from app.modeling.stdio_client import StdioMCPClient, StdioServerError

# ----------------------------------------------------------------------- protocol


def test_protocol_request_result_error_round_trip() -> None:
    req = build_request("1", "tools/list")
    line = encode_message(req)
    assert line.endswith("\n")
    decoded = decode_message(line)
    assert decoded == req

    result_line = encode_message(build_result("1", {"server": "x", "tools": []}))
    assert decode_message(result_line)["result"]["server"] == "x"

    error_line = encode_message(build_error("1", PARSE_ERROR, "boom", data={"k": 1}))
    decoded_err = decode_message(error_line)
    assert decoded_err["error"]["code"] == PARSE_ERROR
    assert decoded_err["error"]["data"] == {"k": 1}


def test_protocol_decode_rejects_invalid_payloads() -> None:
    from app.modeling.mcp_servers.protocol import ProtocolError

    with pytest.raises(ProtocolError):
        decode_message("")
    with pytest.raises(ProtocolError):
        decode_message("not json\n")
    with pytest.raises(ProtocolError):
        decode_message("[1, 2, 3]\n")


# ------------------------------------------------------------------- server loop


def _drive_server(input_lines: list[str], handler, tools: list[str]) -> list[dict[str, Any]]:
    stdin = io.StringIO("".join(input_lines))
    stdout = io.StringIO()
    run_server(
        server_name="test_server",
        tools=tools,
        handle_tool_call=handler,
        stdin=stdin,
        stdout=stdout,
    )
    raw_lines = [line for line in stdout.getvalue().splitlines() if line.strip()]
    return [decode_message(line + "\n") for line in raw_lines]


def test_server_tools_list_returns_declared_tools() -> None:
    def handler(name: str, arguments: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("tools/list should not call the tool handler")

    request = encode_message(build_request("a", "tools/list"))
    responses = _drive_server([request], handler, ["x.foo", "x.bar"])
    assert len(responses) == 1
    assert responses[0]["id"] == "a"
    assert responses[0]["result"] == {"server": "test_server", "tools": ["x.foo", "x.bar"]}


def test_server_unknown_method_returns_method_not_found() -> None:
    def handler(name: str, arguments: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    request = encode_message(build_request("b", "tools/lol"))
    responses = _drive_server([request], handler, [])
    assert responses[0]["error"]["code"] == METHOD_NOT_FOUND


def test_server_invalid_params_rejected() -> None:
    def handler(name: str, arguments: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    request = encode_message(build_request("c", "tools/call", params={"name": "x.foo"}))
    bad_args = encode_message(
        build_request(
            "d", "tools/call", params={"name": "x.foo", "arguments": ["not", "a", "dict"]}
        )
    )
    responses = _drive_server([request, bad_args], handler, ["x.foo"])
    # First call has empty arguments — that's OK and reaches the handler.
    assert responses[0]["result"] == {"ok": True}
    # Second call has list arguments — must be rejected.
    assert responses[1]["error"]["code"] == INVALID_PARAMS


def test_server_parse_error_on_malformed_line() -> None:
    responses = _drive_server(["not json at all\n"], lambda *_: {}, [])
    assert responses[0]["error"]["code"] == PARSE_ERROR


def test_server_handler_exception_becomes_internal_error() -> None:
    def handler(name: str, arguments: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("simulação")

    request = encode_message(
        build_request("e", "tools/call", params={"name": "x.foo", "arguments": {}})
    )
    responses = _drive_server([request], handler, ["x.foo"])
    assert responses[0]["error"]["code"] == INTERNAL_ERROR
    assert "simulação" in responses[0]["error"]["message"]


# ------------------------------------------------------------- concrete servers


def test_blender_server_rejects_tool_outside_allowlist() -> None:
    handler = blender_server.make_handler(_FakeAdapter(available=True))
    out = handler("shell.run", {"cmd": "ls"}, {})
    assert out["ok"] is False
    assert out["error_code"] == "blender.tool_not_allowlisted"


def test_blender_server_returns_adapter_unavailable_when_blender_missing() -> None:
    handler = blender_server.make_handler(_FakeAdapter(available=False, detail="sem blender"))
    out = handler("blender.create_mesh_primitive", {"primitive": "cube"}, {})
    assert out["ok"] is False
    assert out["error_code"] == "blender.adapter_unavailable"
    assert "sem blender" in out["message"]


def test_blender_server_proxies_to_adapter_when_available() -> None:
    adapter = _FakeAdapter(available=True)
    handler = blender_server.make_handler(adapter)
    out = handler(
        "blender.create_mesh_primitive",
        {"primitive": "cube"},
        {"plan_id": "p1", "project_id": "prj", "step_id": "s1", "step_seq": 1},
    )
    assert out["ok"] is True
    assert adapter.calls[-1]["plan_id"] == "p1"
    assert adapter.calls[-1]["step"].tool_name == "blender.create_mesh_primitive"


def test_fusion_server_returns_mock_envelope_for_allowed_tool() -> None:
    out = fusion_server.handle_tool_call(
        "fusion.create_sketch",
        {"plane_ref": "xy"},
        {"plan_id": "p"},
    )
    assert out["ok"] is True
    assert out["mcp_server"] == "fusion_mcp"
    assert out["transport"] == "stdio"


def test_fusion_server_rejects_unknown_tool() -> None:
    out = fusion_server.handle_tool_call("fusion.weird", {}, {})
    assert out["ok"] is False
    assert out["error_code"] == "fusion.tool_not_allowlisted"


# ------------------------------------------------------------------ stdio client


def test_stdio_client_round_trip_against_real_subprocess() -> None:
    """Full smoke: spawns the blender stdio server and exercises tools/list."""
    client = StdioMCPClient(
        [sys.executable, "-m", "app.modeling.mcp_servers.blender_server"],
        name="blender_mcp",
    )
    try:
        result = client.tools_list()
        assert result["server"] == "blender_mcp"
        assert "blender.create_mesh_primitive" in result["tools"]
        status = client.status()
        assert status["server"] == "blender_mcp"
        # Adapter detail varies by host; just assert the field is present.
        assert "tools" in status
    finally:
        client.close()


def test_stdio_client_surfaces_method_not_found_as_error() -> None:
    client = StdioMCPClient(
        [sys.executable, "-m", "app.modeling.mcp_servers.fusion_server"],
        name="fusion_mcp",
    )
    try:
        with pytest.raises(StdioServerError) as exc_info:
            client.call("does/not/exist")
        assert exc_info.value.code == METHOD_NOT_FOUND
    finally:
        client.close()


# ----------------------------------------------------------- LocalMCPClient mode


class _FakeStdioClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
        self.closed = False

    def tool_call(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls.append((name, arguments or {}, meta or {}))
        return {
            "ok": True,
            "mcp_server": "blender_mcp",
            "transport": "stdio",
            "tool_name": name,
            "software": ModelingSoftware.blender.value,
            "message": "fake stdio response",
            "input": arguments or {},
        }

    def close(self) -> None:
        self.closed = True


def _step(
    tool_name: str, software: ModelingSoftware = ModelingSoftware.blender
) -> ModelingPlanStep:
    return ModelingPlanStep(
        seq=1,
        title=f"Run {tool_name}",
        software=software,
        tool_name=tool_name,
        risk_level=ModelingRiskLevel.low,
        approval_required=False,
        status=ModelingStepStatus.approved,
        input_json={"primitive": "cube"},
    )


def test_local_mcp_client_in_process_mode_uses_adapter_or_mock() -> None:
    client = LocalMCPClient(transport_mode="in_process")
    output = client.execute_step(_step("blender.create_mesh_primitive"))
    # No real Blender in CI, so we get the in-process mock envelope.
    assert output["transport"] in {"mock", "stdio"}
    assert output["mcp_server"] == "blender_mcp"


def test_local_mcp_client_stdio_mode_routes_blender_to_stdio() -> None:
    fake_blender = _FakeStdioClient()
    fake_fusion = _FakeStdioClient()
    client = LocalMCPClient(
        transport_mode="stdio",
        blender_stdio=fake_blender,  # type: ignore[arg-type]
        fusion_stdio=fake_fusion,  # type: ignore[arg-type]
    )
    output = client.execute_step(
        _step("blender.create_mesh_primitive"),
        plan_id="plan-1",
        project_id="proj-1",
    )
    assert output["transport"] == "stdio"
    assert fake_blender.calls and not fake_fusion.calls
    name, arguments, meta = fake_blender.calls[0]
    assert name == "blender.create_mesh_primitive"
    assert arguments == {"primitive": "cube"}
    assert meta["plan_id"] == "plan-1"
    assert meta["project_id"] == "proj-1"


def test_local_mcp_client_stdio_mode_keeps_project_store_in_process() -> None:
    fake_blender = _FakeStdioClient()
    client = LocalMCPClient(
        transport_mode="stdio",
        blender_stdio=fake_blender,  # type: ignore[arg-type]
    )
    output = client.execute_step(_step("project_store.create_snapshot"))
    # project_store stays in-process even when stdio is on; no fake call recorded.
    assert fake_blender.calls == []
    assert output["mcp_server"] == "project_store_mcp"
    assert output["transport"] == "mock"


def test_local_mcp_client_stdio_translates_server_error_to_envelope() -> None:
    class _FailingClient(_FakeStdioClient):
        def tool_call(self, name, arguments=None, meta=None):  # type: ignore[override]
            raise StdioServerError("server caiu", code=-32603, data={"stderr_tail": "boom"})

    failing = _FailingClient()
    client = LocalMCPClient(
        transport_mode="stdio",
        blender_stdio=failing,  # type: ignore[arg-type]
    )
    output = client.execute_step(_step("blender.create_mesh_primitive"))
    assert output["ok"] is False
    assert output["error_code"] == "mcp.stdio_server_error"
    assert output["retryable"] is True
    assert output["host_details"]["stdio_code"] == -32603


# ----------------------------------------------------------------- helper class


class _FakeAdapter:
    def __init__(self, *, available: bool, detail: str = "") -> None:
        self._available = available
        self._detail = detail
        self.calls: list[dict[str, Any]] = []

    def is_available(self) -> bool:
        return self._available

    def status(self):
        from app.modeling.blender_adapter import BlenderAdapterStatus

        return BlenderAdapterStatus(
            connected=self._available,
            transport="stdio" if self._available else "mock",
            status="available" if self._available else "adapter_mock",
            detail=self._detail or ("blender" if self._available else "sem blender"),
            executable="fake" if self._available else None,
        )

    def execute(
        self,
        step: ModelingPlanStep,
        *,
        plan_id: str | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append({"step": step, "plan_id": plan_id, "project_id": project_id})
        return {
            "ok": True,
            "mcp_server": "blender_mcp",
            "transport": "stdio",
            "tool_name": step.tool_name,
            "software": step.software.value,
            "message": "fake adapter execute",
            "input": step.input_json,
        }
