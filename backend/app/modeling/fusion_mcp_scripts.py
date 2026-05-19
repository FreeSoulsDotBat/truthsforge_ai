from __future__ import annotations

import json
from textwrap import dedent
from typing import Any

FUSION_SCRIPT_TOOLS: tuple[str, ...] = (
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


def build_autodesk_fusion_script(tool_name: str, arguments: dict[str, Any]) -> str:
    """Build a deterministic Fusion script for the official Autodesk MCP server.

    Autodesk's local Fusion MCP exposes a generic Python execution tool. This
    module keeps Truth's Forge on the narrow adapter path: only backend-owned
    scripts for allowlisted tools are generated, and model/user text only enters
    as JSON data.
    """

    if tool_name not in FUSION_SCRIPT_TOOLS:
        raise ValueError(f"Ferramenta Fusion fora da allowlist: {tool_name}")

    return dedent(
        f"""
        import json
        import math
        import tempfile
        import traceback
        from pathlib import Path

        import adsk.core
        import adsk.fusion

        TOOL_NAME = {json.dumps(tool_name)}
        # Fix #4: ARGUMENTS é desserializado em runtime via json.loads em vez
        # de interpolado direto como literal. O JSON usa ``true``/``false``/
        # ``null`` mas Python espera ``True``/``False``/``None``, então
        # qualquer arg booleano ou nulo crashava o script com
        # ``NameError: name 'true' is not defined``. Pego no trace do bug
        # porta-figurinhas WC2026 (fusion.export_stl com {{"binary": true}}).
        ARGUMENTS = json.loads({repr(json.dumps(arguments, ensure_ascii=False, sort_keys=True))})


        class ToolError(Exception):
            def __init__(self, code, message):
                super().__init__(message)
                self.code = code


        def _emit(payload):
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


        def _app():
            app = adsk.core.Application.get()
            if app is None:
                raise ToolError("fusion.no_application", "Fusion API não retornou aplicação ativa.")
            return app


        def _design():
            design = adsk.fusion.Design.cast(_app().activeProduct)
            if design is None:
                raise ToolError(
                    "fusion.no_active_design",
                    (
                        "Nenhum design ativo no Fusion. "
                        "Abra ou crie um documento antes de chamar tools."
                    ),
                )
            return design


        def _root(design):
            return design.rootComponent


        def _plane_from_ref(design, plane_ref):
            root = _root(design)
            mapping = {{
                "xy": root.xYConstructionPlane,
                "yz": root.yZConstructionPlane,
                "xz": root.xZConstructionPlane,
            }}
            plane = mapping.get(str(plane_ref or "xy").lower())
            if plane is None:
                raise ToolError("fusion.invalid_plane_ref", "plane_ref inválido. Use xy, yz ou xz.")
            return plane


        def _find_sketch(design, sketch_ref=None):
            sketches = _root(design).sketches
            if not sketch_ref:
                if sketches.count == 0:
                    raise ToolError("fusion.no_sketch", "Nenhum sketch disponível na cena.")
                return sketches.item(sketches.count - 1)
            for index in range(sketches.count):
                item = sketches.item(index)
                if item.name == sketch_ref or item.entityToken == sketch_ref:
                    return item
            raise ToolError("fusion.sketch_not_found", "Sketch não encontrado.")


        def _open_design(_args):
            doc = _app().documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
            return {{
                "message": "Documento '{{}}' criado.".format(doc.name),
                "document_name": doc.name,
            }}


        def _create_sketch(args):
            # Fix #2: aceita aliases ``plane``/``plane_ref`` e
            # ``sketch_name``/``name`` porque o LLM (planner) emite o
            # primeiro de cada par mas a versão antiga deste script só
            # lia o segundo, descartando silenciosamente o nome do
            # usuário. Resultado: todo sketch virava "TF_Sketch", e
            # add_rectangle/extrude_profile subsequentes falhavam com
            # "fusion.sketch_not_found" ao procurar pelo nome pedido.
            # Pegado via trace do bug porta-figurinhas WC2026.
            design = _design()
            plane_ref = str(args.get("plane_ref") or args.get("plane") or "xy")
            name = str(args.get("sketch_name") or args.get("name") or "TF_Sketch")
            sketch = _root(design).sketches.add(_plane_from_ref(design, plane_ref))
            sketch.name = name
            return {{
                "message": "Sketch '{{}}' criado em {{}}.".format(sketch.name, plane_ref),
                "sketch_name": sketch.name,
                "sketch_token": sketch.entityToken,
            }}


        def _add_rectangle(args):
            # Fix #6: aceita tres formatos de entrada que o LLM emite:
            # (a) width_mm + height_mm                (legado/canonico)
            # (b) corner1_mm=[x1,y1] + corner2_mm=[x2,y2]   (dois pontos)
            # (c) size_mm=[w, h]                       (lista shorthand)
            # Pegado via trace do bug "modele um prisma": LLM mandou
            # corner1_mm/corner2_mm e o adapter rejeitava com
            # fusion.invalid_dimensions, cascateando em no_profile no
            # extrude subsequente.
            design = _design()
            width_mm = float(args.get("width_mm") or 0.0)
            height_mm = float(args.get("height_mm") or 0.0)

            corner1 = args.get("corner1_mm") or args.get("point1_mm")
            corner2 = args.get("corner2_mm") or args.get("point2_mm")
            if (
                width_mm <= 0
                and height_mm <= 0
                and isinstance(corner1, (list, tuple))
                and isinstance(corner2, (list, tuple))
                and len(corner1) >= 2
                and len(corner2) >= 2
            ):
                width_mm = abs(float(corner2[0]) - float(corner1[0]))
                height_mm = abs(float(corner2[1]) - float(corner1[1]))

            size = args.get("size_mm")
            if (
                width_mm <= 0
                and height_mm <= 0
                and isinstance(size, (list, tuple))
                and len(size) >= 2
            ):
                width_mm = float(size[0])
                height_mm = float(size[1])

            if width_mm <= 0 or height_mm <= 0:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "width_mm/height_mm (ou corner1_mm+corner2_mm, ou size_mm) precisam ser positivos.",
                )
            sketch = _find_sketch(design, args.get("sketch"))
            width_cm = width_mm / 10.0
            height_cm = height_mm / 10.0
            point1 = adsk.core.Point3D.create(-width_cm / 2, -height_cm / 2, 0)
            point2 = adsk.core.Point3D.create(width_cm / 2, height_cm / 2, 0)
            sketch.sketchCurves.sketchLines.addTwoPointRectangle(point1, point2)
            return {{
                "message": "Retângulo {{}}x{{}} mm adicionado a '{{}}'.".format(
                    width_mm, height_mm, sketch.name
                ),
                "sketch_name": sketch.name,
            }}


        def _add_circle(args):
            design = _design()
            diameter_mm = float(args.get("diameter_mm") or 0.0)
            if diameter_mm <= 0:
                raise ToolError("fusion.invalid_dimensions", "diameter_mm precisa ser positivo.")
            sketch = _find_sketch(design, args.get("sketch"))
            radius_cm = diameter_mm / 20.0
            center = adsk.core.Point3D.create(
                float(args.get("center_x_mm") or 0.0) / 10.0,
                float(args.get("center_y_mm") or 0.0) / 10.0,
                0,
            )
            sketch.sketchCurves.sketchCircles.addByCenterRadius(center, radius_cm)
            return {{
                "message": "Círculo ø{{}} mm adicionado a '{{}}'.".format(diameter_mm, sketch.name),
                "sketch_name": sketch.name,
            }}


        def _extrude_profile(args):
            design = _design()
            distance_mm = float(args.get("distance_mm") or 0.0)
            if distance_mm <= 0:
                raise ToolError("fusion.invalid_dimensions", "distance_mm precisa ser positivo.")
            operation = str(args.get("operation") or "new_body").lower()
            operation_map = {{
                "new_body": adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
                "join": adsk.fusion.FeatureOperations.JoinFeatureOperation,
                "cut": adsk.fusion.FeatureOperations.CutFeatureOperation,
                "intersect": adsk.fusion.FeatureOperations.IntersectFeatureOperation,
            }}
            if operation not in operation_map:
                raise ToolError(
                    "fusion.invalid_operation",
                    "operation inválida. Use new_body, join, cut ou intersect.",
                )
            sketch = _find_sketch(design, args.get("sketch"))
            if sketch.profiles.count == 0:
                raise ToolError(
                    "fusion.no_profile",
                    "Sketch não tem profile fechado para extrudar.",
                )
            extrudes = _root(design).features.extrudeFeatures
            input_obj = extrudes.createInput(sketch.profiles.item(0), operation_map[operation])
            input_obj.setDistanceExtent(
                False,
                adsk.core.ValueInput.createByReal(distance_mm / 10.0),
            )
            extrudes.add(input_obj)
            return {{
                "message": "Extrusão de {{}} mm aplicada (operation={{}}).".format(
                    distance_mm, operation
                ),
                "sketch_name": sketch.name,
            }}


        def _set_parameter(args):
            # Fix #1: aceita dois formatos:
            # (a) singular legado:  name='X', expression='10mm', unit='mm'
            # (b) bulk emitido pelo LLM:  parameters dict mapping
            #     param_name -> value (ex: album_width_mm -> 210).
            #     A unidade e inferida do sufixo do nome (_mm/_cm/_deg) e o
            #     valor numerico vira ``expression`` como string.
            # Pegado via trace do bug porta-figurinhas WC2026. Comentarios
            # sem chaves literais porque este modulo inteiro e um f-string
            # template e qualquer ``X`` cru e interpretado como expressao.
            design = _design()

            def _unit_for(param_name, default_unit):
                lower_name = str(param_name).lower()
                if lower_name.endswith("_mm"):
                    return "mm"
                if lower_name.endswith("_cm"):
                    return "cm"
                if lower_name.endswith("_deg"):
                    return "deg"
                if lower_name.endswith("_rad"):
                    return "rad"
                return default_unit

            def _ensure_param(param_name, expression, unit, comment):
                if not param_name or not expression:
                    raise ToolError(
                        "fusion.invalid_parameter",
                        "name e expression são obrigatórios.",
                    )
                existing = design.userParameters.itemByName(param_name)
                if existing is not None:
                    existing.expression = expression
                else:
                    design.userParameters.add(
                        param_name,
                        adsk.core.ValueInput.createByString(expression),
                        unit,
                        comment,
                    )

            bulk = args.get("parameters")
            if isinstance(bulk, dict) and bulk:
                default_unit = str(args.get("unit") or "mm")
                applied = []
                for raw_name, raw_value in bulk.items():
                    param_name = str(raw_name).strip()
                    expression = str(raw_value).strip()
                    unit = _unit_for(param_name, default_unit)
                    _ensure_param(param_name, expression, unit, "")
                    applied.append(param_name)
                return {{
                    "message": "{{}} parâmetro(s) aplicado(s): {{}}.".format(
                        len(applied), ", ".join(applied)
                    ),
                    "applied": applied,
                }}

            # fallback: formato singular legado
            name = str(args.get("name") or "").strip()
            expression = str(args.get("expression") or "").strip()
            unit = str(args.get("unit") or _unit_for(name, "mm"))
            comment = str(args.get("comment") or "")
            _ensure_param(name, expression, unit, comment)
            return {{"message": "Parâmetro '{{}}' = {{}}.".format(name, expression)}}


        def _export(args, fmt):
            # Fix #5: STL e 3MF crashavam com InternalValidationError quando
            # o design não tinha bodies (consequência dos sketches falhados
            # antes dos fixes #0+#2). Adicionado guard explícito para retornar
            # um erro tipado em vez de propagar o crash da SDK do Fusion,
            # que vinha como traceback opaco. STEP funciona com design vazio
            # porque exporta a estrutura mesmo sem geometria.
            design = _design()
            target = str(args.get("target") or "preview." + fmt)
            target_path = Path(target)
            if not target_path.is_absolute():
                target_path = Path(tempfile.gettempdir()) / target_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            export_manager = design.exportManager
            if fmt == "step":
                options = export_manager.createSTEPExportOptions(str(target_path), _root(design))
            elif fmt == "stl":
                if _root(design).bRepBodies.count == 0:
                    raise ToolError(
                        "fusion.no_geometry",
                        "STL requer pelo menos um body sólido; o design está vazio.",
                    )
                options = export_manager.createSTLExportOptions(_root(design), str(target_path))
            elif fmt == "3mf":
                if _root(design).bRepBodies.count == 0:
                    raise ToolError(
                        "fusion.no_geometry",
                        "3MF requer pelo menos um body sólido; o design está vazio.",
                    )
                options = export_manager.createC3MFExportOptions(_root(design), str(target_path))
            else:
                raise ToolError("fusion.invalid_export_format", "Formato não suportado.")
            export_manager.execute(options)
            return {{
                "message": "Exportado para {{}} ({{}}).".format(target_path, fmt),
                "artifact_paths": [str(target_path)],
            }}


        def _validate_dimensions(_args):
            design = _design()
            bodies = _root(design).bRepBodies
            summary = []
            for index in range(bodies.count):
                body = bodies.item(index)
                bbox = body.boundingBox
                summary.append({{
                    "name": body.name,
                    "min_cm": [bbox.minPoint.x, bbox.minPoint.y, bbox.minPoint.z],
                    "max_cm": [bbox.maxPoint.x, bbox.maxPoint.y, bbox.maxPoint.z],
                    "volume_cm3": body.volume,
                }})
            return {{
                "message": "{{}} corpo(s) inspecionado(s).".format(len(summary)),
                "bodies": summary,
            }}


        def _collect_bodies(design):
            bodies = _root(design).bRepBodies
            output = []
            for index in range(bodies.count):
                body = bodies.item(index)
                bbox = body.boundingBox
                try:
                    surface_cm2 = float(body.physicalProperties.area)
                except Exception:
                    surface_cm2 = 0.0
                output.append({{
                    "name": body.name,
                    "is_solid": bool(getattr(body, "isSolid", True)),
                    "volume_mm3": float(getattr(body, "volume", 0.0)) * 1000.0,
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
                }})
            return output


        def _validate_printability(args):
            checks = list(
                args.get("checks")
                or ["is_solid", "volume", "bounding_box", "wall_thickness_approx"]
            )
            min_dimension_mm = 0.8
            min_wall_mm = 0.8
            issues = []
            metrics = {{}}
            for body in _collect_bodies(_design()):
                name = body["name"]
                dims = [
                    abs(body["bbox_max_mm"][i] - body["bbox_min_mm"][i])
                    for i in range(3)
                ]
                metrics[name] = {{
                    "dimensions_mm": dims,
                    "volume_mm3": body["volume_mm3"],
                    "surface_area_mm2": body["surface_area_mm2"],
                    "is_solid": body["is_solid"],
                }}
                if "is_solid" in checks and not body["is_solid"]:
                    issues.append({{
                        "object_name": name,
                        "check": "is_solid",
                        "severity": "error",
                        "message": "Corpo não é sólido fechado.",
                        "recommendation": "Feche o corpo antes de exportar para impressão.",
                    }})
                if "volume" in checks and body["volume_mm3"] <= 0:
                    issues.append({{
                        "object_name": name,
                        "check": "volume",
                        "severity": "error",
                        "message": "Volume não positivo.",
                        "recommendation": "Revise a geometria do corpo.",
                    }})
                if "bounding_box" in checks and dims and min(dims) < min_dimension_mm:
                    issues.append({{
                        "object_name": name,
                        "check": "bounding_box",
                        "severity": "warning",
                        "message": "Dimensão mínima abaixo do perfil de impressão.",
                        "recommendation": "Aumente a escala ou a menor espessura da peça.",
                    }})
                if "wall_thickness_approx" in checks and body["surface_area_mm2"] > 0:
                    approx_wall = 2 * body["volume_mm3"] / body["surface_area_mm2"]
                    metrics[name]["wall_thickness_approx_mm"] = approx_wall
                    if approx_wall < min_wall_mm:
                        issues.append({{
                            "object_name": name,
                            "check": "wall_thickness_approx",
                            "severity": "warning",
                            "message": "Espessura aproximada abaixo do perfil de impressão.",
                            "recommendation": "Aumente paredes ou simplifique regiões finas.",
                        }})
            weights = {{"error": 0.5, "warning": 0.2, "info": 0.05}}
            risk_score = min(1.0, sum(weights.get(item["severity"], 0.0) for item in issues))
            recommendations = []
            for issue in issues:
                rec = issue.get("recommendation")
                if rec and rec not in recommendations:
                    recommendations.append(rec)
            return {{
                "message": "{{}} corpo(s), {{}} issue(s).".format(len(metrics), len(issues)),
                "objects_inspected": len(metrics),
                "checks_executed": checks,
                "issues": issues,
                "metrics": metrics,
                "recommendations": recommendations,
                "risk_score": risk_score,
                "printer_profile": args.get("printer_profile"),
            }}


        def _dispatch(tool_name, args):
            if tool_name == "fusion.open_design":
                return _open_design(args)
            if tool_name == "fusion.create_sketch":
                return _create_sketch(args)
            if tool_name == "fusion.add_rectangle":
                return _add_rectangle(args)
            if tool_name == "fusion.add_circle":
                return _add_circle(args)
            if tool_name == "fusion.extrude_profile":
                return _extrude_profile(args)
            if tool_name == "fusion.set_parameter":
                return _set_parameter(args)
            if tool_name == "fusion.export_step":
                return _export(args, "step")
            if tool_name == "fusion.export_stl":
                return _export(args, "stl")
            if tool_name == "fusion.export_3mf":
                return _export(args, "3mf")
            if tool_name == "fusion.validate_dimensions":
                return _validate_dimensions(args)
            if tool_name == "fusion.validate_printability":
                return _validate_printability(args)
            raise ToolError("fusion.tool_not_implemented", "Ferramenta sem handler determinístico.")


        def run(_context: str):
            try:
                result = _dispatch(TOOL_NAME, dict(ARGUMENTS))
                result.update({{
                    "ok": True,
                    "tool_name": TOOL_NAME,
                    "software": "fusion",
                }})
                _emit(result)
            except ToolError as exc:
                _emit({{
                    "ok": False,
                    "tool_name": TOOL_NAME,
                    "software": "fusion",
                    "error_code": exc.code,
                    "message": str(exc),
                    "retryable": True,
                }})
            except Exception as exc:
                _emit({{
                    "ok": False,
                    "tool_name": TOOL_NAME,
                    "software": "fusion",
                    "error_code": "fusion.script_failed",
                    "message": str(exc),
                    "retryable": True,
                    "traceback": traceback.format_exc(limit=5),
                }})
        """
    ).strip()
