from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.core.config import settings
from app.core.contracts import ModelingPlanStep, ModelingSoftware, ModelingTraceSource
from app.modeling.blender_adapter import BLENDER_TOOLS, BlenderAdapter
from app.modeling.fusion_adapter import FUSION_TOOLS as FUSION_ADAPTER_TOOLS
from app.modeling.fusion_adapter import FusionDesktopAdapter
from app.modeling.observability import current_trace_id, get_tracer
from app.modeling.stdio_client import (
    StdioMCPClient,
    StdioServerError,
    build_blender_command,
    build_fusion_command,
)

if TYPE_CHECKING:
    from app.modeling.mcp_standalone.client import StandaloneMCPClient

logger = logging.getLogger(__name__)

FUSION_TOOLS = list(FUSION_ADAPTER_TOOLS)


class LocalMCPClient:
    """Boundary in front of the local MCP adapters.

    Three transport modes are supported:

    - ``in_process`` (default): calls ``BlenderAdapter.execute`` directly; cheap
      and easy to test, no extra processes involved.
    - ``stdio``: spawns ``blender_server`` and ``fusion_server`` as subprocesses
      and talks JSON-RPC over their pipes. Same observable behaviour but lets us
      relocate the MCP servers later (e.g. ship them next to a remote Blender
      host) without touching the service layer.
    - ``mcp_http`` (ADR-017): routes ``fusion.*`` steps through the standalone
      MCP server (HTTP streamable + Bearer auth) via ``StandaloneMCPClient``;
      ``blender.*`` (frozen) and ``project_store.*`` stay in-process. The backend
      becomes one client among others (e.g. Claude).

    The transport is selected by ``settings.modeling_mcp_transport``
    (``TRUTHS_FORGE_MCP_TRANSPORT=stdio|mcp_http``) and can also be forced via
    the constructor for tests.
    """

    def __init__(
        self,
        blender_adapter: BlenderAdapter | None = None,
        *,
        transport_mode: str | None = None,
        blender_stdio: StdioMCPClient | None = None,
        fusion_stdio: StdioMCPClient | None = None,
        fusion_adapter: FusionDesktopAdapter | None = None,
        standalone_client: StandaloneMCPClient | None = None,
    ) -> None:
        self.blender_adapter = blender_adapter or BlenderAdapter()
        self.fusion_adapter = fusion_adapter or FusionDesktopAdapter()
        mode = (transport_mode or settings.modeling_mcp_transport or "in_process").lower()
        self.transport_mode = mode if mode in {"in_process", "stdio", "mcp_http"} else "in_process"
        self._blender_stdio = blender_stdio
        self._fusion_stdio = fusion_stdio
        self._standalone = standalone_client

    # ------------------------------------------------------------------ stdio

    def _blender_stdio_client(self) -> StdioMCPClient:
        if self._blender_stdio is None:
            self._blender_stdio = StdioMCPClient(build_blender_command(), name="blender_mcp")
        return self._blender_stdio

    def _fusion_stdio_client(self) -> StdioMCPClient:
        if self._fusion_stdio is None:
            self._fusion_stdio = StdioMCPClient(build_fusion_command(), name="fusion_mcp")
        return self._fusion_stdio

    # -------------------------------------------------------------- mcp_http

    def _standalone_client(self) -> StandaloneMCPClient:
        if self._standalone is None:
            # Import tardio: o SDK MCP só é necessário neste transporte.
            from app.modeling.mcp_standalone.client import StandaloneMCPClient

            self._standalone = StandaloneMCPClient()
        return self._standalone

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
        if software == ModelingSoftware.fusion:
            return self.fusion_adapter.status().connected
        return False

    def transport(self, software: ModelingSoftware) -> str:
        if self.transport_mode == "stdio":
            return "stdio"
        if self.transport_mode == "mcp_http" and software == ModelingSoftware.fusion:
            return "mcp_http"
        if software == ModelingSoftware.blender:
            return self.blender_adapter.status().transport
        if software == ModelingSoftware.fusion:
            return self.fusion_adapter.status().transport
        return "mock"

    def adapter_status(self, software: ModelingSoftware) -> str:
        if software == ModelingSoftware.blender:
            return self.blender_adapter.status().status
        if software == ModelingSoftware.fusion:
            return self.fusion_adapter.status().status
        return "adapter_mock"

    def detail(self, software: ModelingSoftware) -> str:
        if software == ModelingSoftware.blender:
            return self.blender_adapter.status().detail
        if software == ModelingSoftware.fusion:
            return self.fusion_adapter.status().detail
        return "Adapter ainda não conectado; chamadas ficam simuladas e auditadas."

    # ------------------------------------------------------------------ execute

    def execute_step(
        self,
        step: ModelingPlanStep,
        *,
        plan_id: str | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        if self.transport_mode == "mcp_http":
            return self._execute_step_mcp_http(step, plan_id=plan_id, project_id=project_id)
        if self.transport_mode == "stdio":
            return self._execute_step_stdio(step, plan_id=plan_id, project_id=project_id)
        return self._execute_step_in_process(step, plan_id=plan_id, project_id=project_id)

    # -------------------------------------------------------------- mcp_http

    def _execute_step_mcp_http(
        self,
        step: ModelingPlanStep,
        *,
        plan_id: str | None,
        project_id: str | None,
    ) -> dict[str, Any]:
        # Só ``fusion.*`` vai pelo servidor MCP standalone (ADR-017). Blender
        # (congelado) e ``project_store.*`` (internos ao backend) seguem
        # in-process — mesmo critério do roteamento stdio.
        if step.tool_name.startswith("fusion."):
            return self._standalone_client().execute_step(
                step, plan_id=plan_id, project_id=project_id
            )
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
        if step.tool_name.startswith("fusion.") and self.fusion_adapter.is_available():
            return self.fusion_adapter.execute(step, plan_id=plan_id, project_id=project_id)

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

        # Propaga trace_id ativo para o servidor MCP via campo reservado
        # ``_trace_id`` no meta do JSON-RPC. O servidor (Fusion addin,
        # Blender runner) reflete em ``trace_events: []`` na resposta para
        # eventos emitidos do lado do adapter.
        trace_id = current_trace_id()
        meta = {
            "plan_id": plan_id,
            "project_id": project_id,
            "step_id": step.id,
            "step_seq": step.seq,
            "step_title": step.title,
            "software": step.software.value,
            "risk_level": step.risk_level.value,
            "approval_required": step.approval_required,
            "_trace_id": trace_id,
        }
        try:
            result = client.tool_call(step.tool_name, arguments=step.input_json, meta=meta)
        except StdioServerError as exc:
            logger.error("Servidor stdio '%s' falhou: %s", server_name, exc, exc_info=True)
            tracer = get_tracer()
            tracer.record(
                "mcp.transport_error",
                source=ModelingTraceSource.mcp,
                level="error",
                message=str(exc),
                payload={
                    "server": server_name,
                    "tool_name": step.tool_name,
                    "stdio_code": exc.code,
                    "stdio_data": exc.data,
                },
            )
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
            # Drena eventos de trace emitidos pelo adapter (Fusion/Blender).
            # O adapter acumula eventos durante a execução do tool e os
            # retorna como ``trace_events: []``. Aqui incorporamos ao trace
            # ativo via ModelingTracer.ingest_external_events.
            trace_events = result.get("trace_events")
            if isinstance(trace_events, list) and trace_events:
                default_source = (
                    ModelingTraceSource.fusion
                    if server_name == "fusion_mcp"
                    else ModelingTraceSource.blender
                )
                get_tracer().ingest_external_events(trace_events, default_source=default_source)
                # Não exporta para o caller (poluiria a interface dict
                # consumida pelo executor) — já está nos eventos
                # persistidos via tracer.
                result = {k: v for k, v in result.items() if k != "trace_events"}
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
