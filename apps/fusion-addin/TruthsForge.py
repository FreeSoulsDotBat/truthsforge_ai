"""Truth's Forge AI — Fusion 360 add-in.

Architecture
============

The add-in lives inside the Fusion 360 Python interpreter and acts as a thin
loopback bridge between the Truth's Forge backend (running anywhere on the
host) and the Fusion main thread.

Wire format mirrors the line-delimited JSON-RPC 2.0 used by the rest of the
modeling stack (see ``backend/app/modeling/mcp_servers/protocol.py``). The
add-in implements ``auth``, ``tools/list``, ``status`` and ``tools/call`` over
a TCP socket bound to ``127.0.0.1`` on an OS-assigned port.

Threading rules (Autodesk):

- Worker threads from the socket server MUST NOT touch the Fusion API.
- Every tool call is dispatched to the main thread via ``app.fireCustomEvent``;
  the main-thread handler executes the operation and writes the result back to
  a per-request queue that the worker thread is waiting on.

Security model:

- Ephemeral token generated on startup, written to the discovery file together
  with host/port and the Fusion process PID. The token never crosses the loop
  back interface unencrypted only because the loopback boundary already keeps
  it on this machine.
- The discovery file is created with default user-only permissions; the
  backend is expected to read it from a directory it controls.
- The first message on every connection MUST be ``auth`` with a matching
  token. Anything else closes the connection immediately.

Installation
============

In Fusion 360 → ``Utilities`` → ``Scripts and Add-Ins`` → ``Add-Ins`` →
``+ Add``, then pick this directory. Enable "Run on Startup" if you want the
bridge available without manual launch.

The bridge can be disabled at any time by toggling the add-in off in the same
panel; this is a no-op for the backend, which falls back to mock mode.
"""

from __future__ import annotations

import hmac
import json
import os
import secrets
import socket
import socketserver
import sys
import tempfile
import threading
import traceback
from pathlib import Path
from queue import Empty, Queue
from typing import Any

try:
    import adsk.cam  # noqa: F401  (Fusion namespace bootstrap)
    import adsk.core
    import adsk.fusion
except ImportError:  # pragma: no cover - module is exercised inside Fusion only
    adsk = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Globals (managed by Fusion's run/stop lifecycle)
# ---------------------------------------------------------------------------

_app: Any = None
_ui: Any = None
_server: socketserver.ThreadingTCPServer | None = None
_server_thread: threading.Thread | None = None
_token: str | None = None
_discovery_path: Path | None = None
_custom_event: Any = None
_custom_event_handler: Any = None
_custom_event_id = "truths_forge.modeling.bridge.dispatch"
_pending_requests: dict[str, dict[str, Any]] = {}
_pending_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Tool surface
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Discovery file
# ---------------------------------------------------------------------------

def _resolve_discovery_path() -> Path:
    """Pick the discovery file location.

    Order: ``TRUTHS_FORGE_FUSION_BRIDGE_DISCOVERY`` env override > a stable
    user-scoped path under the home directory. The backend uses the same env
    var, so deployments that customize ``data_dir`` stay in sync.
    """
    override = os.environ.get("TRUTHS_FORGE_FUSION_BRIDGE_DISCOVERY")
    if override:
        return Path(override).expanduser()
    base = Path.home() / ".truths_forge" / "fusion-bridge.json"
    return base


def _write_discovery(port: int, token: str) -> Path:
    path = _resolve_discovery_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "host": "127.0.0.1",
        "port": int(port),
        "token": token,
        "pid": os.getpid(),
        "wire_format": "json-rpc-2.0-line-delimited",
        "tools": list(FUSION_TOOLS),
    }
    # Write atomically so the backend never reads a half-written file.
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)
    return path


def _delete_discovery() -> None:
    if _discovery_path is None:
        return
    try:
        _discovery_path.unlink(missing_ok=True)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# JSON-RPC framing
# ---------------------------------------------------------------------------

