from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any

try:
    import bpy
except ImportError:  # pragma: no cover - only available inside Blender.
    bpy = None


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


def _safe_export_name(value: str | None, fallback: str) -> str:
    candidate = Path(value or fallback).name.replace("\x00", "").strip()
    if not candidate:
        candidate = fallback
    if not candidate.lower().endswith(".stl"):
        candidate = f"{candidate}.stl"
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


def _create_mesh_primitive(input_json: dict[str, Any]) -> dict[str, Any]:
    primitive = str(input_json.get("primitive") or "cube").lower()
    if primitive not in {"cube"}:
        raise ValueError(f"Primitivo não permitido no MVP: {primitive}")
    dimensions = input_json.get("dimensions_mm") or input_json.get("dimensions") or [40, 20, 10]
    if not isinstance(dimensions, list) or len(dimensions) != 3:
        raise ValueError("dimensions_mm deve ser uma lista [x, y, z].")
    size_m = [max(float(value), 0.1) / 1000.0 for value in dimensions]
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, size_m[2] / 2))
    obj = bpy.context.object
    obj.name = str(input_json.get("name") or "TruthsForge_Primitive")[:63]
    obj.dimensions = size_m
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return {
        "message": f"Primitivo {primitive} criado com dimensões {dimensions} mm.",
        "objects": [obj.name],
    }


def _apply_bevel(input_json: dict[str, Any]) -> dict[str, Any]:
    width_mm = max(float(input_json.get("bevel_mm") or 1.0), 0.0)
    segments = max(1, min(int(input_json.get("segments") or 3), 16))
    targets = _mesh_objects()
    if not targets:
        raise ValueError("Nenhum objeto mesh encontrado para aplicar bevel.")
    for obj in targets:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        modifier = obj.modifiers.new(name="TruthsForge_Bevel", type="BEVEL")
        modifier.width = width_mm / 1000.0
        modifier.segments = segments
        modifier.affect = "EDGES"
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        obj.select_set(False)
    return {
        "message": f"Bevel aplicado em {len(targets)} objeto(s).",
        "objects": [obj.name for obj in targets],
    }


def _export_stl(input_json: dict[str, Any], exports_dir: Path) -> dict[str, Any]:
    targets = _mesh_objects()
    if not targets:
        raise ValueError("Nenhum objeto mesh encontrado para exportar STL.")
    exports_dir.mkdir(parents=True, exist_ok=True)
    export_path = exports_dir / _safe_export_name(input_json.get("target"), "preview.stl")
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
    elif tool_name == "blender.export_stl":
        result = _export_stl(input_json, exports_dir)
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
