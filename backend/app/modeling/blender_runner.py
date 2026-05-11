from __future__ import annotations

import json
import math
import sys
import traceback
from pathlib import Path
from typing import Any

try:
    import bmesh
    import bpy
except ImportError:  # pragma: no cover - only available inside Blender.
    bmesh = None
    bpy = None


PRIMITIVE_OPS = {
    "cube": "primitive_cube_add",
    "cylinder": "primitive_cylinder_add",
    "uv_sphere": "primitive_uv_sphere_add",
    "plane": "primitive_plane_add",
    "cone": "primitive_cone_add",
}

BOOLEAN_OPERATIONS = {"union", "difference", "intersect"}

PRINTABILITY_CHECKS = {
    "bounding_box",
    "volume",
    "normals",
    "non_manifold",
    "loose_parts",
    "thickness_approx",
    "overhang_approx",
}

OVERHANG_THRESHOLD_DEG = 45.0
THIN_FACE_AREA_M2 = 1.0e-6


def _job_path_from_argv(argv: list[str]) -> Path:
    if "--" not in argv:
        raise ValueError(
            "Job path ausente. Use blender --background --python runner.py -- job.json"
        )
    index = argv.index("--")
    try:
        return Path(argv[index + 1]).resolve()
    except IndexError as exc:
        raise ValueError("Job path ausente depois de --.") from exc


def _write_result(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_export_name(value: str | None, fallback: str, suffix: str) -> str:
    candidate = Path(value or fallback).name.replace("\x00", "").strip()
    if not candidate:
        candidate = fallback
    if not candidate.lower().endswith(suffix.lower()):
        candidate = f"{candidate}{suffix}"
    return candidate


def _ensure_scene(blend_path: Path) -> None:
    if bpy is None:
        raise RuntimeError("bpy não está disponível; execute este script dentro do Blender.")
    if blend_path.is_file():
        bpy.ops.wm.open_mainfile(filepath=str(blend_path))
        return
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 0.001


def _save_scene(blend_path: Path) -> None:
    blend_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))


def _mesh_objects() -> list[Any]:
    return [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]


def _select_only(obj: Any) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def _resolve_object(reference: str | None) -> Any:
    """Resolve an object name; fall back to the active mesh, then to the first mesh."""
    if reference:
        obj = bpy.context.scene.objects.get(reference)
        if obj is None:
            raise ValueError(f"Objeto '{reference}' não encontrado na cena.")
        return obj
    active = bpy.context.view_layer.objects.active
    if active and active.type == "MESH":
        return active
    meshes = _mesh_objects()
    if not meshes:
        raise ValueError("Nenhum objeto mesh disponível na cena.")
    return meshes[0]


def _dimensions_in_meters(input_json: dict[str, Any], default_mm: list[float]) -> list[float]:
    dimensions = input_json.get("dimensions_mm") or input_json.get("dimensions") or default_mm
    if not isinstance(dimensions, list) or len(dimensions) != 3:
        raise ValueError("dimensions_mm deve ser uma lista [x, y, z].")
    return [max(float(value), 0.1) / 1000.0 for value in dimensions]


def _location_meters(input_json: dict[str, Any]) -> tuple[float, float, float]:
    location = input_json.get("location") or {}
    if not isinstance(location, dict):
        raise ValueError("location deve ser um objeto {x, y, z} em mm.")
    return (
        float(location.get("x", 0)) / 1000.0,
        float(location.get("y", 0)) / 1000.0,
        float(location.get("z", 0)) / 1000.0,
    )


def _create_mesh_primitive(input_json: dict[str, Any]) -> dict[str, Any]:
    primitive = str(input_json.get("primitive") or "cube").lower()
    if primitive not in PRIMITIVE_OPS:
        raise ValueError(f"Primitivo não permitido: {primitive}")
    op_name = PRIMITIVE_OPS[primitive]
    op = getattr(bpy.ops.mesh, op_name)

    size_m = _dimensions_in_meters(input_json, [40, 20, 10])
    location = input_json.get("location")
    if location is None:
        location_m = (0.0, 0.0, size_m[2] / 2)
    else:
        location_m = _location_meters(input_json)

    if primitive == "cube":
        op(size=1, location=location_m)
    elif primitive == "cylinder":
        op(radius=size_m[0] / 2, depth=size_m[2], location=location_m)
    elif primitive == "cone":
        op(radius1=size_m[0] / 2, depth=size_m[2], location=location_m)
    elif primitive == "uv_sphere":
        op(radius=size_m[0] / 2, location=location_m)
    elif primitive == "plane":
        op(size=size_m[0], location=location_m)

    obj = bpy.context.object
    obj.name = str(input_json.get("name") or f"TF_{primitive.capitalize()}")[:63]
    obj.dimensions = size_m
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return {
        "message": f"Primitivo {primitive} criado.",
        "objects": [obj.name],
    }


