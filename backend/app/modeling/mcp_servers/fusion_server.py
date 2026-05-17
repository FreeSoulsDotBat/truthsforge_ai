"""stdio JSON-RPC server for Fusion 360.

Behaviour:

- When Autodesk's local Fusion MCP Server is reachable, proxy allowlisted
  ``tools/call`` requests through ``FusionDesktopAdapter`` over HTTP.
- When only the legacy desktop add-in is detected, proxy through its loopback
  bridge.
- Otherwise, return a mock envelope identifying the missing bridge/MCP server so
  the UI surfaces the right reason — same shape as the in-process mock the rest
  of the stack already understands.

The wire format is identical to ``blender_server`` for parity.
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
from app.modeling.fusion_adapter import FUSION_TOOLS, FusionDesktopAdapter
from app.modeling.mcp_servers._server_base import run_server

SERVER_NAME = "fusion_mcp"


def _build_step(name: str, arguments: dict[str, Any], meta: dict[str, Any]) -> ModelingPlanStep:
    return ModelingPlanStep(
        id=str(meta.get("step_id") or f"stdio_{name}"),
        seq=int(meta.get("step_seq") or 1),
        title=str(meta.get("step_title") or name),
        software=ModelingSoftware.fusion,
        tool_name=name,
        risk_level=ModelingRiskLevel(str(meta.get("risk_level") or "low")),
        approval_required=bool(meta.get("approval_required", False)),
        status=ModelingStepStatus.approved,
        input_json=dict(arguments),
    )


def make_handler(adapter: FusionDesktopAdapter):
    def handle_tool_call(
        name: str, arguments: dict[str, Any], meta: dict[str, Any]
    ) -> dict[str, Any]:
        if name not in FUSION_TOOLS:
            return {
                "ok": False,
                "mcp_server": SERVER_NAME,
                "transport": "stdio",
                "tool_name": name,
                "software": ModelingSoftware.fusion.value,
                "error_code": "fusion.tool_not_allowlisted",
                "retryable": False,
                "safe_to_retry_after_snapshot_restore": False,
                "message": f"Ferramenta '{name}' não está na allowlist do servidor Fusion.",
                "input": arguments,
            }
        if not adapter.is_available():
            return {
                "ok": True,
                "mcp_server": SERVER_NAME,
                "transport": "stdio",
                "tool_name": name,
                "software": ModelingSoftware.fusion.value,
                "message": (
                    "Tool call preparada via servidor MCP stdio do Fusion. "
                    "Add-in desktop ainda não conectado; chamadas ficam em mock."
                ),
                "input": arguments,
                "_meta": meta,
            }
        step = _build_step(name, arguments, meta)
        return adapter.execute(step, plan_id=meta.get("plan_id"), project_id=meta.get("project_id"))

    return handle_tool_call


def make_status_handler(adapter: FusionDesktopAdapter):
    def handle_status() -> dict[str, Any]:
        status = adapter.status()
        return {
            "server": SERVER_NAME,
            "connected": status.connected,
            "transport": status.transport,
            "status": status.status,
            "detail": status.detail,
            "mcp_url": status.mcp_url,
            "discovery_path": status.discovery_path,
            "addin_pid": status.addin_pid,
            "tools": list(FUSION_TOOLS),
        }

    return handle_status


def main() -> int:
    adapter = FusionDesktopAdapter()
    return run_server(
        server_name=SERVER_NAME,
        tools=list(FUSION_TOOLS),
        handle_tool_call=make_handler(adapter),
        handle_status=make_status_handler(adapter),
    )


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


# Backwards-compatible aliases for tests imported in PR #5.
_compat_adapter = FusionDesktopAdapter(enable_autodesk_mcp=False)
handle_tool_call = make_handler(_compat_adapter)
handle_status = make_status_handler(_compat_adapter)
