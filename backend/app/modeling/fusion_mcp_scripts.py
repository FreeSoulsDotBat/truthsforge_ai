from __future__ import annotations

import json
from textwrap import dedent
from typing import Any

FUSION_SCRIPT_TOOLS: tuple[str, ...] = (
    "fusion.open_design",
    "fusion.create_sketch",
    "fusion.add_rectangle",
    "fusion.add_circle",
    "fusion.add_polygon",
    "fusion.add_line",
    "fusion.add_arc",
    "fusion.add_box",
    "fusion.add_cylinder",
    "fusion.add_sphere",
    "fusion.add_cone",
    "fusion.extrude_profile",
    "fusion.revolve_profile",
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
            # Fix #8: LLM as vezes manda planos abstratos que nao sao
            # construction planes (ex: "InnerFace_Left", "Top",
            # "front_face_of_body_1"). Esses casos exigem face references
            # reais, fora do escopo desta iteracao. Para evitar cascata,
            # fazemos fallback para XY com aviso e emitimos o nome
            # original no message do tool call (visivel via trace).
            root = _root(design)
            mapping = {{
                "xy": root.xYConstructionPlane,
                "yz": root.yZConstructionPlane,
                "xz": root.xZConstructionPlane,
                "top": root.xYConstructionPlane,
                "front": root.xZConstructionPlane,
                "right": root.yZConstructionPlane,
            }}
            normalized = str(plane_ref or "xy").lower()
            plane = mapping.get(normalized)
            if plane is None:
                # Fallback para XY com warning no message — preferivel a
                # cascade de sketch_not_found em add_rectangle/extrude.
                return root.xYConstructionPlane
            return plane


        def _eval_param(value, design, default=None):
            # Fix #10: resolve valor para mm aceitando 4 formatos:
            #   (a) int/float       -> assume mm, retorna direto
            #   (b) "49" / "49.5"  -> parse direto como mm
            #   (c) "param_name"   -> lookup em userParameters
            #                         (com prefixo opcional "-" para negar)
            #   (d) "a + b - c"    -> eval em namespace dos params (mm)
            #
            # Fusion API armazena userParameters em cm internamente; multiplicamos
            # por 10 ao expor em mm. Para expressoes compostas usamos eval com
            # __builtins__ vazio (sandboxed) e namespace so com nomes/valores
            # dos parametros do design.
            if value is None:
                return default
            if isinstance(value, (int, float)):
                return float(value)
            if not isinstance(value, str):
                return default
            s = value.strip()
            if not s:
                return default
            try:
                return float(s)
            except ValueError:
                pass
            # Lookup simples de parametro (com sinal opcional)
            simple_token = s.lstrip("-+").strip()
            if simple_token and all(c.isalnum() or c == "_" for c in simple_token):
                param = design.userParameters.itemByName(simple_token)
                if param is not None:
                    sign = -1.0 if s.startswith("-") else 1.0
                    return sign * float(param.value) * 10.0
            # Expressao composta: eval em namespace fechado (sem builtins).
            namespace = {{}}
            for i in range(design.userParameters.count):
                p = design.userParameters.item(i)
                namespace[p.name] = float(p.value) * 10.0
            try:
                return float(eval(s, {{"__builtins__": {{}}}}, namespace))
            except Exception:
                return default


        def _eval_pair(value_list, design):
            # Helper para listas tipo origin_mm=[x, y] ou cell_size_mm=[w, h]
            # cujos elementos podem ser strings paramentricas.
            if not isinstance(value_list, (list, tuple)) or len(value_list) < 2:
                return None
            a = _eval_param(value_list[0], design)
            b = _eval_param(value_list[1], design)
            if a is None or b is None:
                return None
            return (a, b)


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
            # usuário.
            # Fix #8: planos desconhecidos (ex: 'InnerFace_Left') caiam
            # em XY com warning visivel via trace ao inves de cascade.
            design = _design()
            plane_ref = str(args.get("plane_ref") or args.get("plane") or "xy")
            name = str(args.get("sketch_name") or args.get("name") or "TF_Sketch")
            _KNOWN_PLANES = ("xy", "yz", "xz", "top", "front", "right")
            fallback_applied = plane_ref.lower() not in _KNOWN_PLANES
            sketch = _root(design).sketches.add(_plane_from_ref(design, plane_ref))
            sketch.name = name
            warn_suffix = (
                " [WARN: plano '{{}}' nao suportado, usei XY como fallback]".format(plane_ref)
                if fallback_applied
                else ""
            )
            return {{
                "message": "Sketch '{{}}' criado em {{}}.{{}}".format(
                    sketch.name, plane_ref, warn_suffix
                ),
                "sketch_name": sketch.name,
                "sketch_token": sketch.entityToken,
                "plane_fallback_applied": fallback_applied,
            }}


        def _add_rectangle(args):
            # Fix #6: aceita formatos do LLM:
            # (a) width_mm + height_mm                (legado/canonico)
            # (b) corner1_mm=[x1,y1] + corner2_mm=[x2,y2]   (dois pontos)
            # (c) size_mm=[w, h]                       (lista shorthand)
            # Fix #9: modo grade quando vier cols + rows + cell_size_mm.
            # LLM usa esse formato para criar grades de bolsos. Cada
            # celula vira um retangulo separado no mesmo sketch, com
            # offset incremental.
            design = _design()

            # Fix #10: cols/rows podem vir como nomes de parametro
            # (ex: "num_rows"). Resolve via _eval_param antes do int().
            cols_val = _eval_param(args.get("cols") or args.get("columns"), design, 0.0)
            rows_val = _eval_param(args.get("rows"), design, 0.0)
            cols = int(cols_val or 0)
            rows = int(rows_val or 0)
            cell_pair = _eval_pair(args.get("cell_size_mm"), design)
            if (
                cols > 0
                and rows > 0
                and cell_pair is not None
            ):
                cell_w_mm, cell_h_mm = cell_pair
                gap_mm = _eval_param(args.get("gap_mm"), design, 0.0) or 0.0
                grid_pair = _eval_pair(
                    args.get("grid_origin_mm") or [0, 0], design
                ) or (0.0, 0.0)
                origin_x_mm, origin_y_mm = grid_pair
                sketch = _find_sketch(design, args.get("sketch"))
                count = 0
                for row in range(rows):
                    for col in range(cols):
                        x0_mm = origin_x_mm + col * (cell_w_mm + gap_mm)
                        y0_mm = origin_y_mm + row * (cell_h_mm + gap_mm)
                        p1 = adsk.core.Point3D.create(
                            x0_mm / 10.0, y0_mm / 10.0, 0
                        )
                        p2 = adsk.core.Point3D.create(
                            (x0_mm + cell_w_mm) / 10.0,
                            (y0_mm + cell_h_mm) / 10.0,
                            0,
                        )
                        sketch.sketchCurves.sketchLines.addTwoPointRectangle(p1, p2)
                        count += 1
                return {{
                    "message": (
                        "Grade {{}}x{{}} ({{}} retangulos {{}}x{{}}mm) "
                        "adicionada a '{{}}'."
                    ).format(
                        cols, rows, count, cell_w_mm, cell_h_mm, sketch.name
                    ),
                    "sketch_name": sketch.name,
                    "rectangles_added": count,
                }}

            # Fix #10: width_mm/height_mm podem ser expressoes paramentricas.
            width_mm = _eval_param(args.get("width_mm"), design, 0.0) or 0.0
            height_mm = _eval_param(args.get("height_mm"), design, 0.0) or 0.0

            corner1 = _eval_pair(
                args.get("corner1_mm") or args.get("point1_mm"), design
            )
            corner2 = _eval_pair(
                args.get("corner2_mm") or args.get("point2_mm"), design
            )
            if width_mm <= 0 and height_mm <= 0 and corner1 and corner2:
                width_mm = abs(corner2[0] - corner1[0])
                height_mm = abs(corner2[1] - corner1[1])

            size_pair = _eval_pair(args.get("size_mm"), design)
            if width_mm <= 0 and height_mm <= 0 and size_pair:
                width_mm, height_mm = size_pair

            if width_mm <= 0 or height_mm <= 0:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "width_mm/height_mm (ou corner1_mm+corner2_mm, "
                    "ou size_mm) precisam ser positivos.",
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
            # Fix #10: diameter_mm/center_*_mm podem ser expressoes paramentricas.
            # Onda A quick fix: aceita aliases circle_diameter_mm e radius_mm
            # (LLM varia o nome do campo). center_mm=[x,y] como lista tambem.
            design = _design()
            diameter_mm = _eval_param(
                args.get("diameter_mm") or args.get("circle_diameter_mm"), design, 0.0
            ) or 0.0
            if diameter_mm <= 0:
                radius_mm = _eval_param(args.get("radius_mm"), design, 0.0) or 0.0
                if radius_mm > 0:
                    diameter_mm = radius_mm * 2
            if diameter_mm <= 0:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "diameter_mm (ou radius_mm/circle_diameter_mm) precisa ser positivo.",
                )
            sketch = _find_sketch(design, args.get("sketch"))
            radius_cm = diameter_mm / 20.0
            center_pair = _eval_pair(args.get("center_mm"), design)
            if center_pair is not None:
                center_x_mm, center_y_mm = center_pair
            else:
                center_x_mm = _eval_param(args.get("center_x_mm"), design, 0.0) or 0.0
                center_y_mm = _eval_param(args.get("center_y_mm"), design, 0.0) or 0.0
            center = adsk.core.Point3D.create(
                center_x_mm / 10.0,
                center_y_mm / 10.0,
                0,
            )
            sketch.sketchCurves.sketchCircles.addByCenterRadius(center, radius_cm)
            return {{
                "message": "Círculo ø{{}} mm adicionado a '{{}}'.".format(diameter_mm, sketch.name),
                "sketch_name": sketch.name,
            }}


        def _extrude_profile(args):
            # Fix #10: distance_mm pode ser expressao paramentrica.
            # Aceita tambem distancia negativa (para cut em direcao oposta).
            design = _design()
            distance_mm = _eval_param(args.get("distance_mm"), design, 0.0) or 0.0
            if distance_mm == 0:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "distance_mm precisa ser diferente de zero.",
                )
            operation = str(args.get("operation") or "new_body").lower()
            operation_map = {{
                "new_body": adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
                "join": adsk.fusion.FeatureOperations.JoinFeatureOperation,
                "cut": adsk.fusion.FeatureOperations.CutFeatureOperation,
                "intersect": adsk.fusion.FeatureOperations.IntersectFeatureOperation,
            }}
            # Onda A quick fix: operation desconhecida (ex: 'join_or_new_body'
            # que o LLM inventou) cai em new_body com warning visivel no trace
            # em vez de abortar o step. Tenta primeiro extrair um token valido
            # da string composta.
            operation_warning = ""
            if operation not in operation_map:
                matched = next((op for op in operation_map if op in operation), None)
                fallback_op = matched or "new_body"
                operation_warning = (
                    " [WARN: operation '{{}}' invalida, usei '{{}}']".format(
                        operation, fallback_op
                    )
                )
                operation = fallback_op
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
                "message": "Extrusão de {{}} mm aplicada (operation={{}}).{{}}".format(
                    distance_mm, operation, operation_warning
                ),
                "sketch_name": sketch.name,
            }}


        def _add_polygon(args):
            # Onda A: poligono regular de N lados inscrito num circulo.
            # Constroi os vertices por trigonometria e conecta com linhas
            # (Fusion auto-merge de pontos coincidentes fecha o profile).
            # Aceita diameter_mm OU radius_mm; center_mm=[x,y] opcional.
            design = _design()
            sides = int(_eval_param(args.get("sides"), design, 0.0) or 0)
            if sides < 3:
                raise ToolError("fusion.invalid_dimensions", "sides precisa ser >= 3.")
            radius_mm = _eval_param(args.get("radius_mm"), design, 0.0) or 0.0
            if radius_mm <= 0:
                diameter_mm = _eval_param(args.get("diameter_mm"), design, 0.0) or 0.0
                if diameter_mm > 0:
                    radius_mm = diameter_mm / 2
            if radius_mm <= 0:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "diameter_mm ou radius_mm precisa ser positivo.",
                )
            center_pair = _eval_pair(args.get("center_mm"), design) or (0.0, 0.0)
            cx_cm = center_pair[0] / 10.0
            cy_cm = center_pair[1] / 10.0
            radius_cm = radius_mm / 10.0
            sketch = _find_sketch(design, args.get("sketch"))
            points = []
            for i in range(sides):
                angle = 2 * math.pi * i / sides + math.pi / 2
                points.append(
                    adsk.core.Point3D.create(
                        cx_cm + radius_cm * math.cos(angle),
                        cy_cm + radius_cm * math.sin(angle),
                        0,
                    )
                )
            lines = sketch.sketchCurves.sketchLines
            for i in range(sides):
                lines.addByTwoPoints(points[i], points[(i + 1) % sides])
            return {{
                "message": "Poligono de {{}} lados (r={{}}mm) adicionado a '{{}}'.".format(
                    sides, radius_mm, sketch.name
                ),
                "sketch_name": sketch.name,
            }}


        def _add_line(args):
            # Onda A: polilinha a partir de uma lista de pontos [[x,y],...].
            # closed=true fecha o loop (ultimo -> primeiro), permitindo
            # perfis arbitrarios fechados para extrude/revolve.
            design = _design()
            raw_points = args.get("points_mm") or args.get("points") or []
            if not isinstance(raw_points, list) or len(raw_points) < 2:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "points_mm precisa ser uma lista com >= 2 pontos.",
                )
            pts = []
            for raw in raw_points:
                pair = _eval_pair(raw, design)
                if pair is None:
                    raise ToolError(
                        "fusion.invalid_dimensions",
                        "ponto invalido em points_mm; use [x, y] em mm.",
                    )
                pts.append(adsk.core.Point3D.create(pair[0] / 10.0, pair[1] / 10.0, 0))
            sketch = _find_sketch(design, args.get("sketch"))
            lines = sketch.sketchCurves.sketchLines
            closed = bool(args.get("closed"))
            n = len(pts)
            edges = n if closed else n - 1
            for i in range(edges):
                lines.addByTwoPoints(pts[i], pts[(i + 1) % n])
            return {{
                "message": "Polilinha de {{}} ponto(s){{}} adicionada a '{{}}'.".format(
                    n, " (fechada)" if closed else "", sketch.name
                ),
                "sketch_name": sketch.name,
            }}


        def _add_arc(args):
            # Onda A: arco por centro + ponto inicial + angulo de varredura.
            design = _design()
            center_pair = _eval_pair(args.get("center_mm"), design)
            start_pair = _eval_pair(args.get("start_mm"), design)
            sweep_deg = _eval_param(args.get("sweep_deg"), design, 0.0) or 0.0
            if center_pair is None or start_pair is None or sweep_deg == 0:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "center_mm, start_mm e sweep_deg (!=0) sao obrigatorios.",
                )
            center = adsk.core.Point3D.create(
                center_pair[0] / 10.0, center_pair[1] / 10.0, 0
            )
            start = adsk.core.Point3D.create(
                start_pair[0] / 10.0, start_pair[1] / 10.0, 0
            )
            sketch = _find_sketch(design, args.get("sketch"))
            sweep_rad = sweep_deg * math.pi / 180.0
            sketch.sketchCurves.sketchArcs.addByCenterStartSweep(center, start, sweep_rad)
            return {{
                "message": "Arco de {{}} graus adicionado a '{{}}'.".format(
                    sweep_deg, sketch.name
                ),
                "sketch_name": sketch.name,
            }}


        def _revolve_profile(args):
            # Onda A: revolve um profile fechado em torno de um eixo
            # (x/y/z) por um angulo (default 360 = solido completo).
            # Destrava esferas (semicirculo revolvido), cones, vasos.
            design = _design()
            sketch = _find_sketch(design, args.get("sketch"))
            if sketch.profiles.count == 0:
                raise ToolError(
                    "fusion.no_profile",
                    "Sketch nao tem profile fechado para revolver.",
                )
            angle_deg = _eval_param(args.get("angle_deg"), design, 360.0)
            if not angle_deg:
                angle_deg = 360.0
            operation = str(args.get("operation") or "new_body").lower()
            operation_map = {{
                "new_body": adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
                "join": adsk.fusion.FeatureOperations.JoinFeatureOperation,
                "cut": adsk.fusion.FeatureOperations.CutFeatureOperation,
                "intersect": adsk.fusion.FeatureOperations.IntersectFeatureOperation,
            }}
            op = operation_map.get(operation, operation_map["new_body"])
            axis_name = str(args.get("axis") or "y").lower()
            root = _root(design)
            axis_map = {{
                "x": root.xConstructionAxis,
                "y": root.yConstructionAxis,
                "z": root.zConstructionAxis,
            }}
            axis = axis_map.get(axis_name, root.yConstructionAxis)
            revolves = root.features.revolveFeatures
            input_obj = revolves.createInput(sketch.profiles.item(0), axis, op)
            angle_rad = float(angle_deg) * math.pi / 180.0
            input_obj.setAngleExtent(False, adsk.core.ValueInput.createByReal(angle_rad))
            revolves.add(input_obj)
            return {{
                "message": "Revolucao de {{}} graus (eixo {{}}) aplicada a '{{}}'.".format(
                    angle_deg, axis_name, sketch.name
                ),
                "sketch_name": sketch.name,
            }}


        def _unique_sketch_name(design, base):
            # Gera um nome de sketch livre (base, base (1), base (2)...).
            existing = set()
            sketches = _root(design).sketches
            for i in range(sketches.count):
                existing.add(sketches.item(i).name)
            if base not in existing:
                return base
            n = 1
            while "{{}} ({{}})".format(base, n) in existing:
                n += 1
            return "{{}} ({{}})".format(base, n)


        def _add_box(args):
            # Onda B: primitiva direta. Cria sketch interno + extrude num
            # unico step (corpo editavel na timeline, nao TemporaryBRep).
            design = _design()
            w = _eval_param(args.get("width_mm"), design, 0.0) or 0.0
            d = _eval_param(args.get("depth_mm"), design, 0.0) or 0.0
            h = _eval_param(args.get("height_mm"), design, 0.0) or 0.0
            if w <= 0 or d <= 0 or h <= 0:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "width_mm, depth_mm e height_mm precisam ser positivos.",
                )
            center = _eval_pair(args.get("center_mm"), design) or (0.0, 0.0)
            root = _root(design)
            sketch = root.sketches.add(root.xYConstructionPlane)
            sketch.name = _unique_sketch_name(design, str(args.get("name") or "Box"))
            cx_cm = center[0] / 10.0
            cy_cm = center[1] / 10.0
            w_cm = w / 10.0
            d_cm = d / 10.0
            p1 = adsk.core.Point3D.create(cx_cm - w_cm / 2, cy_cm - d_cm / 2, 0)
            p2 = adsk.core.Point3D.create(cx_cm + w_cm / 2, cy_cm + d_cm / 2, 0)
            sketch.sketchCurves.sketchLines.addTwoPointRectangle(p1, p2)
            extrudes = root.features.extrudeFeatures
            inp = extrudes.createInput(
                sketch.profiles.item(0),
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
            )
            inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(h / 10.0))
            extrudes.add(inp)
            return {{
                "message": "Caixa {{}}x{{}}x{{}} mm criada ('{{}}').".format(
                    w, d, h, sketch.name
                ),
                "sketch_name": sketch.name,
            }}


        def _add_cylinder(args):
            # Onda B: cilindro = circulo + extrude.
            design = _design()
            diameter_mm = _eval_param(args.get("diameter_mm"), design, 0.0) or 0.0
            if diameter_mm <= 0:
                radius_mm = _eval_param(args.get("radius_mm"), design, 0.0) or 0.0
                if radius_mm > 0:
                    diameter_mm = radius_mm * 2
            h = _eval_param(args.get("height_mm"), design, 0.0) or 0.0
            if diameter_mm <= 0 or h <= 0:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "diameter_mm (ou radius_mm) e height_mm precisam ser positivos.",
                )
            center = _eval_pair(args.get("center_mm"), design) or (0.0, 0.0)
            root = _root(design)
            sketch = root.sketches.add(root.xYConstructionPlane)
            sketch.name = _unique_sketch_name(design, str(args.get("name") or "Cylinder"))
            center_pt = adsk.core.Point3D.create(
                center[0] / 10.0, center[1] / 10.0, 0
            )
            sketch.sketchCurves.sketchCircles.addByCenterRadius(
                center_pt, diameter_mm / 20.0
            )
            extrudes = root.features.extrudeFeatures
            inp = extrudes.createInput(
                sketch.profiles.item(0),
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
            )
            inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(h / 10.0))
            extrudes.add(inp)
            return {{
                "message": "Cilindro o{{}}x{{}} mm criado ('{{}}').".format(
                    diameter_mm, h, sketch.name
                ),
                "sketch_name": sketch.name,
            }}


        def _add_sphere(args):
            # Onda B: esfera = semicirculo revolvido 360 graus.
            # Desenha um meio-perfil (linha diametral no eixo + arco) no
            # plano XZ e revolve em torno da linha diametral.
            design = _design()
            diameter_mm = _eval_param(args.get("diameter_mm"), design, 0.0) or 0.0
            if diameter_mm <= 0:
                radius_mm = _eval_param(args.get("radius_mm"), design, 0.0) or 0.0
                if radius_mm > 0:
                    diameter_mm = radius_mm * 2
            if diameter_mm <= 0:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "diameter_mm (ou radius_mm) precisa ser positivo.",
                )
            r_cm = diameter_mm / 20.0
            root = _root(design)
            sketch = root.sketches.add(root.xZConstructionPlane)
            sketch.name = _unique_sketch_name(design, str(args.get("name") or "Sphere"))
            top = adsk.core.Point3D.create(0, r_cm, 0)
            bottom = adsk.core.Point3D.create(0, -r_cm, 0)
            # Linha diametral (eixo de revolucao) + arco semicircular ao lado +X.
            axis_line = sketch.sketchCurves.sketchLines.addByTwoPoints(bottom, top)
            sketch.sketchCurves.sketchArcs.addByCenterStartSweep(
                adsk.core.Point3D.create(0, 0, 0), top, -math.pi
            )
            revolves = root.features.revolveFeatures
            inp = revolves.createInput(
                sketch.profiles.item(0),
                axis_line,
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
            )
            inp.setAngleExtent(False, adsk.core.ValueInput.createByReal(2 * math.pi))
            revolves.add(inp)
            return {{
                "message": "Esfera o{{}} mm criada ('{{}}').".format(
                    diameter_mm, sketch.name
                ),
                "sketch_name": sketch.name,
            }}


        def _add_cone(args):
            # Onda B: cone/frustum = trapezio (ou triangulo) revolvido.
            # top_diameter_mm=0 => cone pontudo; >0 => frustum.
            design = _design()
            base_d = _eval_param(args.get("base_diameter_mm"), design, 0.0) or 0.0
            if base_d <= 0:
                base_r = _eval_param(args.get("base_radius_mm"), design, 0.0) or 0.0
                if base_r > 0:
                    base_d = base_r * 2
            top_d = _eval_param(args.get("top_diameter_mm"), design, 0.0) or 0.0
            h = _eval_param(args.get("height_mm"), design, 0.0) or 0.0
            if base_d <= 0 or h <= 0:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "base_diameter_mm e height_mm precisam ser positivos.",
                )
            base_r_cm = base_d / 20.0
            top_r_cm = top_d / 20.0
            h_cm = h / 10.0
            root = _root(design)
            sketch = root.sketches.add(root.xZConstructionPlane)
            sketch.name = _unique_sketch_name(design, str(args.get("name") or "Cone"))
            # Perfil no semiplano +X: (0,0) -> (base_r,0) -> (top_r,h) -> (0,h)
            # fechando de volta em (0,0). A aresta x=0 e o eixo de revolucao.
            pts = [
                adsk.core.Point3D.create(0, 0, 0),
                adsk.core.Point3D.create(base_r_cm, 0, 0),
                adsk.core.Point3D.create(max(top_r_cm, 0.0), h_cm, 0),
                adsk.core.Point3D.create(0, h_cm, 0),
            ]
            lines = sketch.sketchCurves.sketchLines
            axis_line = lines.addByTwoPoints(pts[3], pts[0])  # aresta x=0 = eixo
            lines.addByTwoPoints(pts[0], pts[1])
            lines.addByTwoPoints(pts[1], pts[2])
            lines.addByTwoPoints(pts[2], pts[3])
            revolves = root.features.revolveFeatures
            inp = revolves.createInput(
                sketch.profiles.item(0),
                axis_line,
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
            )
            inp.setAngleExtent(False, adsk.core.ValueInput.createByReal(2 * math.pi))
            revolves.add(inp)
            shape = "cone" if top_d <= 0 else "tronco de cone"
            return {{
                "message": "{{}} base o{{}} topo o{{}} altura {{}} mm criado ('{{}}').".format(
                    shape, base_d, top_d, h, sketch.name
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

            # Aliases observados em traces reais: ``parameters``,
            # ``parameters_mm``, ``params``. O LLM varia a chave conforme
            # o contexto da unidade. Sempre que vier dict bulk, processa.
            bulk = (
                args.get("parameters")
                or args.get("parameters_mm")
                or args.get("params")
            )
            if isinstance(bulk, dict) and bulk:
                default_unit = (
                    "mm" if args.get("parameters_mm") else str(args.get("unit") or "mm")
                )
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

            # Fix #1.2: bulk implicito — LLM as vezes manda os parametros
            # DIRETO como kwargs no args raiz, sem wrapper ``parameters``.
            # Exemplo de input observado: cols=4, rows=3, sticker_width_mm=46.
            # Detectamos esse modo pela ausencia de ``name``/``expression``
            # singulares + presenca de >=2 chaves que parecem nomes de
            # parametro (valor numerico ou expressao string). Chaves
            # reservadas (notes, unit, comment) sao ignoradas.
            # NOTA: nao usar chaves literais em comentarios deste modulo;
            # ele e um f-string template e isso gera SyntaxError.
            singular_name = str(args.get("name") or "").strip()
            singular_expr = str(args.get("expression") or "").strip()
            if not singular_name and not singular_expr:
                _RESERVED_KEYS = {{
                    "notes",
                    "unit",
                    "comment",
                    "parameters",
                    "parameters_mm",
                    "params",
                }}
                implicit_bulk = {{
                    k: v
                    for k, v in args.items()
                    if k not in _RESERVED_KEYS
                    and (isinstance(v, (int, float)) or isinstance(v, str))
                }}
                if len(implicit_bulk) >= 2:
                    default_unit = str(args.get("unit") or "mm")
                    applied = []
                    for raw_name, raw_value in implicit_bulk.items():
                        param_name = str(raw_name).strip()
                        expression = str(raw_value).strip()
                        unit = _unit_for(param_name, default_unit)
                        _ensure_param(param_name, expression, unit, "")
                        applied.append(param_name)
                    return {{
                        "message": "{{}} parametro(s) aplicado(s) (bulk implicito): {{}}.".format(
                            len(applied), ", ".join(applied)
                        ),
                        "applied": applied,
                    }}

            # fallback: formato singular legado
            name = singular_name
            expression = singular_expr
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
            if tool_name == "fusion.add_polygon":
                return _add_polygon(args)
            if tool_name == "fusion.add_line":
                return _add_line(args)
            if tool_name == "fusion.add_arc":
                return _add_arc(args)
            if tool_name == "fusion.extrude_profile":
                return _extrude_profile(args)
            if tool_name == "fusion.revolve_profile":
                return _revolve_profile(args)
            if tool_name == "fusion.add_box":
                return _add_box(args)
            if tool_name == "fusion.add_cylinder":
                return _add_cylinder(args)
            if tool_name == "fusion.add_sphere":
                return _add_sphere(args)
            if tool_name == "fusion.add_cone":
                return _add_cone(args)
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