def _apply_bevel(input_json: dict[str, Any]) -> dict[str, Any]:
    width_mm = max(float(input_json.get("bevel_mm") or 1.0), 0.0)
    segments = max(1, min(int(input_json.get("segments") or 3), 16))
    targets = _mesh_objects()
    if not targets:
        raise ValueError("Nenhum objeto mesh encontrado para aplicar bevel.")
    for obj in targets:
        _select_only(obj)
        modifier = obj.modifiers.new(name="TruthsForge_Bevel", type="BEVEL")
        modifier.width = width_mm / 1000.0
        modifier.segments = segments
        modifier.affect = "EDGES"
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    return {
        "message": f"Bevel aplicado em {len(targets)} objeto(s).",
        "objects": [obj.name for obj in targets],
    }


def _apply_boolean(input_json: dict[str, Any]) -> dict[str, Any]:
    operation = str(input_json.get("operation") or "union").lower()
    if operation not in BOOLEAN_OPERATIONS:
        raise ValueError(f"Operação boolean não permitida: {operation}")
    target = _resolve_object(input_json.get("target"))
    other_ref = input_json.get("with") or input_json.get("other")
    other = _resolve_object(other_ref if isinstance(other_ref, str) else None)
    if other.name == target.name:
        raise ValueError("Operação boolean precisa de dois objetos distintos.")

    _select_only(target)
    modifier = target.modifiers.new(name="TruthsForge_Boolean", type="BOOLEAN")
    modifier.operation = operation.upper()
    modifier.object = other
    bpy.ops.object.modifier_apply(modifier=modifier.name)

    if bool(input_json.get("delete_other", True)):
        bpy.ops.object.select_all(action="DESELECT")
        other.select_set(True)
        bpy.ops.object.delete()

    return {
        "message": f"Boolean {operation} aplicada em {target.name}.",
        "objects": [target.name],
    }


def _bmesh_from_object(obj: Any) -> Any:
    mesh = bmesh.new()
    mesh.from_mesh(obj.data)
    mesh.normal_update()
    return mesh


def _measure_object_stats(obj: Any) -> dict[str, Any]:
    bbox = [tuple(obj.matrix_world @ vertex) for vertex in (obj.bound_box[i] for i in range(8))]
    xs = [point[0] for point in bbox]
    ys = [point[1] for point in bbox]
    zs = [point[2] for point in bbox]
    mesh = _bmesh_from_object(obj)
    try:
        volume_m3 = mesh.calc_volume(signed=False)
    except Exception:
        volume_m3 = 0.0
    finally:
        mesh.free()
    return {
        "name": obj.name,
        "bbox_min_mm": [
            round(min(xs) * 1000.0, 3),
            round(min(ys) * 1000.0, 3),
            round(min(zs) * 1000.0, 3),
        ],
        "bbox_max_mm": [
            round(max(xs) * 1000.0, 3),
            round(max(ys) * 1000.0, 3),
            round(max(zs) * 1000.0, 3),
        ],
        "dimensions_mm": [round(value * 1000.0, 3) for value in obj.dimensions],
        "volume_mm3": round(volume_m3 * 1.0e9, 3),
    }


def _count_non_manifold_edges(mesh: Any) -> int:
    return sum(1 for edge in mesh.edges if not edge.is_manifold)


def _count_loose_verts(mesh: Any) -> int:
    return sum(1 for vert in mesh.verts if not vert.link_edges)


