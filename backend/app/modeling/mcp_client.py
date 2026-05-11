from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.core.contracts import ModelingPlanStep, ModelingSoftware
from app.modeling.blender_adapter import BLENDER_TOOLS, BlenderAdapter
from app.modeling.stdio_client import (
    StdioMCPClient,
    StdioServerError,
    build_blender_command,
    build_fusion_command,
)

logger = logging.getLogger(__name__)

FUSION_TOOLS = [
    "fusion.create_sketch",
    "fusion.extrude_profile",
    "fusion.validate_dimensions",
    "fusion.validate_printability",
]


class LocalMCPClient:
    """Boundary in front of the local MCP adapters.

    Two transport modes are supported:

    - ``in_process`` (default): calls ``BlenderAdapter.execute`` directly; cheap
      and easy to test, no extra processes involved.
    - ``stdio``: spawns ``blender_server`` and ``fusion_server`` as subprocesses
      and talks JSON-RPC over their pipes. Same observable behaviour but lets us
      relocate the MCP servers later (e.g. ship them next to a remote Blender
      host) without touching the service layer.

    The transport is selected by ``settings.modeling_mcp_transport``
    (``TRUTHS_FORGE_MCP_TRANSPORT=stdio``) and can also be forced via the
    constructor for tests.
    """

    def __init__(
        self,
        blender_adapter: BlenderAdapter | None = None,
        *,
        transport_mode: str | None = None,
        blender_stdio: StdioMCPClient | None = None,
        fusion_stdio: StdioMCPClient | None = None,
    ) -> None:
        self.blender_adapter = blender_adapter or BlenderAdapter()
        mode = (transport_mode or settings.modeling_mcp_transport or "in_process").lower()
        self.transport_mode = mode if mode in {"in_process", "stdio"} else "in_process"
        self._blender_stdio = blender_stdio
        self._fusion_stdio = fusion_stdio

    # ------------------------------------------------------------------ stdio

    def _blender_stdio_client(self) -> StdioMCPClient:
        if self._blender_stdio is None:
            self._blender_stdio = StdioMCPClient(build_blender_command(), name="blender_mcp")
        return self._blender_stdio

    def _fusion_stdio_client(self) -> StdioMCPClient:
        if self._fusion_stdio is None:
            self._fusion_stdio = StdioMCPClient(build_fusion_command(), name="fusion_mcp")
        return self._fusion_stdio

    def shutdown(self) -> None:
        for client in (self._blender_stdio, self._fusion_stdio):
            if client is not None:
                client.close()

    # ------------------------------------------------------------- capabilities

    def capabilities(self) -> dict[ModelingSoftware, list[str]]:
        return {
            ModelingSoftware.blender: list(BLENDER_TOOLS),
            ModelingSoftware.fusion: list(FUSION_TOOLS),
        }

    def is_connected(self, software: ModelingSoftware) -> bool:
        if software == ModelingSoftware.blender:
            return self.blender_adapter.status().connected
        return False

    def transport(self, software: ModelingSoftware) -> str:
        if self.transport_mode == "stdio":
            return "stdio"
        if software == ModelingSoftware.blender:
            return self.blender_adapter.status().transport
        return "mock"

    def adapter_status(self, software: ModelingSoftware) -> str:
        if software == ModelingSoftware.blender:
            return self.blender_adapter.status().status
        return "adapter_mock"

    def detail(self, software: ModelingSoftware) -> str:
        if software == ModelingSoftware.blender:
            return self.blender_adapter.status().detail
        return "Adapter Fusion 360 ainda não conectado; chamadas ficam simuladas e auditadas."

    # ------------------------------------------------------------------ execute

    def execute_step(
        self,
        step: ModelingPlanStep,
        *,
        plan_id: str | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        if self.transport_mode == "stdio":
            return self._execute_step_stdio(step, plan_id=plan_id, project_id=project_id)
        return self._execute_step_in_process(step, plan_id=plan_id, project_id=project_id)

    # ------------------------------------------------------------ in_process

    def _execute_step_in_process(
        self,
        step: ModelingPlanStep,
        *,
        plan_id: str | None,
        project_id: str | None,
    ) -> dict[str, Any]:
        if step.tool_name.startswith("blender.") and self.blender_adapter.is_available():
            return self.blender_adapter.execute(step, plan_id=plan_id, project_id=project_id)

        server = "project_store_mcp"
        if step.tool_name.startswith("blender."):
            server = "blender_mcp"
        if step.tool_name.startswith("fusion."):
            server = "fusion_mcp"
        return {
            "ok": True,
            "mcp_server": server,
            "transport": "mock",
            "tool_name": step.tool_name,
            "software": step.software.value,
            "message": (
                "Tool call preparada para MCP local; execução real exige adapter desktop conectado."
            ),
            "input": step.input_json,
        }

    # ---------------------------------------------------------------- stdio

    def _execute_step_stdio(
        self,
        step: ModelingPlanStep,
        *,
        plan_id: str | None,
        project_id: str | None,
    ) -> dict[str, Any]:
        if step.tool_name.startswith("blender."):
            client = self._blender_stdio_client()
            server_name = "blender_mcp"
        elif step.tool_name.startswith("fusion."):
            client = self._fusion_stdio_client()
            server_name = "fusion_mcp"
        else:
            # project_store.* and other internal tools stay in-process even when
            # stdio is enabled — they live inside the backend itself.
            return self._execute_step_in_process(step, plan_id=plan_id, project_id=project_id)

        meta = {
            "plan_id": plan_id,
            "project_id": project_id,
            "step_id": step.id,
            "step_seq": step.seq,
            "step_title": step.title,
            "software": step.software.value,
            "risk_level": step.risk_level.value,
            "approval_required": step.approval_required,
        }
        try:
            result = client.tool_call(step.tool_name, arguments=step.input_json, meta=meta)
        except StdioServerError as exc:
            logger.warning("Servidor stdio '%s' falhou: %s", server_name, exc)
            return {
                "ok": False,
                "mcp_server": server_name,
                "transport": "stdio",
                "tool_name": step.tool_name,
                "software": step.software.value,
                "error_code": "mcp.stdio_server_error",
                "retryable": True,
                "safe_to_retry_after_snapshot_restore": False,
                "message": str(exc),
                "input": step.input_json,
                "host_details": {"stdio_code": exc.code, "stdio_data": exc.data},
            }
        if isinstance(result, dict):
            return result
        return {
            "ok": False,
            "mcp_server": server_name,
            "transport": "stdio",
            "tool_name": step.tool_name,
            "software": step.software.value,
            "error_code": "mcp.unexpected_payload",
            "retryable": False,
            "safe_to_retry_after_snapshot_restore": False,
            "message": "Servidor stdio devolveu payload sem ser objeto JSON.",
            "input": step.input_json,
        }