def _encode(message: dict[str, Any]) -> bytes:
    return (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")


def _decode(line: bytes) -> dict[str, Any]:
    return json.loads(line.decode("utf-8").strip())


def _build_result(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _build_error(request_id: Any, code: int, message: str, data: Any | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


# ---------------------------------------------------------------------------
# Custom event handler (main thread)
# ---------------------------------------------------------------------------

if adsk is not None:
    class _BridgeCustomEventHandler(adsk.core.CustomEventHandler):  # type: ignore[misc]
        def notify(self, args: Any) -> None:
            try:
                additional = json.loads(args.additionalInfo) if args.additionalInfo else {}
            except (ValueError, TypeError):
                additional = {}
            request_id = additional.get("request_id")
            if not request_id:
                return
            with _pending_lock:
                pending = _pending_requests.get(request_id)
            if pending is None:
                return
            try:
                result = _execute_on_main_thread(pending["name"], pending["arguments"], pending["meta"])
                pending["queue"].put({"ok": True, "result": result})
            except Exception as exc:  # noqa: BLE001 - serialize anything that explodes
                pending["queue"].put(
                    {
                        "ok": False,
                        "error": str(exc),
                        "traceback_tail": traceback.format_exc()[-2000:],
                    }
                )
else:  # pragma: no cover - allow importing outside Fusion for sanity
    class _BridgeCustomEventHandler:  # type: ignore[no-redef]
        def notify(self, args: Any) -> None:
            pass


# ---------------------------------------------------------------------------
# Tool implementations (main thread only)
# ---------------------------------------------------------------------------

class _ToolError(Exception):
    """Raised by tool handlers to signal a structured failure to the caller."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _execute_on_main_thread(
    name: str, arguments: dict[str, Any], meta: dict[str, Any]
) -> dict[str, Any]:
    if adsk is None:
        raise _ToolError("fusion.bridge_no_fusion", "Add-in fora do Fusion 360.")
    if name not in FUSION_TOOLS:
        raise _ToolError(
            "fusion.tool_not_allowlisted",
            f"Ferramenta '{name}' não permitida no add-in.",
        )

    design = adsk.fusion.Design.cast(_app.activeProduct) if _app else None
    if design is None and name not in {"fusion.open_design"}:
        raise _ToolError(
            "fusion.no_active_design",
            "Nenhum design ativo no Fusion. Abra um documento antes de chamar tools.",
        )

    if name == "fusion.open_design":
        return _open_design(arguments)
    if name == "fusion.create_sketch":
        return _create_sketch(design, arguments)
    if name == "fusion.add_rectangle":
        return _add_rectangle(design, arguments)
    if name == "fusion.add_circle":
        return _add_circle(design, arguments)
    if name == "fusion.extrude_profile":
        return _extrude_profile(design, arguments)
    if name == "fusion.set_parameter":
        return _set_parameter(design, arguments)
    if name == "fusion.export_step":
        return _export(design, arguments, "step")
    if name == "fusion.export_stl":
        return _export(design, arguments, "stl")
    if name == "fusion.export_3mf":
        return _export(design, arguments, "3mf")
    if name == "fusion.validate_dimensions":
        return _validate_dimensions(design, arguments)
    if name == "fusion.validate_printability":
        return _validate_printability(design, arguments)
    raise _ToolError("fusion.tool_not_implemented", f"Ferramenta '{name}' sem handler.")


def _open_design(_arguments: dict[str, Any]) -> dict[str, Any]:
    docs = _app.documents
    new_doc = docs.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    return {"message": f"Documento '{new_doc.name}' criado.", "document_name": new_doc.name}


def _root_component(design: Any) -> Any:
    return design.rootComponent


def _plane_from_ref(design: Any, plane_ref: str) -> Any:
    root = _root_component(design)
    mapping = {"xy": root.xYConstructionPlane, "yz": root.yZConstructionPlane, "xz": root.xZConstructionPlane}
    plane = mapping.get(plane_ref.lower())
    if plane is None:
        raise _ToolError(
            "fusion.invalid_plane_ref",
            f"plane_ref inválido: {plane_ref!r}. Use xy/yz/xz.",
        )
    return plane


def _create_sketch(design: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    plane_ref = str(arguments.get("plane_ref") or "xy")
    name = str(arguments.get("name") or "TF_Sketch")
    plane = _plane_from_ref(design, plane_ref)
    sketches = _root_component(design).sketches
    sketch = sketches.add(plane)
    sketch.name = name
    return {
        "message": f"Sketch '{sketch.name}' criado em {plane_ref}.",
        "sketch_name": sketch.name,
        "sketch_token": sketch.entityToken,
    }


def _find_sketch(design: Any, sketch_ref: str | None) -> Any:
    sketches = _root_component(design).sketches
    if not sketch_ref:
        if sketches.count == 0:
            raise _ToolError("fusion.no_sketch", "Nenhum sketch disponível na cena.")
        return sketches.item(sketches.count - 1)
    for index in range(sketches.count):
        item = sketches.item(index)
        if item.name == sketch_ref or item.entityToken == sketch_ref:
            return item
    raise _ToolError("fusion.sketch_not_found", f"Sketch '{sketch_ref}' não encontrado.")


def _add_rectangle(design: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    width_mm = float(arguments.get("width_mm") or 0.0)
    height_mm = float(arguments.get("height_mm") or 0.0)
    if width_mm <= 0 or height_mm <= 0:
        raise _ToolError(
            "fusion.invalid_dimensions",
            "width_mm e height_mm precisam ser positivos.",
        )
    sketch = _find_sketch(design, arguments.get("sketch"))
    width_cm = width_mm / 10.0
    height_cm = height_mm / 10.0
    point1 = adsk.core.Point3D.create(-width_cm / 2, -height_cm / 2, 0)
    point2 = adsk.core.Point3D.create(width_cm / 2, height_cm / 2, 0)
    sketch.sketchCurves.sketchLines.addTwoPointRectangle(point1, point2)
    return {
        "message": f"Retângulo {width_mm}x{height_mm} mm adicionado a '{sketch.name}'.",
        "sketch_name": sketch.name,
    }


def _add_circle(design: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    diameter_mm = float(arguments.get("diameter_mm") or 0.0)
    if diameter_mm <= 0:
        raise _ToolError("fusion.invalid_dimensions", "diameter_mm precisa ser positivo.")
    sketch = _find_sketch(design, arguments.get("sketch"))
    radius_cm = diameter_mm / 20.0  # /2 to radius, /10 to cm
    center = adsk.core.Point3D.create(
        float(arguments.get("center_x_mm") or 0) / 10.0,
        float(arguments.get("center_y_mm") or 0) / 10.0,
        0,
    )
    sketch.sketchCurves.sketchCircles.addByCenterRadius(center, radius_cm)
    return {
        "message": f"Círculo ø{diameter_mm} mm adicionado a '{sketch.name}'.",
        "sketch_name": sketch.name,
    }


def _extrude_profile(design: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    distance_mm = float(arguments.get("distance_mm") or 0.0)
    if distance_mm <= 0:
        raise _ToolError("fusion.invalid_dimensions", "distance_mm precisa ser positivo.")
    operation = str(arguments.get("operation") or "new_body").lower()
    operation_map = {
        "new_body": adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        "join": adsk.fusion.FeatureOperations.JoinFeatureOperation,
        "cut": adsk.fusion.FeatureOperations.CutFeatureOperation,
        "intersect": adsk.fusion.FeatureOperations.IntersectFeatureOperation,
    }
    if operation not in operation_map:
        raise _ToolError(
            "fusion.invalid_operation",
            f"operation inválida: {operation!r}. Use new_body/join/cut/intersect.",
        )
    sketch = _find_sketch(design, arguments.get("sketch"))
    if sketch.profiles.count == 0:
        raise _ToolError("fusion.no_profile", "Sketch não tem profile fechado para extrudar.")
    profile = sketch.profiles.item(0)
    extrudes = _root_component(design).features.extrudeFeatures
    input_obj = extrudes.createInput(profile, operation_map[operation])
    distance_cm = distance_mm / 10.0
    distance_value = adsk.core.ValueInput.createByReal(distance_cm)
    input_obj.setDistanceExtent(False, distance_value)
    extrudes.add(input_obj)
    return {
        "message": f"Extrusão de {distance_mm} mm aplicada (operation={operation}).",
        "sketch_name": sketch.name,
    }


def _set_parameter(design: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    name = str(arguments.get("name") or "").strip()
    expression = str(arguments.get("expression") or "").strip()
    if not name or not expression:
        raise _ToolError("fusion.invalid_parameter", "name e expression são obrigatórios.")
    user_parameters = design.userParameters
    existing = user_parameters.itemByName(name)
    if existing is not None:
        existing.expression = expression
    else:
        unit = str(arguments.get("unit") or "mm")
        comment = str(arguments.get("comment") or "")
        user_parameters.add(name, adsk.core.ValueInput.createByString(expression), unit, comment)
    return {"message": f"Parâmetro '{name}' = {expression}."}


def _export(design: Any, arguments: dict[str, Any], fmt: str) -> dict[str, Any]:
    target = str(arguments.get("target") or f"preview.{fmt}")
    target_path = Path(target)
    if not target_path.is_absolute():
        target_path = Path(tempfile.gettempdir()) / target_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    export_manager = design.exportManager
    if fmt == "step":
        options = export_manager.createSTEPExportOptions(str(target_path), _root_component(design))
    elif fmt == "stl":
        options = export_manager.createSTLExportOptions(_root_component(design), str(target_path))
    elif fmt == "3mf":
        options = export_manager.createC3MFExportOptions(_root_component(design), str(target_path))
    else:
        raise _ToolError("fusion.invalid_export_format", f"Formato '{fmt}' não suportado.")
    export_manager.execute(options)
    return {
        "message": f"Exportado para {target_path} ({fmt}).",
        "artifact_paths": [str(target_path)],
    }


def _validate_dimensions(design: Any, _arguments: dict[str, Any]) -> dict[str, Any]:
    bodies = _root_component(design).bRepBodies
    summary = []
    for index in range(bodies.count):
        body = bodies.item(index)
        bbox = body.boundingBox
        summary.append(
            {
                "name": body.name,
                "min_cm": [bbox.minPoint.x, bbox.minPoint.y, bbox.minPoint.z],
                "max_cm": [bbox.maxPoint.x, bbox.maxPoint.y, bbox.maxPoint.z],
                "volume_cm3": body.volume,
            }
        )
    return {
        "message": f"{len(summary)} corpo(s) inspecionado(s).",
        "bodies": summary,
    }


def _validate_printability(design: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    bodies = _collect_body_summaries(design)
    if not bodies:
        return {
            "message": "Nenhum corpo no design para validar.",
            "objects_inspected": 0,
            "checks_executed": list(arguments.get("checks") or []),
            "issues": [],
            "metrics": {},
            "risk_score": 0.0,
            "printer_profile": arguments.get("printer_profile"),
        }
    from printability_logic import compute_printability_report

    return compute_printability_report(
        bodies,
        checks=arguments.get("checks"),
        printer_profile=arguments.get("printer_profile"),
    )


def _collect_body_summaries(design: Any) -> list[dict[str, Any]]:
    """Extract printability inputs from the active design's bodies.

    All values are converted to millimetres / mm² so the pure logic module
    can stay agnostic of Fusion's centimetre defaults.
    """
    if adsk is None:
        return []
    summaries: list[dict[str, Any]] = []
    root = _root_component(design)
    bodies = root.bRepBodies
    # cos(135°) ≈ -0.7071; faces whose normal Z is below this threshold are
    # pointing strongly downward and count as overhang.
    overhang_normal_threshold = -0.7071
    # Faces smaller than this are "thin features" (0.01 cm² = 1 mm²).
    thin_face_area_cm2 = 0.01
    for index in range(bodies.count):
        body = bodies.item(index)
        try:
            volume_cm3 = float(getattr(body, "volume", 0.0))
        except Exception:
            volume_cm3 = 0.0
        try:
            surface_cm2 = float(getattr(body.physicalProperties, "area", 0.0))
        except Exception:
            surface_cm2 = 0.0
        bbox = body.boundingBox
        downward_area_cm2 = 0.0
        total_face_area_cm2 = 0.0
        thin_area_cm2 = 0.0
        for face_index in range(body.faces.count):
            face = body.faces.item(face_index)
            try:
                evaluator = face.evaluator
                _, area_cm2 = evaluator.getArea()
            except Exception:
                area_cm2 = 0.0
            total_face_area_cm2 += float(area_cm2)
            if area_cm2 < thin_face_area_cm2:
                thin_area_cm2 += float(area_cm2)
            try:
                normal_eval = face.evaluator
                _, normal = normal_eval.getNormalAtPoint(face.pointOnFace)
                if normal.z <= overhang_normal_threshold:
                    downward_area_cm2 += float(area_cm2)
            except Exception:
                continue
        summaries.append(
            {
                "name": body.name,
                "is_solid": bool(getattr(body, "isSolid", True)),
                "volume_mm3": volume_cm3 * 1000.0,
                "surface_area_mm2": surface_cm2 * 100.0,
                "bbox_min_mm": [
                    bbox.minPoint.x * 10.0,
                    bbox.minPoint.y * 10.0,
                    bbox.minPoint.z * 10.0,
                ],
                "bbox_max_mm": [
                    bbox.maxPoint.x * 10.0,
                    bbox.maxPoint.y * 10.0,
                    bbox.maxPoint.z * 10.0,
                ],
                "downward_face_area_mm2": downward_area_cm2 * 100.0,
                "total_face_area_mm2": total_face_area_cm2 * 100.0,
                "thin_face_area_mm2": thin_area_cm2 * 100.0,
            }
        )
    return summaries


# ---------------------------------------------------------------------------
# TCP server
# ---------------------------------------------------------------------------

def _make_handler_class() -> type[socketserver.StreamRequestHandler]:
    class _Handler(socketserver.StreamRequestHandler):
        timeout = 60

        def handle(self) -> None:  # type: ignore[override]
            try:
                authenticated = False
                while True:
                    raw = self.rfile.readline()
                    if not raw:
                        return
                    try:
                        message = _decode(raw)
                    except (ValueError, json.JSONDecodeError):
                        self._send(_build_error(None, -32700, "Mensagem JSON inválida."))
                        continue
                    request_id = message.get("id")
                    method = message.get("method")
                    params = message.get("params") or {}

                    if method == "auth":
                        token_in = (params or {}).get("token") if isinstance(params, dict) else None
                        # Comparação timing-safe (mesmo invariante do servidor
                        # MCP standalone — RNF-001/ADR-019).
                        if (
                            not _token
                            or not isinstance(token_in, str)
                            or not hmac.compare_digest(token_in, _token)
                        ):
                            self._send(_build_error(request_id, -32001, "Token inválido."))
                            return
                        authenticated = True
                        self._send(_build_result(request_id, {"ok": True}))
                        continue
                    if not authenticated:
                        self._send(_build_error(request_id, -32001, "Auth obrigatória."))
                        return
                    if method == "tools/list":
                        self._send(
                            _build_result(
                                request_id,
                                {"server": "fusion_mcp", "tools": list(FUSION_TOOLS)},
                            )
                        )
                        continue
                    if method == "status":
                        self._send(
                            _build_result(
                                request_id,
                                {
                                    "server": "fusion_mcp",
                                    "connected": True,
                                    "transport": "loopback",
                                    "addin_pid": os.getpid(),
                                    "tools": list(FUSION_TOOLS),
                                },
                            )
                        )
                        continue
                    if method == "tools/call":
                        self._dispatch_tool_call(request_id, params)
                        continue
                    self._send(_build_error(request_id, -32601, f"Método não suportado: {method}"))
            except Exception as exc:  # noqa: BLE001 - never let one client kill the server
                try:
                    self._send(_build_error(None, -32603, f"Erro interno: {exc}"))
                except OSError:
                    pass

        def _send(self, payload: dict[str, Any]) -> None:
            try:
                self.wfile.write(_encode(payload))
                self.wfile.flush()
            except OSError:
                pass

        def _dispatch_tool_call(self, request_id: Any, params: dict[str, Any]) -> None:
            name = str((params or {}).get("name") or "")
            arguments = (params or {}).get("arguments") or {}
            meta = (params or {}).get("_meta") or {}
            if not isinstance(arguments, dict) or not isinstance(meta, dict):
                self._send(
                    _build_error(request_id, -32602, "arguments e _meta precisam ser objetos.")
                )
                return
            response_queue: Queue[dict[str, Any]] = Queue(maxsize=1)
            dispatch_id = secrets.token_hex(8)
            with _pending_lock:
                _pending_requests[dispatch_id] = {
                    "name": name,
                    "arguments": arguments,
                    "meta": meta,
                    "queue": response_queue,
                }
            try:
                if _app is None:
                    self._send(_build_error(request_id, -32603, "Fusion não inicializado."))
                    return
                _app.fireCustomEvent(_custom_event_id, json.dumps({"request_id": dispatch_id}))
                try:
                    outcome = response_queue.get(timeout=120)
                except Empty:
                    self._send(_build_error(request_id, -32603, "Timeout esperando main thread."))
                    return
            finally:
                with _pending_lock:
                    _pending_requests.pop(dispatch_id, None)
            # Observabilidade: o backend propaga ``_trace_id`` no _meta.
            # O addin não tem ModelingTracer próprio, mas devolve uma
            # lista ``trace_events: []`` com pelo menos um evento por
            # tool call para o backend incorporar via
            # ``ModelingTracer.ingest_external_events``. Ver
            # backend/app/modeling/observability.py e o plano em
            # C:\Users\Jonatan\.claude\plans\para-que-seja-mais-immutable-puffin.md
            trace_id = meta.get("_trace_id") if isinstance(meta, dict) else None

            if not outcome.get("ok"):
                payload = {
                    "ok": False,
                    "mcp_server": "fusion_mcp",
                    "transport": "loopback",
                    "tool_name": name,
                    "software": "fusion",
                    "error_code": "fusion.execution_failed",
                    "retryable": False,
                    "safe_to_retry_after_snapshot_restore": False,
                    "message": str(outcome.get("error") or "Falha desconhecida."),
                    "host_details": {"traceback_tail": outcome.get("traceback_tail")},
                    "input": arguments,
                    "trace_events": (
                        [
                            {
                                "event_type": "fusion.tool_error",
                                "source": "fusion",
                                "level": "error",
                                "message": str(outcome.get("error") or "Falha desconhecida."),
                                "payload": {
                                    "tool_name": name,
                                    "traceback_tail": outcome.get("traceback_tail"),
                                    "_trace_id": trace_id,
                                },
                            }
                        ]
                        if trace_id
                        else []
                    ),
                }
                self._send(_build_result(request_id, payload))
                return
            tool_result = outcome.get("result") or {}
            payload = {
                "ok": True,
                "mcp_server": "fusion_mcp",
                "transport": "loopback",
                "tool_name": name,
                "software": "fusion",
                "message": tool_result.get("message") or "Tool call executada no Fusion.",
                "input": arguments,
                "artifact_paths": tool_result.get("artifact_paths") or [],
                "result": tool_result,
                "trace_events": (
                    [
                        {
                            "event_type": "fusion.tool_completed",
                            "source": "fusion",
                            "level": "info",
                            "message": (
                                tool_result.get("message")
                                or f"Tool {name} executada no Fusion"
                            ),
                            "payload": {
                                "tool_name": name,
                                "artifact_paths": tool_result.get("artifact_paths") or [],
                                "_trace_id": trace_id,
                            },
                        }
                    ]
                    if trace_id
                    else []
                ),
            }
            self._send(_build_result(request_id, payload))

    return _Handler


class _ThreadedTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def server_bind(self) -> None:  # type: ignore[override]
        # Bind to loopback only; fail loudly if 127.0.0.1 is busy.
        super().server_bind()


# ---------------------------------------------------------------------------
# Fusion lifecycle
# ---------------------------------------------------------------------------

def run(_context: Any) -> None:
    """Called by Fusion when the add-in starts."""
    global _app, _ui, _server, _server_thread, _token, _discovery_path, _custom_event, _custom_event_handler
    if adsk is None:
        return
    _app = adsk.core.Application.get()
    _ui = _app.userInterface
    try:
        _custom_event = _app.registerCustomEvent(_custom_event_id)
    except RuntimeError:
        # already registered (hot reload) — try to fetch it back
        _custom_event = _app.registerCustomEvent(_custom_event_id)
    _custom_event_handler = _BridgeCustomEventHandler()
    _custom_event.add(_custom_event_handler)

    _token = secrets.token_urlsafe(24)
    _server = _ThreadedTCPServer(("127.0.0.1", 0), _make_handler_class())
    bound_host, bound_port = _server.server_address[0], _server.server_address[1]
    _discovery_path = _write_discovery(bound_port, _token)
    _server_thread = threading.Thread(
        target=_server.serve_forever, name="truths_forge_bridge", daemon=True
    )
    _server_thread.start()
    if _ui is not None:
        _ui.messageBox(
            f"Truth's Forge bridge ativo em {bound_host}:{bound_port}.\n"
            f"Discovery em {_discovery_path}.\n"
            "Token efêmero gerado nesta sessão."
        )


def stop(_context: Any) -> None:
    """Called by Fusion when the add-in stops or Fusion exits."""
    global _server, _server_thread, _custom_event, _custom_event_handler
    if _server is not None:
        try:
            _server.shutdown()
            _server.server_close()
        except OSError:
            pass
        _server = None
    _server_thread = None
    _delete_discovery()
    if _app is not None and _custom_event is not None and _custom_event_handler is not None:
        try:
            _custom_event.remove(_custom_event_handler)
            _app.unregisterCustomEvent(_custom_event_id)
        except RuntimeError:
            pass
    _custom_event = None
    _custom_event_handler = None
    if _ui is not None:
        try:
            _ui.messageBox("Truth's Forge bridge encerrada.")
        except Exception:  # pragma: no cover
            pass


if __name__ == "__main__":  # pragma: no cover - manual smoke
    print("Este script roda dentro do Fusion 360 como add-in. Não execute diretamente.", file=sys.stderr)
