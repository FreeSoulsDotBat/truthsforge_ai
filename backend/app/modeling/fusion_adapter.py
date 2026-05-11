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
import os
import socket
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.contracts import ModelingPlanStep, ModelingSoftware, now_utc
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
    consecutive_failures: int = 0
    last_error_at: datetime | None = None
    last_error_message: str | None = None
    effective_host: str | None = None


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

    # When more than this many consecutive failures pile up the probe goes into
    # cooldown — we still surface a fresh status to callers, but cached.
    BACKOFF_THRESHOLD = 3
    BACKOFF_SECONDS = 5.0
    STATUS_CACHE_SECONDS = 2.0

    def __init__(
        self,
        discovery_path: Path | None = None,
        *,
        timeout_seconds: float = 30.0,
        host_override: str | None = None,
        status_cache_seconds: float | None = None,
    ) -> None:
        self._configured_discovery_path = discovery_path
        self.timeout_seconds = timeout_seconds
        self._configured_host_override = host_override
        self._status_cache_seconds = (
            status_cache_seconds if status_cache_seconds is not None else self.STATUS_CACHE_SECONDS
        )
        self._lock = threading.Lock()
        self._next_request_id = 0
        # Health tracking — written only under _lock.
        self._consecutive_failures = 0
        self._last_error_at: datetime | None = None
        self._last_error_message: str | None = None
        self._cached_status: FusionAdapterStatus | None = None
        self._cached_status_expires_at = 0.0

    # ----------------------------------------------------------- discovery

    @property
    def discovery_path(self) -> Path:
        if self._configured_discovery_path is not None:
            return self._configured_discovery_path
        return settings.state_dir / "fusion-bridge.json"

    def _host_override(self) -> str | None:
        """Pick the runtime host override.

        Priority: constructor arg > env var. Returning ``None`` means "use the
        host that the add-in wrote into the discovery file". Useful when the
        backend runs inside a container and needs to redirect 127.0.0.1 to
        ``host.docker.internal`` (or any other reachable host).
        """
        if self._configured_host_override is not None:
            return self._configured_host_override
        env_override = os.environ.get("TRUTHS_FORGE_FUSION_BRIDGE_HOST", "").strip()
        return env_override or None

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
        host = self._host_override() or str(raw.get("host") or "127.0.0.1")
        port = int(raw.get("port") or 0)
        token = str(raw.get("token") or "")
        if not port or not token:
            return None
        return FusionBridgeDiscovery(host=host, port=port, token=token, pid=raw.get("pid"))

    # ----------------------------------------------- health-check accounting

    def _record_failure(self, message: str) -> None:
        with self._lock:
            self._consecutive_failures += 1
            self._last_error_at = now_utc()
            self._last_error_message = message

    def _record_success(self) -> None:
        with self._lock:
            self._consecutive_failures = 0
            self._last_error_at = None
            self._last_error_message = None

    def _in_backoff(self) -> bool:
        with self._lock:
            if self._consecutive_failures < self.BACKOFF_THRESHOLD:
                return False
            if self._last_error_at is None:
                return False
            elapsed = (now_utc() - self._last_error_at).total_seconds()
            return elapsed < self.BACKOFF_SECONDS

    def _snapshot_health(self) -> tuple[int, datetime | None, str | None]:
        with self._lock:
            return (
                self._consecutive_failures,
                self._last_error_at,
                self._last_error_message,
            )

    # -------------------------------------------------------------- status

    def status(self) -> FusionAdapterStatus:
        now_monotonic = time.monotonic()
        cached = self._cached_status
        if cached is not None and now_monotonic < self._cached_status_expires_at:
            return cached

        discovery = self._read_discovery()
        if discovery is None:
            failures, last_at, last_msg = self._snapshot_health()
            status = FusionAdapterStatus(
                connected=False,
                transport="mock",
                status="adapter_mock",
                detail=(
                    "Add-in do Fusion 360 não detectado. "
                    "Abra o Fusion e ative o add-in 'Truth's Forge' para conectar."
                ),
                discovery_path=str(self.discovery_path),
                consecutive_failures=failures,
                last_error_at=last_at,
                last_error_message=last_msg,
                effective_host=self._host_override(),
            )
            self._cache_status(status, ttl_seconds=self._status_cache_seconds)
            return status

        if self._in_backoff():
            failures, last_at, last_msg = self._snapshot_health()
            status = FusionAdapterStatus(
                connected=False,
                transport="mock",
                status="adapter_backoff",
                detail=(
                    f"Add-in falhou {failures} vez(es) em sequência; "
                    f"probing em backoff por {self.BACKOFF_SECONDS:.0f}s."
                ),
                discovery_path=str(self.discovery_path),
                addin_pid=discovery.pid,
                consecutive_failures=failures,
                last_error_at=last_at,
                last_error_message=last_msg,
                effective_host=discovery.host,
            )
            self._cache_status(status, ttl_seconds=self._status_cache_seconds)
            return status

        try:
            self._call(discovery, PROTOCOL_STATUS, params=None)
        except FusionBridgeError as exc:
            self._record_failure(str(exc))
            failures, last_at, last_msg = self._snapshot_health()
            status = FusionAdapterStatus(
                connected=False,
                transport="mock",
                status="adapter_offline",
                detail=f"Add-in do Fusion 360 não respondeu: {exc}",
                discovery_path=str(self.discovery_path),
                addin_pid=discovery.pid,
                consecutive_failures=failures,
                last_error_at=last_at,
                last_error_message=last_msg,
                effective_host=discovery.host,
            )
            self._cache_status(status, ttl_seconds=self._status_cache_seconds)
            return status

        self._record_success()
        status = FusionAdapterStatus(
            connected=True,
            transport="loopback",
            status="available",
            detail="Add-in do Fusion 360 conectado via loopback autenticado.",
            discovery_path=str(self.discovery_path),
            addin_pid=discovery.pid,
            consecutive_failures=0,
            effective_host=discovery.host,
        )
        self._cache_status(status, ttl_seconds=self._status_cache_seconds)
        return status

    def is_available(self) -> bool:
        return self.status().connected

    def _cache_status(self, status: FusionAdapterStatus, *, ttl_seconds: float) -> None:
        self._cached_status = status
        self._cached_status_expires_at = time.monotonic() + max(ttl_seconds, 0.0)

    def invalidate_status_cache(self) -> None:
        """Force the next ``status()`` call to re-probe the add-in."""
        self._cached_status = None
        self._cached_status_expires_at = 0.0

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
            self._record_failure(str(exc))
            self.invalidate_status_cache()
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
        self._record_success()
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
