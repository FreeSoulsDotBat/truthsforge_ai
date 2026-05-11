"""stdio JSON-RPC server that proxies tool calls to ``BlenderAdapter``.

Spawn this server as ``python -m app.modeling.mcp_servers.blender_server``. The
backend's ``StdioMCPClient`` keeps the process alive across requests and shuts
it down on application exit. This module deliberately reuses the in-process
``BlenderAdapter`` so all the safety guards (allowlist, error envelope,
workspace jail) stay in a single place.
"""

from __future__ import annotations

import sys
from typing import Any

from app.core.contracts import (
    ModelingPlanStep,
    ModelingRiskLevel,
    ModelingSoftware,
    ModelingStepStatus,
)
from app.modeling.blender_adapter import BLENDER_TOOLS, BlenderAdapter
from app.modeling.mcp_servers._server_base import run_server

SERVER_NAME = "blender_mcp"


def _build_step(name: str, arguments: dict[str, Any], meta: dict[str, Any]) -> ModelingPlanStep:
    """Reconstruct a ModelingPlanStep from MCP tool-call params for the adapter."""
    return ModelingPlanStep(
        id=str(meta.get("step_id") or f"stdio_{name}"),
        seq=int(meta.get("step_seq") or 1),
        title=str(meta.get("step_title") or name),
        software=ModelingSoftware.blender,
        tool_name=name,
        risk_level=ModelingRiskLevel(str(meta.get("risk_level") or "low")),
        approval_required=bool(meta.get("approval_required", False)),
        status=ModelingStepStatus.approved,
        input_json=dict(arguments),
    )


def make_handler(adapter: BlenderAdapter):
    def handle_tool_call(
        name: str, arguments: dict[str, Any], meta: dict[str, Any]
    ) -> dict[str, Any]:
        if name not in BLENDER_TOOLS:
            return {
                "ok": False,
                "mcp_server": SERVER_NAME,
                "transport": "stdio",
                "tool_name": name,
                "software": ModelingSoftware.blender.value,
                "error_code": "blender.tool_not_allowlisted",
                "retryable": False,
                "safe_to_retry_after_snapshot_restore": False,
                "message": f"Ferramenta '{name}' não está na allowlist do servidor Blender.",
                "input": arguments,
            }
        if not adapter.is_available():
            return {
                "ok": False,
                "mcp_server": SERVER_NAME,
                "transport": "stdio",
                "tool_name": name,
                "software": ModelingSoftware.blender.value,
                "error_code": "blender.adapter_unavailable",
                "retryable": False,
                "safe_to_retry_after_snapshot_restore": False,
                "message": adapter.status().detail,
                "input": arguments,
            }
        step = _build_step(name, arguments, meta)
        return adapter.execute(
            step,
            plan_id=meta.get("plan_id"),
            project_id=meta.get("project_id"),
        )

    return handle_tool_call


def make_status_handler(adapter: BlenderAdapter):
    def handle_status() -> dict[str, Any]:
        status = adapter.status()
        return {
            "server": SERVER_NAME,
            "connected": status.connected,
            "transport": status.transport,
            "status": status.status,
            "detail": status.detail,
            "executable": status.executable,
            "tools": BLENDER_TOOLS,
        }

    return handle_status


def main() -> int:
    adapter = BlenderAdapter()
    return run_server(
        server_name=SERVER_NAME,
        tools=BLENDER_TOOLS,
        handle_tool_call=make_handler(adapter),
        handle_status=make_status_handler(adapter),
    )


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    sys.exit(main())
