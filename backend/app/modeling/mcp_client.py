from __future__ import annotations

from typing import Any

from app.core.contracts import ModelingPlanStep, ModelingSoftware
from app.modeling.blender_adapter import BLENDER_TOOLS, BlenderAdapter


class LocalMCPClient:
    """Thin boundary for local MCP adapters.

    The first implementation is intentionally mockable: it records what would be sent
    to Blender/Fusion without executing arbitrary desktop automation.
    """

    def __init__(self, blender_adapter: BlenderAdapter | None = None) -> None:
        self.blender_adapter = blender_adapter or BlenderAdapter()

    def capabilities(self) -> dict[ModelingSoftware, list[str]]:
        return {
            ModelingSoftware.blender: BLENDER_TOOLS,
            ModelingSoftware.fusion: [
                "fusion.create_sketch",
                "fusion.extrude_profile",
                "fusion.validate_dimensions",
            ],
        }

    def is_connected(self, software: ModelingSoftware) -> bool:
        if software == ModelingSoftware.blender:
            return self.blender_adapter.status().connected
        return False

    def transport(self, software: ModelingSoftware) -> str:
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

    def execute_step(
        self,
        step: ModelingPlanStep,
        *,
        plan_id: str | None = None,
        project_id: str | None = None,
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