def _count_loose_parts(mesh: Any) -> int:
    """Number of disconnected mesh islands."""
    seen: set[int] = set()
    parts = 0
    for vert in mesh.verts:
        if vert.index in seen:
            continue
        parts += 1
        stack = [vert]
        while stack:
            current = stack.pop()
            if current.index in seen:
                continue
            seen.add(current.index)
            for edge in current.link_edges:
                other = edge.other_vert(current)
                if other and other.index not in seen:
                    stack.append(other)
    return parts


def _count_inverted_normals(mesh: Any) -> int:
    """Faces whose normal points opposite to the volume's outward direction.

    Uses a rough heuristic: faces with the dot product between their normal and
    the vector from the centroid to the face center being negative.
    """
    if not mesh.faces:
        return 0
    cx = sum(v.co.x for v in mesh.verts) / max(1, len(mesh.verts))
    cy = sum(v.co.y for v in mesh.verts) / max(1, len(mesh.verts))
    cz = sum(v.co.z for v in mesh.verts) / max(1, len(mesh.verts))
    inverted = 0
    for face in mesh.faces:
        outward_x = face.calc_center_median().x - cx
        outward_y = face.calc_center_median().y - cy
        outward_z = face.calc_center_median().z - cz
        dot = outward_x * face.normal.x + outward_y * face.normal.y + outward_z * face.normal.z
        if dot < 0:
            inverted += 1
    return inverted


def _count_overhang_faces(mesh: Any, threshold_deg: float = OVERHANG_THRESHOLD_DEG) -> int:
    """Faces whose normal angle to the +Z axis exceeds the threshold."""
    if not mesh.faces:
        return 0
    cos_threshold = math.cos(math.radians(threshold_deg))
    overhangs = 0
    for face in mesh.faces:
        # Down-facing faces with steep angle become overhang risks.
        if face.normal.z < -cos_threshold:
            overhangs += 1
    return overhangs


def _count_thin_faces(mesh: Any, min_area_m2: float = THIN_FACE_AREA_M2) -> int:
    return sum(1 for face in mesh.faces if face.calc_area() < min_area_m2)


