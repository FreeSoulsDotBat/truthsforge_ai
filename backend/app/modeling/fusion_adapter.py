"""Bridge between the backend and local Fusion 360 MCP surfaces.

Preferred path: Autodesk's built-in Fusion MCP Server on
``TRUTHS_FORGE_FUSION_MCP_URL`` (default ``http://127.0.0.1:27182/mcp``). That
server exposes a generic Python execution tool, so this adapter never forwards
model-generated scripts. It translates the existing ``fusion.*`` allowlist into
backend-owned deterministic scripts and sends only those via JSON-RPC over HTTP.

Legacy fallback: the Truth's Forge Fusion add-in under ``apps/fusion-addin``.
At startup it writes a discovery file under
``settings.state_dir / "fusion-bridge.json"`` containing
``{"host", "port", "token", "pid"}`` and listens on loopback for line-delimited
JSON-RPC messages. This keeps older local setups working while the official MCP
port becomes the default.

Both paths reuse the same ``ModelingErrorEnvelope``/audit conventions as the
rest of the modeling stack. Stale discovery files left behind by a crash are
detected because the TCP connect refuses.
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
from urllib.parse import urlparse, urlunparse

import httpx

from app.core.config import settings
from app.core.contracts import ModelingPlanStep, ModelingSoftware, now_utc
from app.modeling.fusion_mcp_scripts import build_autodesk_fusion_script
from app.modeling.mcp_servers.protocol import (
    build_request,
    decode_message,
    encode_message,
)

from app.modeling.tool_registry import FUSION_TOOLS as _REGISTRY_FUSION_TOOLS

logger = logging.getLogger(__name__)

# ``FUSION_TOOLS`` is derived from :mod:`app.modeling.tool_registry`
# (ADR-013) and intentionally **excludes** ``fusion.run_script`` — the
# adapter never accepts a free-script step from the planner. The descriptor
# exists in the registry for audit/policy purposes only.
FUSION_TOOLS: tuple[str, ...] = tuple(
    name for name in _REGISTRY_FUSION_TOOLS if name != "fusion.run_script"
)

# Methods that the add-in always exposes regardless of tool surface.
PROTOCOL_AUTH = "auth"
PROTOCOL_TOOLS_LIST = "tools/list"
PROTOCOL_TOOLS_CALL = "tools/call"
PROTOCOL_STATUS = "status"
AUTODESK_MCP_EXECUTE_TOOL = "fusion_mcp_execute"
AUTODESK_MCP_READ_TOOL = "fusion_mcp_read"
AUTODESK_MCP_REQUIRED_TOOLS = {AUTODESK_MCP_EXECUTE_TOOL, AUTODESK_MCP_READ_TOOL}


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
    mcp_url: str | None = None
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
        autodesk_mcp_url: str | None = None,
        enable_autodesk_mcp: bool | None = None,
        status_cache_seconds: float | None = None,
    ) -> None:
        self._configured_discovery_path = discovery_path
        self.timeout_seconds = timeout_seconds
        self._configured_host_override = host_override
        self._configured_autodesk_mcp_url = autodesk_mcp_url
        self._enable_autodesk_mcp = (
            enable_autodesk_mcp if enable_autodesk_mcp is not None else discovery_path is None
        )
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

    @property
    def autodesk_mcp_url(self) -> str:
        return (self._configured_autodesk_mcp_url or settings.fusion_mcp_url).strip()

    def _autodesk_mcp_urls(self) -> list[str]:
        if not self._enable_autodesk_mcp:
            return []
        primary = self.autodesk_mcp_url
        if not primary:
            return []
        urls = [primary]
        parsed = urlparse(primary)
        if parsed.hostname in {"127.0.0.1", "localhost"}:
            netloc = "host.docker.internal"
            if parsed.port:
                netloc = f"{netloc}:{parsed.port}"
            urls.append(urlunparse(parsed._replace(netloc=netloc)))
        return list(dict.fromkeys(urls))

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

    # ---------------------------------------------------------- Autodesk MCP

    def _probe_autodesk_mcp_status(self) -> tuple[FusionAdapterStatus | None, str | None]:
        urls = self._autodesk_mcp_urls()
        if not urls:
            return None, None
        errors: list[str] = []
        for url in urls:
            try:
                init_result = self._call_autodesk_mcp(
                    url,
                    "initialize",
                    {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "truths-forge-ai", "version": "0.1.0"},
                    },
                )
                tools_result = self._call_autodesk_mcp(url, PROTOCOL_TOOLS_LIST, {})
            except FusionBridgeError as exc:
                errors.append(f"{url}: {exc}")
                continue
            tool_names = {
                str(tool.get("name"))
                for tool in tools_result.get("tools", [])
                if isinstance(tool, dict)
            }
            if not AUTODESK_MCP_REQUIRED_TOOLS.issubset(tool_names):
                errors.append(
                    f"{url}: tools oficiais incompletas ({', '.join(sorted(tool_names))})"
                )
                continue
            server_info = init_result.get("serverInfo") if isinstance(init_result, dict) else {}
            server_name = (
                str(server_info.get("name"))
                if isinstance(server_info, dict) and server_info.get("name")
                else "Autodesk Fusion MCP"
            )
            return (
                FusionAdapterStatus(
                    connected=True,
                    transport="http",
                    status="available",
                    detail=f"{server_name} conectado em {url}.",
                    mcp_url=url,
                    consecutive_failures=0,
                    effective_host=urlparse(url).hostname,
                ),
                None,
            )
        return None, "; ".join(errors) if errors else None

    # -------------------------------------------------------------- status

    def status(self) -> FusionAdapterStatus:
        now_monotonic = time.monotonic()
        cached = self._cached_status
        if cached is not None and now_monotonic < self._cached_status_expires_at:
            return cached

        autodesk_status, autodesk_error = self._probe_autodesk_mcp_status()
        if autodesk_status is not None:
            self._record_success()
            self._cache_status(autodesk_status, ttl_seconds=self._status_cache_seconds)
            return autodesk_status

        discovery = self._read_discovery()
        if discovery is None:
            failures, last_at, last_msg = self._snapshot_health()
            status = FusionAdapterStatus(
                connected=False,
                transport="mock",
                status="adapter_mock",
                detail=(
                    "Fusion MCP Server não respondeu"
                    + (f" ({autodesk_error})" if autodesk_error else "")
                    + ". Add-in/bridge legado 'Truth's Forge' também não detectado."
                ),
                mcp_url=self.autodesk_mcp_url if self._enable_autodesk_mcp else None,
                discovery_path=str(self.discovery_path),
                consecutive_failures=failures,
                last_error_at=last_at,
                last_error_message=autodesk_error or last_msg,
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
            transport="local",
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
        status = self.status()
        if status.connected and status.transport == "http" and status.mcp_url:
            return self._execute_via_autodesk_mcp(
                step,
                status.mcp_url,
                plan_id=plan_id,
                project_id=project_id,
            )
        discovery = self._read_discovery()
        if discovery is None:
            return self._error_envelope(
                step,
                error_code="fusion.bridge_not_configured",
                message=(
                    "Fusion MCP Server não respondeu e bridge legado do Fusion 360 "
                    "não foi detectado."
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
        if result.get("transport") == "loopback":
            result = {**result, "transport": "local"}
        return result

    def _execute_via_autodesk_mcp(
        self,
        step: ModelingPlanStep,
        mcp_url: str,
        *,
        plan_id: str | None,
        project_id: str | None,
    ) -> dict[str, Any]:
        try:
            script = build_autodesk_fusion_script(step.tool_name, dict(step.input_json))
            raw_result = self._call_autodesk_mcp(
                mcp_url,
                PROTOCOL_TOOLS_CALL,
                {
                    "name": AUTODESK_MCP_EXECUTE_TOOL,
                    "arguments": {
                        "featureType": "script",
                        "object": {"script": script},
                    },
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
                },
            )
            payload = self._extract_mcp_content_json(raw_result)
        except (FusionBridgeError, ValueError) as exc:
            self._record_failure(str(exc))
            self.invalidate_status_cache()
            return self._error_envelope(
                step,
                error_code="fusion.autodesk_mcp_error",
                message=str(exc),
                retryable=True,
                host_details={"mcp_url": mcp_url},
                transport="http",
            )

        if not isinstance(payload, dict):
            return self._error_envelope(
                step,
                error_code="fusion.autodesk_mcp_invalid_payload",
                message="Fusion MCP Server devolveu conteúdo sem objeto JSON parseável.",
                retryable=False,
                host_details={"mcp_url": mcp_url, "raw_result": raw_result},
                transport="http",
            )

        if payload.get("ok") is False:
            return self._error_envelope(
                step,
                error_code=str(payload.get("error_code") or "fusion.autodesk_script_error"),
                message=str(payload.get("message") or "Script determinístico falhou no Fusion."),
                retryable=bool(payload.get("retryable", True)),
                host_details={"mcp_url": mcp_url, "payload": payload},
                transport="http",
            )

        self._record_success()
        return {
            "ok": True,
            "mcp_server": "fusion_mcp",
            "transport": "http",
            "tool_name": step.tool_name,
            "software": ModelingSoftware.fusion.value,
            "message": str(payload.get("message") or "Comando executado no Fusion MCP Server."),
            "input": step.input_json,
            "result": payload,
            "artifact_paths": list(payload.get("artifact_paths") or []),
        }

    # ----------------------------------------------------------- networking

    def _call_autodesk_mcp(
        self,
        url: str,
        method: str,
        params: dict[str, Any] | None,
    ) -> Any:
        with self._lock:
            self._next_request_id += 1
            request_id = f"fusion-http-{method.replace('/', '-')}-{self._next_request_id}"

        request_payload = build_request(request_id, method, params)
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    url,
                    json=request_payload,
                    headers={"Accept": "application/json, text/event-stream"},
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise FusionBridgeError(
                f"Fusion MCP HTTP indisponível: {exc}",
                data={"url": url},
            ) from exc

        response_payload = self._decode_autodesk_http_response(response)
        if response_payload.get("id") != request_id:
            raise FusionBridgeError(
                f"Fusion MCP devolveu id divergente: esperado {request_id}, "
                f"recebido {response_payload.get('id')!r}.",
                data={"url": url},
            )
        if "error" in response_payload:
            error = response_payload["error"] or {}
            raise FusionBridgeError(
                str(error.get("message") or "Erro desconhecido no Fusion MCP."),
                code=error.get("code"),
                data=error.get("data"),
            )
        result = response_payload.get("result")
        return result if isinstance(result, dict) else {}

    @staticmethod
    def _decode_autodesk_http_response(response: httpx.Response) -> dict[str, Any]:
        content_type = response.headers.get("content-type", "")
        if "text/event-stream" not in content_type:
            payload = response.json()
            if not isinstance(payload, dict):
                raise FusionBridgeError("Fusion MCP devolveu JSON sem objeto raiz.")
            return payload

        for line in response.text.splitlines():
            if not line.startswith("data:"):
                continue
            raw = line.removeprefix("data:").strip()
            if not raw or raw == "[DONE]":
                continue
            payload = json.loads(raw)
            if isinstance(payload, dict):
                return payload
        raise FusionBridgeError("Fusion MCP SSE não trouxe payload data JSON.")

    @staticmethod
    def _extract_mcp_content_json(result: dict[str, Any]) -> dict[str, Any] | None:
        content = result.get("content")
        if not isinstance(content, list):
            return result
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "text":
                continue
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        return None

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
        transport: str = "local",
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "mcp_server": "fusion_mcp",
            "transport": transport,
            "tool_name": step.tool_name,
            "software": ModelingSoftware.fusion.value,
            "error_code": error_code,
            "retryable": retryable,
            "safe_to_retry_after_snapshot_restore": False,
            "message": message,
            "input": step.input_json,
            "host_details": host_details or {},
        }
