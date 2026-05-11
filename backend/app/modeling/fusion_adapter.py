"""Bridge between the backend and the Fusion 360 desktop add-in.

The add-in runs inside the Fusion 360 process (its embedded Python). At startup
it writes a discovery file under ``settings.state_dir / "fusion-bridge.json"``
containing ``{"host", "port", "token", "pid"}`` and listens on the loopback
interface for line-delimited JSON-RPC messages. This adapter speaks that wire
format and reuses the same ``ModelingErrorEnvelope``/audit conventions as the
rest of the modeling stack.

Design rules (Autodesk docs):

- The add-in routes every Fusion-API touch back to the main thread via custom
  events. The backend never makes API calls directly; it only sends ``tools/call``
  intents.
- The token is ephemeral (regenerated on add-in startup) and lives only on the
  local disk; the loopback socket is the trust boundary.
- The discovery file is the single source of truth for "is the add-in alive?".
  Stale files left behind by a crash are detected because the TCP connect refuses.
"""

from __future__ import annotations

import json
import logging
import socket
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.contracts import ModelingPlanStep, ModelingSoftware
from app.modeling.mcp_servers.protocol import (
    build_request,
    decode_message,
    encode_message,
)

logger = logging.getLogger(__name__)

FUSION_TOOLS: tuple[str, ...] = (
    "fusion.open_design",
    "fusion.create_sketch",
    "fusion.add_rectangle",
    "fusion.add_circle",
    "fusion.extrude_profile",
    "fusion.set_parameter",
    "fusion.export_step",
    "fusion.export_stl",
    "fusion.export_3mf",
    "fusion.validate_dimensions",
    "fusion.validate_printability",
)

# Methods that the add-in always exposes regardless of tool surface.
PROTOCOL_AUTH = "auth"
PROTOCOL_TOOLS_LIST = "tools/list"
PROTOCOL_TOOLS_CALL = "tools/call"
PROTOCOL_STATUS = "status"


@dataclass(frozen=True)
class FusionBridgeDiscovery:
    host: str
    port: int
    token: str
    pid: int | None = None


@dataclass(frozen=True)
class FusionAdapterStatus:
    connected: bool
    transport: str
    status: str
    detail: str
    discovery_path: str | None = None
    addin_pid: int | None = None