def _printability_for_object(obj: Any, checks: set[str]) -> dict[str, Any]:
    metrics = _measure_object_stats(obj)
    issues: list[dict[str, Any]] = []
    mesh = _bmesh_from_object(obj)
    try:
        if "non_manifold" in checks:
            count = _count_non_manifold_edges(mesh)
            metrics["non_manifold_edges"] = count
            if count:
                issues.append(
                    {
                        "check": "non_manifold",
                        "severity": "error",
                        "message": f"{count} aresta(s) não-manifold em {obj.name}.",
                        "detail": {"object": obj.name, "edge_count": count},
                    }
                )
        if "loose_parts" in checks:
            parts = _count_loose_parts(mesh)
            metrics["loose_parts"] = parts
            if parts > 1:
                issues.append(
                    {
                        "check": "loose_parts",
                        "severity": "warning",
                        "message": f"{obj.name} possui {parts} pedaços desconectados.",
                        "detail": {"object": obj.name, "parts": parts},
                    }
                )
            loose = _count_loose_verts(mesh)
            if loose:
                issues.append(
                    {
                        "check": "loose_parts",
                        "severity": "warning",
                        "message": f"{loose} vértice(s) soltos em {obj.name}.",
                        "detail": {"object": obj.name, "loose_verts": loose},
                    }
                )
        if "normals" in checks:
            inverted = _count_inverted_normals(mesh)
            metrics["inverted_normals_estimate"] = inverted
            if inverted and inverted >= max(4, len(mesh.faces) // 8):
                issues.append(
                    {
                        "check": "normals",
                        "severity": "warning",
                        "message": (
                            f"Heurística sugere {inverted} face(s) "
                            f"com normal invertida em {obj.name}."
                        ),
                        "detail": {"object": obj.name, "inverted_estimate": inverted},
                    }
                )
        if "overhang_approx" in checks:
            overhangs = _count_overhang_faces(mesh)
            metrics["overhang_face_estimate"] = overhangs
            if overhangs:
                issues.append(
                    {
                        "check": "overhang_approx",
                        "severity": "info",
                        "message": (
                            f"{overhangs} face(s) abaixo de "
                            f"{OVERHANG_THRESHOLD_DEG:.0f}° em {obj.name}; pode exigir suporte."
                        ),
                        "detail": {
                            "object": obj.name,
                            "face_count": overhangs,
                            "threshold_deg": OVERHANG_THRESHOLD_DEG,
                        },
                    }
                )
        if "thickness_approx" in checks:
            thin = _count_thin_faces(mesh)
            metrics["thin_face_estimate"] = thin
            if thin:
                issues.append(
                    {
                        "check": "thickness_approx",
                        "severity": "info",
                        "message": (
                            f"{thin} face(s) muito pequena(s) em {obj.name}; possível parede fina."
                        ),
                        "detail": {"object": obj.name, "face_count": thin},
                    }
                )
        if "volume" in checks and metrics.get("volume_mm3", 0) <= 0:
            issues.append(
                {
                    "check": "volume",
                    "severity": "warning",
                    "message": f"Volume não positivo em {obj.name}; geometria pode estar aberta.",
                    "detail": {"object": obj.name},
                }
            )
    finally:
        mesh.free()
    return {"metrics": metrics, "issues": issues}


def _validate_printability(input_json: dict[str, Any]) -> dict[str, Any]:
    requested = input_json.get("checks") or list(PRINTABILITY_CHECKS)
    if not isinstance(requested, list):
        raise ValueError("checks deve ser uma lista.")
    checks = {check for check in requested if check in PRINTABILITY_CHECKS}
    if not checks:
        checks = set(PRINTABILITY_CHECKS)

    targets = _mesh_objects()
    if not targets:
        return {
            "message": "Nenhum objeto mesh para validar.",
            "objects_inspected": 0,
            "checks_executed": sorted(checks),
            "issues": [],
            "metrics": {},
            "risk_score": 0.0,
        }

    issues: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {}
    for obj in targets:
        per_object = _printability_for_object(obj, checks)
        metrics[obj.name] = per_object["metrics"]
        issues.extend(per_object["issues"])

    weights = {"error": 0.5, "warning": 0.2, "info": 0.05}
    score = min(1.0, sum(weights.get(issue["severity"], 0.05) for issue in issues))
    return {
        "message": (
            f"Printability validada em {len(targets)} objeto(s); "
            f"{len(issues)} aviso(s) registrado(s)."
        ),
        "objects_inspected": len(targets),
        "checks_executed": sorted(checks),
        "issues": issues,
        "metrics": metrics,
        "risk_score": round(score, 3),
        "printer_profile": input_json.get("printer_profile"),
    }


def _validate_mesh(input_json: dict[str, Any]) -> dict[str, Any]:
    obj = _resolve_object(input_json.get("target"))
    mesh = _bmesh_from_object(obj)
    try:
        non_manifold = _count_non_manifold_edges(mesh)
        loose_verts = _count_loose_verts(mesh)
        loose_parts = _count_loose_parts(mesh)
    finally:
        mesh.free()
    ok = non_manifold == 0 and loose_verts == 0
    return {
        "message": (
            f"validate_mesh em {obj.name}: "
            f"non_manifold={non_manifold}, loose_verts={loose_verts}, parts={loose_parts}"
        ),
        "objects": [obj.name],
        "non_manifold_edges": non_manifold,
        "loose_verts": loose_verts,
        "loose_parts": loose_parts,
        "ok_geometry": ok,
    }


def _export_stl(input_json: dict[str, Any], exports_dir: Path) -> dict[str, Any]:
    targets = _mesh_objects()
    if not targets:
        raise ValueError("Nenhum objeto mesh encontrado para exportar STL.")
    exports_dir.mkdir(parents=True, exist_ok=True)
    export_path = exports_dir / _safe_export_name(input_json.get("target"), "preview", ".stl")
    try:
        bpy.ops.wm.stl_export(filepath=str(export_path))
    except Exception:
        try:
            bpy.ops.preferences.addon_enable(module="io_mesh_stl")
            bpy.ops.export_mesh.stl(filepath=str(export_path))
        except Exception as exc:
            raise RuntimeError(
                "Exportação STL não está disponível nesta versão do Blender."
            ) from exc
    return {
        "message": "STL exportado.",
        "artifact_paths": [str(export_path)],
        "objects": [obj.name for obj in targets],
    }


def _export_obj(input_json: dict[str, Any], exports_dir: Path) -> dict[str, Any]:
    targets = _mesh_objects()
    if not targets:
        raise ValueError("Nenhum objeto mesh encontrado para exportar OBJ.")
    exports_dir.mkdir(parents=True, exist_ok=True)
    export_path = exports_dir / _safe_export_name(input_json.get("target"), "preview", ".obj")
    exported = False
    last_error: Exception | None = None
    for attempt in (
        lambda: bpy.ops.wm.obj_export(filepath=str(export_path)),
        lambda: bpy.ops.export_scene.obj(filepath=str(export_path)),
    ):
        try:
            attempt()
            exported = True
            break
        except Exception as exc:
            last_error = exc
    if not exported:
        raise RuntimeError(
            "Exportação OBJ não está disponível nesta versão do Blender."
        ) from last_error
    return {
        "message": "OBJ exportado.",
        "artifact_paths": [str(export_path)],
        "objects": [obj.name for obj in targets],
    }


def _export_3mf(input_json: dict[str, Any], exports_dir: Path) -> dict[str, Any]:
    targets = _mesh_objects()
    if not targets:
        raise ValueError("Nenhum objeto mesh encontrado para exportar 3MF.")
    exports_dir.mkdir(parents=True, exist_ok=True)
    export_path = exports_dir / _safe_export_name(input_json.get("target"), "preview", ".3mf")
    exported = False
    last_error: Exception | None = None
    for attempt in (
        lambda: bpy.ops.wm.threemf_export(filepath=str(export_path)),
        lambda: bpy.ops.export_mesh.threemf(filepath=str(export_path)),
    ):
        try:
            attempt()
            exported = True
            break
        except Exception as exc:
            last_error = exc
    if not exported:
        raise RuntimeError(
            "Exportação 3MF não está disponível nesta versão do Blender."
        ) from last_error
    return {
        "message": "3MF exportado.",
        "artifact_paths": [str(export_path)],
        "objects": [obj.name for obj in targets],
    }


def _execute(job: dict[str, Any]) -> dict[str, Any]:
    tool_name = str(job.get("tool_name") or "")
    input_json = job.get("input_json") if isinstance(job.get("input_json"), dict) else {}
    blend_path = Path(str(job["blend_path"])).resolve()
    exports_dir = Path(str(job["exports_dir"])).resolve()
    _ensure_scene(blend_path)

    if tool_name == "blender.create_mesh_primitive":
        result = _create_mesh_primitive(input_json)
    elif tool_name == "blender.apply_bevel":
        result = _apply_bevel(input_json)
    elif tool_name == "blender.apply_boolean":
        result = _apply_boolean(input_json)
    elif tool_name == "blender.export_stl":
        result = _export_stl(input_json, exports_dir)
    elif tool_name == "blender.export_obj":
        result = _export_obj(input_json, exports_dir)
    elif tool_name == "blender.export_3mf":
        result = _export_3mf(input_json, exports_dir)
    elif tool_name == "blender.validate_mesh":
        result = _validate_mesh(input_json)
    elif tool_name == "blender.validate_printability":
        result = _validate_printability(input_json)
    else:
        raise ValueError(f"Ferramenta não implementada pelo runner Blender: {tool_name}")

    _save_scene(blend_path)
    artifact_paths = list(result.get("artifact_paths") or [])
    if str(blend_path) not in artifact_paths:
        artifact_paths.append(str(blend_path))
    return {
        "ok": True,
        "tool_name": tool_name,
        "blend_path": str(blend_path),
        "artifact_paths": artifact_paths,
        **result,
    }


def main() -> int:
    result_path: Path | None = None
    try:
        job_path = _job_path_from_argv(sys.argv)
        job = json.loads(job_path.read_text(encoding="utf-8"))
        result_path = Path(str(job["result_path"])).resolve()
        _write_result(result_path, _execute(job))
        return 0
    except Exception as exc:
        payload = {
            "ok": False,
            "message": "Falha ao executar etapa Blender.",
            "error": str(exc),
            "traceback_tail": traceback.format_exc()[-4000:],
        }
        if result_path is None:
            try:
                job_path = _job_path_from_argv(sys.argv)
                job = json.loads(job_path.read_text(encoding="utf-8"))
                result_path = Path(str(job["result_path"])).resolve()
            except Exception:
                result_path = Path.cwd() / "blender-runner-error.json"
        _write_result(result_path, payload)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