class FusionBridgeError(RuntimeError):
    """Raised when the bridge connection fails or the add-in returns an error."""

    def __init__(self, message: str, *, code: int | None = None, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data


class FusionDesktopAdapter:
    """Owns a short-lived TCP connection per call to the Fusion add-in.

    Each call opens, authenticates, dispatches, and closes; the add-in is
    expected to handle a steady stream of these. We deliberately do not keep a
    persistent socket because the Fusion process restarts during normal use
    (e.g. on document switch) and a per-call connection is easier to reason
    about under those resets.
    """

    tools = list(FUSION_TOOLS)

    def __init__(
        self,
        discovery_path: Path | None = None,
        *,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._configured_discovery_path = discovery_path
        self.timeout_seconds = timeout_seconds
        self._lock = threading.Lock()
        self._next_request_id = 0

    # ----------------------------------------------------------- discovery

    @property
    def discovery_path(self) -> Path:
        if self._configured_discovery_path is not None:
            return self._configured_discovery_path
        return settings.state_dir / "fusion-bridge.json"

    def _read_discovery(self) -> FusionBridgeDiscovery | None:
        path = self.discovery_path
        if not path.is_file():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(raw, dict):
            return None
        host = str(raw.get("host") or "127.0.0.1")
        port = int(raw.get("port") or 0)
        token = str(raw.get("token") or "")
        if not port or not token:
            return None
        return FusionBridgeDiscovery(host=host, port=port, token=token, pid=raw.get("pid"))

    # -------------------------------------------------------------- status

    def status(self) -> FusionAdapterStatus:
        discovery = self._read_discovery()
        if discovery is None:
            return FusionAdapterStatus(
                connected=False,
                transport="mock",
                status="adapter_mock",
                detail=(
                    "Add-in do Fusion 360 não detectado. "
                    "Abra o Fusion e ative o add-in 'Truth's Forge' para conectar."
                ),
                discovery_path=str(self.discovery_path),
            )
        try:
            # Reuse the auth handshake as a liveness probe.
            self._call(discovery, PROTOCOL_STATUS, params=None)
        except FusionBridgeError as exc:
            return FusionAdapterStatus(
                connected=False,
                transport="mock",
                status="adapter_offline",
                detail=f"Add-in do Fusion 360 não respondeu: {exc}",
                discovery_path=str(self.discovery_path),
                addin_pid=discovery.pid,
            )
        return FusionAdapterStatus(
            connected=True,
            transport="loopback",
            status="available",
            detail="Add-in do Fusion 360 conectado via loopback autenticado.",
            discovery_path=str(self.discovery_path),
            addin_pid=discovery.pid,
        )

    def is_available(self) -> bool:
        return self.status().connected

    # -------------------------------------------------------------- execute

    def execute(
        self,
        step: ModelingPlanStep,
        *,
        plan_id: str | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        if step.tool_name not in FUSION_TOOLS:
            return self._error_envelope(
                step,
                error_code="fusion.tool_not_allowlisted",
                message=f"Ferramenta '{step.tool_name}' não permitida no adapter Fusion.",
                retryable=False,
            )
        discovery = self._read_discovery()
        if discovery is None:
            return self._error_envelope(
                step,
                error_code="fusion.bridge_not_configured",
                message=(
                    "Add-in do Fusion 360 não detectado. "
                    "Abra o Fusion e ative o add-in 'Truth's Forge'."
                ),
                retryable=True,
            )
        params = {
            "name": step.tool_name,
            "arguments": dict(step.input_json),
            "_meta": {
                "plan_id": plan_id,
                "project_id": project_id,
                "step_id": step.id,
                "step_seq": step.seq,
                "step_title": step.title,
                "software": ModelingSoftware.fusion.value,
                "risk_level": step.risk_level.value,
                "approval_required": step.approval_required,
            },
        }
        try:
            result = self._call(discovery, PROTOCOL_TOOLS_CALL, params=params)
        except FusionBridgeError as exc:
            return self._error_envelope(
                step,
                error_code="fusion.bridge_error",
                message=str(exc),
                retryable=True,
                host_details={"bridge_code": exc.code, "bridge_data": exc.data},
            )
        if not isinstance(result, dict):
            return self._error_envelope(
                step,
                error_code="fusion.bridge_invalid_payload",
                message="Add-in devolveu payload sem ser objeto JSON.",
                retryable=False,
            )
        return result

    # ----------------------------------------------------------- networking

    def _call(
        self,
        discovery: FusionBridgeDiscovery,
        method: str,
        params: dict[str, Any] | None,
    ) -> Any:
        with self._lock:
            self._next_request_id += 1
            auth_request_id = f"fusion-auth-{self._next_request_id}"
            self._next_request_id += 1
            method_request_id = f"fusion-{method.replace('/', '-')}-{self._next_request_id}"

        try:
            with socket.create_connection(
                (discovery.host, discovery.port), timeout=self.timeout_seconds
            ) as conn:
                conn.settimeout(self.timeout_seconds)
                reader = conn.makefile("r", encoding="utf-8", newline="\n")
                writer = conn.makefile("w", encoding="utf-8", newline="\n")
                # 1) Auth handshake.
                writer.write(
                    encode_message(
                        build_request(auth_request_id, PROTOCOL_AUTH, {"token": discovery.token})
                    )
                )
                writer.flush()
                self._consume_response(reader, auth_request_id)
                # 2) Real method.
                writer.write(encode_message(build_request(method_request_id, method, params)))
                writer.flush()
                return self._consume_response(reader, method_request_id)
        except OSError as exc:
            raise FusionBridgeError(
                f"Conexão com add-in Fusion recusada/expirou: {exc}",
                data={"host": discovery.host, "port": discovery.port},
            ) from exc

    @staticmethod
    def _consume_response(reader: Any, expected_id: str) -> Any:
        line = reader.readline()
        if not line:
            raise FusionBridgeError("Add-in encerrou a conexão sem responder.")
        response = decode_message(line)
        if response.get("id") != expected_id:
            raise FusionBridgeError(
                f"Add-in devolveu id divergente: esperado {expected_id}, "
                f"recebido {response.get('id')!r}.",
            )
        if "error" in response:
            error = response["error"] or {}
            raise FusionBridgeError(
                str(error.get("message") or "Erro desconhecido."),
                code=error.get("code"),
                data=error.get("data"),
            )
        return response.get("result")

    # ------------------------------------------------------------- envelope

    @staticmethod
    def _error_envelope(
        step: ModelingPlanStep,
        *,
        error_code: str,
        message: str,
        retryable: bool,
        host_details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "mcp_server": "fusion_mcp",
            "transport": "loopback",
            "tool_name": step.tool_name,
            "software": ModelingSoftware.fusion.value,
            "error_code": error_code,
            "retryable": retryable,
            "safe_to_retry_after_snapshot_restore": False,
            "message": message,
            "input": step.input_json,
            "host_details": host_details or {},
        }
